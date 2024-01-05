import logging
import discord
from discord.ui import Button, View
from discord import app_commands
from settings import (
    ANNOUNCEMENT_URL_BASE,
    APPROVED_GUILD_IDS,
    CHARACTORS_INFO,
    ERROR_MESSAGES,
    ITEMS_PER_PAGE,
    USER_DEFAULT_STYLE_ID,
    ANNOUNCEMENT_DEFAULT_STYLE_ID,
)
from utils import (
    get_character_info,
    speakers,
    speaker_settings,
    save_style_settings,
    get_style_details,
    validate_style_id,
)




# ページネーションのビュークラス
class PaginationView(View):
    """A view for paginating through a list of speakers."""

    def __init__(self, speakers, page=1):
        super().__init__()
        self.speakers = speakers
        self.page = page
        self.total_pages = max(
            1,
            len(speakers) // ITEMS_PER_PAGE
            + (1 if len(speakers) % ITEMS_PER_PAGE > 0 else 0),
        )

    @discord.ui.button(label="前へ", style=discord.ButtonStyle.primary)
    async def previous(self, interaction: discord.Interaction, button: Button):
        self.page = max(1, self.page - 1)
        await self.update_message(interaction)

    @discord.ui.button(label="次へ", style=discord.ButtonStyle.primary)
    async def next(self, interaction: discord.Interaction, button: Button):
        self.page = min(self.total_pages, self.page + 1)
        await self.update_message(interaction)

    async def update_message(self, interaction):
        # 現在のページに応じてボタンの有効/無効を設定
        self.children[0].disabled = self.page <= 1
        self.children[1].disabled = self.page >= self.total_pages

        start_index = (self.page - 1) * ITEMS_PER_PAGE
        end_index = start_index + ITEMS_PER_PAGE

        # メッセージを更新
        message = f"**利用可能な話者とスタイル (ページ {self.page}/{self.total_pages}):**\n"
        for speaker in self.speakers[start_index:end_index]:
            name = speaker["name"]
            character_id, display_name = get_character_info(name)
            url = f"{ANNOUNCEMENT_URL_BASE}/{character_id}/"
            styles_info = " ".join(
                f"{style['name']} (ID: `{style['id']}`)" for style in speaker["styles"]
            )
            message += f"\n[{display_name}]({url}): {styles_info}"

        await interaction.response.edit_message(content=message, view=self)

    async def send_initial_message(self, interaction):
        self.children[0].disabled = self.page <= 1
        self.children[1].disabled = self.page >= self.total_pages
        start_index = (self.page - 1) * ITEMS_PER_PAGE
        end_index = start_index + ITEMS_PER_PAGE

        # メッセージを整形して作成
        message = f"**利用可能な話者とスタイル (ページ {self.page}):**\n"
        for speaker in self.speakers[start_index:end_index]:
            name = speaker["name"]
            character_id, display_name = get_character_info(name)
            url = f"{ANNOUNCEMENT_URL_BASE}/{character_id}/"
            styles_info = " ".join(
                f"{style['name']} (ID: `{style['id']}`)" for style in speaker["styles"]
            )
            message += f"\n[{display_name}]({url}): {styles_info}"

        # 最初のメッセージを送信
        await interaction.response.send_message(
            content=message,
            view=self,
            ephemeral=True,
        )


# 話者選択のビュークラス
class SpeakerSelectionView(View):
    """A view for selecting a speaker from a list."""

    def __init__(self, speakers, page=1):
        super().__init__()
        self.speakers = speakers
        self.page = page
        self.total_pages = max(
            1,
            len(speakers) // ITEMS_PER_PAGE
            + (1 if len(speakers) % ITEMS_PER_PAGE > 0 else 0),
        )
        self.add_buttons()

    async def send_initial_message(self, interaction):
        message_content = self.create_message_content()
        await interaction.response.send_message(
            content=message_content, view=self, ephemeral=True
        )

    def create_message_content(self):
        start_index = (self.page - 1) * ITEMS_PER_PAGE
        end_index = start_index + ITEMS_PER_PAGE
        message_content = f"**利用可能な話者 (ページ {self.page}/{self.total_pages}):**\n"
        for speaker in self.speakers[start_index:end_index]:
            message_content += f"- {speaker['name']}\n"
        return message_content

    async def update_message(self, interaction):
        # ボタンをクリアして再生成
        self.clear_items()
        self.add_buttons()

        # メッセージを更新
        message_content = self.create_message_content()

        if interaction.response.is_done():
            await interaction.followup.edit_message(
                message_id=interaction.message.id, content=message_content, view=self
            )
        else:
            await interaction.response.edit_message(content=message_content, view=self)

    def add_buttons(self):
        start_index = (self.page - 1) * ITEMS_PER_PAGE
        end_index = start_index + ITEMS_PER_PAGE

        for speaker in self.speakers[start_index:end_index]:
            button = discord.ui.Button(
                label=speaker["name"], style=discord.ButtonStyle.secondary
            )
            button.callback = self.create_button_callback(speaker)
            self.add_item(button)

        # 'Previous' button を作成。
        previous_button = discord.ui.Button(
            label="前へ", style=discord.ButtonStyle.primary
        )
        previous_button.disabled = self.page <= 1
        previous_button.callback = self.on_previous_button_click  # 引数なしで修正

        # 'Next' button を作成。
        next_button = discord.ui.Button(label="次へ", style=discord.ButtonStyle.primary)
        next_button.disabled = self.page >= self.total_pages
        next_button.callback = self.on_next_button_click  # 引数なしで修正

        # Add buttons to the view.
        self.add_item(previous_button)
        self.add_item(next_button)

    async def on_previous_button_click(self, interaction: discord.Interaction):
        self.page = max(1, self.page - 1)
        await self.update_message(interaction)

    async def on_next_button_click(self, interaction: discord.Interaction):
        self.page = min(self.total_pages, self.page + 1)
        await self.update_message(interaction)

    def create_button_callback(self, speaker):
        async def button_callback(interaction: discord.Interaction):
            await self.select_speaker(interaction, speaker)

        return button_callback

    async def select_speaker(self, interaction: discord.Interaction, speaker):
        # ここで選択された話者に基づいて処理を行います。
        # 例えば、スタイル選択ビューを表示するなど。
        # ...

        # 以下は一例です。
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild_id)
        view = StyleSelectionView(speaker, user_id, guild_id)
        await interaction.response.edit_message(
            content=f"**{speaker['name']}** のスタイルを選択してください。", view=view
        )


# スタイル選択のビュークラスの例
class StyleSelectionView(View):
    def __init__(self, speaker, user_id, guild_id):
        super().__init__()
        self.speaker = speaker
        self.user_id = user_id
        self.guild_id = guild_id
        self.add_style_buttons()

    def add_style_buttons(self):
        for style in self.speaker["styles"]:
            self.add_item(self.create_style_button(style))

    def create_style_button(self, style):
        style_name = style["name"]
        style_id = style["id"]
        button = discord.ui.Button(
            label=f"{style_name} (ID: {style_id})", style=discord.ButtonStyle.secondary
        )
        button.callback = self.create_button_callback(style_id)
        return button

    def create_button_callback(self, style_id):
        # コールバック関数を動的に生成
        async def button_callback(interaction: discord.Interaction):
            await self.on_select(interaction, style_id)

        return button_callback

    async def on_select(self, interaction: discord.Interaction, style_id: int):
        # スタイル選択時の処理
        style_name = next(
            (
                style["name"]
                for style in self.speaker["styles"]
                if style["id"] == style_id
            ),
            None,
        )
        if not style_name:
            await interaction.response.send_message(
                ERROR_MESSAGES["invalid_style"], ephemeral=True
            )
            return
        speaker_manager = SpeakerManager()
        # スタイル設定を更新
        speaker_manager.update_style_setting(
            self.guild_id, self.user_id, style_id, "user"
        )

        # ユーザーに更新を通知
        await interaction.response.send_message(
            f"スタイルが「{self.speaker['name']} - {style_name}」に設定されました。"
        )


async def handle_voice_config_command(interaction, style_id: int, voice_scope: str):
    guild_id = str(interaction.guild_id)
    user_id = str(interaction.user.id)
    user_display_name = interaction.user.display_name  # Corrected variable name

    # Define descriptions for each voice style scope
    voice_scope_description = {
        "user": f"{user_display_name}さんのテキスト読み上げ音声",  # Corrected variable name
        "announcement": "アナウンス音声",
        "user_default": "ユーザーデフォルトTTS音声",
    }

    try:
        # If style_id and voice_scope are None, display all settings
        if style_id is not None and voice_scope is not None:
            valid, speaker_name, style_name = validate_style_id(style_id)
            if not valid:
                await interaction.response.send_message(
                    ERROR_MESSAGES["invalid_style"],
                    ephemeral=True,
                )
                return
        elif style_id is None and voice_scope is None:
            messages = []
            for t in voice_scope_description:
                style_id, speaker_name, style_name = get_current_style_details(
                    guild_id, user_id, t
                )
                character_id, display_name = get_character_info(speaker_name)
                url = f"{ANNOUNCEMENT_URL_BASE}/{character_id}/"
                messages.append(
                    f"**{voice_scope_description[t]}**: [{display_name}]({url}) {style_name}"
                )
            await interaction.response.send_message("\n".join(messages))
            return
        elif style_id is None and voice_scope is not None:
            # Display current style settings
            current_style_id, speaker_name, style_name = get_current_style_details(
                guild_id, user_id, voice_scope
            )
            # もち子さんの場合、特別なクレジット表記を使用
            if speaker_name == "もち子さん":
                speaker_name = "もち子(cv 明日葉よもぎ)"
            character_id = CHARACTORS_INFO.get(speaker_name, "unknown")  # キャラクターIDを取得
            url = f"{ANNOUNCEMENT_URL_BASE}/{character_id}/"
            await interaction.response.send_message(
                f"現在の{voice_scope_description[voice_scope]}は「[VOICEVOX:{speaker_name}]({url}) {style_name}」です。"
            )
        elif style_id is not None and voice_scope is None:
            messages = []
            for t in voice_scope_description:
                style_id, speaker_name, style_name = get_current_style_details(
                    guild_id, user_id, t
                )
                character_id, display_name = get_character_info(speaker_name)
                url = f"{ANNOUNCEMENT_URL_BASE}/{character_id}/"
                messages.append(
                    f"**{voice_scope_description[t]}**: [{display_name}]({url}) {style_name}"
                )
            await interaction.response.send_message("\n".join(messages))
            return
        speaker_manager = SpeakerManager()
        # スタイル設定を更新
        speaker_manager.update_style_setting(guild_id, user_id, style_id, voice_scope)
        # もち子さんの場合、特別なクレジット表記を使用
        if speaker_name == "もち子さん":
            speaker_name = "もち子(cv 明日葉よもぎ)"
        character_id = CHARACTORS_INFO.get(speaker_name, "unknown")  # キャラクターIDを取得
        url = f"{ANNOUNCEMENT_URL_BASE}/{character_id}/"
        await interaction.response.send_message(
            f"{voice_scope_description[voice_scope]}が「[VOICEVOX:{speaker_name}]({url}) {style_name}」に更新されました。"
        )
        return

    except Exception as e:
        await interaction.response.send_message(f"エラーが発生しました: {e}")
        logging.error(f"Error in handle_voice_config_command: {e}", exc_info=True)


class SpeakerManager:
    def __init__(self):
        self.speaker_settings = {}

    def update_style_setting(self, guild_id, user_id, style_id, voice_scope):
        valid_scopes = ["user_default", "announcement", "user"]
        if voice_scope not in valid_scopes:
            logging.error(f"無効なvoice_scopeが指定されました: {voice_scope}")
            return

        try:
            if voice_scope == "user_default":
                self.speaker_settings[guild_id]["user_default"] = style_id
            elif voice_scope == "announcement":
                self.speaker_settings[guild_id]["announcement"] = style_id
            elif voice_scope == "user":
                self.speaker_settings[user_id] = style_id
            # ここで設定を保存するロジックを追加
        except KeyError as e:
            logging.error(f"キーが見つかりません: {e}")


def get_current_style_details(guild_id, user_id, voice_scope):
    if voice_scope == "user_default":
        style_id = speaker_settings[guild_id].get("user_default", USER_DEFAULT_STYLE_ID)
    elif voice_scope == "announcement":
        style_id = speaker_settings[guild_id].get(
            "announcement", ANNOUNCEMENT_DEFAULT_STYLE_ID
        )
    elif voice_scope == "user":
        style_id = speaker_settings.get(user_id, USER_DEFAULT_STYLE_ID)

    speaker_name, style_name = get_style_details(style_id)
    return style_id, speaker_name, style_name


def setup_commands(server, bot):
    @bot.tree.command(
        name="leave", guilds=APPROVED_GUILD_IDS, description="ボットをボイスチャンネルから切断します。"
    )
    async def leave(interaction: discord.Interaction):
        if interaction.guild.voice_client:
            guild_id = str(interaction.guild_id)
            await server.clear_playback_queue(guild_id)  # キューをクリア
            if "text_channel" in speaker_settings.get(guild_id, {}):
                del speaker_settings[guild_id]["text_channel"]
            await interaction.guild.voice_client.disconnect()  # 切断
            await interaction.response.send_message("ボイスチャンネルから切断しました。")

    @bot.tree.command(
        name="voice_config",
        guilds=APPROVED_GUILD_IDS,
        description="あなたのテキスト読み上げキャラクターを設定します。",
    )
    async def voice_config(interaction: discord.Interaction, style_id: int):
        await handle_voice_config_command(interaction, style_id, voice_scope="user")

    @bot.tree.command(
        name="server_voice_config",
        guilds=APPROVED_GUILD_IDS,
        description="サーバーのテキスト読み上げキャラクターを表示また設定します。",
    )
    @app_commands.choices(
        voice_scope=[
            app_commands.Choice(name="アナウンス音声", value="announcement"),
            app_commands.Choice(name="ユーザーデフォルトTTS音声", value="user_default"),
        ]
    )
    async def server_voice_config(
        interaction: discord.Interaction, voice_scope: str, style_id: int = None
    ):
        await handle_voice_config_command(interaction, style_id, voice_scope)

    @bot.tree.command(
        name="join",
        guilds=APPROVED_GUILD_IDS,
        description="ボットをボイスチャンネルに接続し、読み上げを開始します。",
    )
    async def join(interaction: discord.Interaction):
        # defer the response to keep the interaction alive
        await interaction.response.defer()
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.followup.send(ERROR_MESSAGES["connection"])
            return
        try:
            channel = interaction.user.voice.channel
            voice_client = await channel.connect(self_deaf=True)
            # 接続成功時の処理
            # 接続メッセージの読み上げ
            welcome_voice = "読み上げを開始します。"

            guild_id = str(interaction.guild_id)
            user_id = str(interaction.user.id)  # コマンド使用者のユーザーID
            user_display_name = interaction.user.display_name  # Corrected variable name
            text_channel_id = str(interaction.channel_id)  # このコマンドを使用したテキストチャンネルID

            # サーバー設定が存在しない場合は初期化
            if guild_id not in speaker_settings:
                speaker_settings[guild_id] = {"text_channel": text_channel_id}
            else:
                # 既にサーバー設定が存在する場合はテキストチャンネルIDを更新
                speaker_settings[guild_id]["text_channel"] = text_channel_id

            save_style_settings()  # 変更を保存

            # 通知スタイルIDを取得
            announcement_style_id = speaker_settings.get(guild_id, {}).get(
                "announcement", ANNOUNCEMENT_DEFAULT_STYLE_ID
            )
            # ユーザーのスタイルIDを取得
            user_style_id = speaker_settings.get(
                user_id,
                speaker_settings[guild_id].get("user_default", USER_DEFAULT_STYLE_ID),
            )

            # クレジットをメッセージに追加
            announcement_speaker_name, announcement_style_name = get_style_details(
                announcement_style_id
            )
            (
                announcement_character_id,
                announcement_display_name,
            ) = get_character_info(announcement_speaker_name)
            announcement_url = f"{ANNOUNCEMENT_URL_BASE}/{announcement_character_id}/"
            user_speaker_name, user_style_name = get_style_details(user_style_id)
            user_character_id, user_tts_display_name = get_character_info(
                user_speaker_name
            )
            user_url = f"{ANNOUNCEMENT_URL_BASE}/{user_character_id}/"
            welcome_message = (
                f"アナウンス音声「[{announcement_display_name}]({announcement_url}) {announcement_style_name}」\n"
                f"{user_display_name}さんのテキスト読み上げ音声「[{user_tts_display_name}]({user_url}) {user_style_name}」"
            )

            # メッセージとスタイルIDをキューに追加
            await server.text_to_speech(
                voice_client, welcome_voice, announcement_style_id, guild_id
            )
            await interaction.followup.send(welcome_message)
        except Exception as e:
            # エラーメッセージをユーザーに通知
            await interaction.followup.send(f"接続中にエラーが発生しました: {e}")

    @bot.tree.command(
        name="list", guilds=APPROVED_GUILD_IDS, description="話者とそのスタイルをページングして表示します。"
    )
    async def list(interaction: discord.Interaction):
        if not speakers:
            await interaction.response.send_message("話者のデータを取得できませんでした。")
            return

        # 最初のページを表示
        view = PaginationView(speakers)
        await view.send_initial_message(interaction)

    @bot.tree.command(
        name="select_speaker", guilds=APPROVED_GUILD_IDS, description="話者を選択します。"
    )
    async def select_speaker(interaction: discord.Interaction):
        if not speakers:
            await interaction.response.send_message("話者のデータを取得できませんでした。")
            return

        # 話者選択のためのページネーションビューを作成
        view = SpeakerSelectionView(speakers)
        await view.send_initial_message(interaction)

    @bot.tree.command(
        name="help", guilds=APPROVED_GUILD_IDS, description="利用可能なコマンドとその説明を表示します。"
    )
    async def help_command(interaction: discord.Interaction):
        help_text = """
        **VOICECHATLOIDヘルプ**
        以下は利用可能なコマンドのリストです：

        `/join` - ボットをユーザーのいるボイスチャンネルに接続します。
        `/leave` - ボットをボイスチャンネルから切断します。
        `/voice_config [style_id]` - ユーザーのテキスト読み上げ音声スタイルを設定します。
        `/server_voice_config [voice_scope] [style_id]` - サーバーのテキスト読み上げキャラクターを設定します。
        `/list` - 利用可能な話者とそのスタイルを表示します。

        各コマンドの詳細については、コマンドを入力時に表示される説明を参照してください。
        """
        await interaction.response.send_message(help_text)
