import discord
from settings import (
    APPROVED_GUILD_IDS,
    CHARACTORS_INFO,
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
from voice import clear_playback_queue, text_to_speech
from discord import app_commands
import discord
from discord.ui import Button, View

ITEMS_PER_PAGE = 4  # 1ページあたりのアイテム数


class StyleSelectionView(View):
    def __init__(self, speaker):
        super().__init__()
        self.speaker = speaker

    async def send_initial_message(self, interaction):
        message = f"**{self.speaker['name']}の利用可能なスタイル:**\n"
        for style in self.speaker["styles"]:
            self.add_item(
                Button(label=style["name"], custom_id=f"select_style_{style['id']}")
            )
        await interaction.response.send_message(content=message, view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        for item in self.children:
            if interaction.data["custom_id"] == item.custom_id:
                style_id = int(item.custom_id.split("_")[-1])
                await self.handle_style_selection(interaction, style_id)
                return True  # 正常に処理されたことを示します
        return False  # 何も一致しなかった場合

    async def handle_style_selection(self, interaction: discord.Interaction, style_id):
        print(f"Selected style ID: {style_id}")  # デバッグメッセージ
        update_style_setting(str(interaction.user.id), style_id)
        await interaction.followup.send(f"スタイルが更新されました: {style_id}")


class PaginationView(View):
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

    @discord.ui.button(
        label="Select", style=discord.ButtonStyle.secondary, custom_id="select_speaker"
    )
    async def select_speaker(self, interaction: discord.Interaction, button: Button):
        try:
            # interaction.response.defer() を使用して、処理時間を確保します
            await interaction.response.defer()

            # インデックスをボタンのcustom_idから取得します
            selected_index = int(button.custom_id.split("_")[-1])

            selected_speaker = self.speakers[selected_index]
            view = StyleSelectionView(selected_speaker)
            await view.send_initial_message(interaction)

        except Exception as e:
            # エラーメッセージをログに記録
            print(f"Error in select_speaker: {e}")
            # ユーザーにフィードバックを提供
            await interaction.followup.send("話者の選択中にエラーが発生しました。")

    async def update_message(self, interaction):
        # 既存の話者選択ボタンをクリア
        self.clear_items()

        # 前へ/次へのボタンを再追加
        self.add_item(
            Button(
                label="前へ",
                style=discord.ButtonStyle.primary,
                custom_id="previous",
                disabled=self.page <= 1,
            )
        )
        self.add_item(
            Button(
                label="次へ",
                style=discord.ButtonStyle.primary,
                custom_id="next",
                disabled=self.page >= self.total_pages,
            )
        )

        start_index = (self.page - 1) * ITEMS_PER_PAGE
        end_index = start_index + ITEMS_PER_PAGE

        # メッセージを更新
        message = f"**利用可能な話者とスタイル (ページ {self.page}/{self.total_pages}):**\n"
        for speaker in self.speakers[start_index:end_index]:
            name = speaker["name"]
            character_id, display_name = get_character_info(name)
            url = f"https://voicevox.hiroshiba.jp/dormitory/{character_id}/"
            message += f"\n- [{display_name}]({url})"

        # 話者選択用のボタンを追加
        for i, speaker in enumerate(self.speakers[start_index:end_index]):
            button = Button(
                label=f'{speaker["name"]}を選択',
                custom_id=f"select_speaker_{i}",
                style=discord.ButtonStyle.secondary,
            )
            button.callback = self.select_speaker
            self.add_item(button)

        # メッセージを送信または更新
        if interaction.response.is_done():
            await interaction.followup.edit_message(
                message_id=interaction.message.id, content=message, view=self
            )
        else:
            await interaction.response.edit_message(content=message, view=self)

    async def send_initial_message(self, interaction):
        self.children[0].disabled = self.page <= 1
        self.children[1].disabled = self.page >= self.total_pages
        start_index = (self.page - 1) * ITEMS_PER_PAGE
        end_index = start_index + ITEMS_PER_PAGE

        # メッセージを更新
        message = f"**利用可能な話者とスタイル (ページ {self.page}/{self.total_pages}):**\n"
        for speaker in self.speakers[start_index:end_index]:
            name = speaker["name"]
            character_id, display_name = get_character_info(name)
            url = f"https://voicevox.hiroshiba.jp/dormitory/{character_id}/"
            message += f"\n- [{display_name}]({url})"

        # 話者選択用のボタンを追加
        for i, speaker in enumerate(self.speakers[start_index:end_index]):
            button = Button(
                label=f'{speaker["name"]}を選択',
                custom_id=f"select_speaker_{i}",
                style=discord.ButtonStyle.secondary,
            )
            button.callback = self.select_speaker
            self.add_item(button)
        # 最初のメッセージを送信
        await interaction.response.send_message(content=message, view=self)


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
        if style_id is None and voice_scope is None:
            messages = []
            for t in voice_scope_description:
                style_id, speaker_name, style_name = get_current_style_details(
                    guild_id, user_id, t
                )
                character_id, display_name = get_character_info(speaker_name)
                url = f"https://voicevox.hiroshiba.jp/dormitory/{character_id}/"
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
            url = f"https://voicevox.hiroshiba.jp/dormitory/{character_id}/"
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
                url = f"https://voicevox.hiroshiba.jp/dormitory/{character_id}/"
                messages.append(
                    f"**{voice_scope_description[t]}**: [{display_name}]({url}) {style_name}"
                )
            await interaction.response.send_message("\n".join(messages))
            return
        elif style_id is not None and voice_scope is not None:
            valid, speaker_name, style_name = validate_style_id(style_id)
            if not valid:
                await interaction.response.send_message(
                    f"スタイルID {style_id} は無効です。`/list`で有効なIDを確認し、正しいIDを入力してください。",
                    ephemeral=True,
                )
                return
            update_style_setting(guild_id, user_id, style_id, voice_scope)
            # もち子さんの場合、特別なクレジット表記を使用
            if speaker_name == "もち子さん":
                speaker_name = "もち子(cv 明日葉よもぎ)"
            character_id = CHARACTORS_INFO.get(speaker_name, "unknown")  # キャラクターIDを取得
            url = f"https://voicevox.hiroshiba.jp/dormitory/{character_id}/"
            await interaction.response.send_message(
                f"{voice_scope_description[voice_scope]}が「[VOICEVOX:{speaker_name}]({url}) {style_name}」に更新されました。"
            )
            return

    except Exception as e:
        await interaction.response.send_message(f"エラーが発生しました: {e}")
    return None  # Return None if there's no response


def update_style_setting(guild_id, user_id, style_id, voice_scope):
    if voice_scope == "user_default":
        speaker_settings[guild_id]["user_default"] = style_id
    elif voice_scope == "announcement":
        speaker_settings[guild_id]["announcement"] = style_id
    elif voice_scope == "user":
        speaker_settings[user_id] = style_id
    save_style_settings()


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


def setup_commands(bot):
    @bot.tree.command(
        name="leave", guilds=APPROVED_GUILD_IDS, description="ボットをボイスチャンネルから切断します。"
    )
    async def leave(interaction: discord.Interaction):
        if interaction.guild.voice_client:
            guild_id = str(interaction.guild_id)
            await clear_playback_queue(guild_id)  # キューをクリア
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

        try:
            if interaction.user.voice and interaction.user.voice.channel:
                channel = interaction.user.voice.channel
                voice_client = await channel.connect(self_deaf=True)
                # 接続成功時の処理
                # 接続メッセージの読み上げ
                welcome_voice = "読み上げを開始します。"

                guild_id = str(interaction.guild_id)
                user_id = str(interaction.user.id)  # コマンド使用者のユーザーID
                user_display_name = (
                    interaction.user.display_name
                )  # Corrected variable name
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
                    speaker_settings[guild_id].get(
                        "user_default", USER_DEFAULT_STYLE_ID
                    ),
                )

                # クレジットをメッセージに追加
                announcement_speaker_name, announcement_style_name = get_style_details(
                    announcement_style_id
                )
                (
                    announcement_character_id,
                    announcement_display_name,
                ) = get_character_info(announcement_speaker_name)
                announcement_url = f"https://voicevox.hiroshiba.jp/dormitory/{announcement_character_id}/"
                user_speaker_name, user_style_name = get_style_details(user_style_id)
                user_character_id, user_tts_display_name = get_character_info(
                    user_speaker_name
                )
                user_url = (
                    f"https://voicevox.hiroshiba.jp/dormitory/{user_character_id}/"
                )
                welcome_message = (
                    f"アナウンス音声「[{announcement_display_name}]({announcement_url}) {announcement_style_name}」\n"
                    f"{user_display_name}さんのテキスト読み上げ音声「[{user_tts_display_name}]({user_url}) {user_style_name}」"
                )

                # メッセージとスタイルIDをキューに追加
                await text_to_speech(
                    voice_client, welcome_voice, announcement_style_id, guild_id
                )
                await interaction.followup.send(welcome_message)
            else:
                await interaction.followup.send(
                    "ボイスチャンネルに接続できませんでした。ユーザーがボイスチャンネルにいることを確認してください。"
                )
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

    # @bot.command(name="remove_command")
    # async def remove_command(ctx, command_name: str):
    #     # このコマンドを使用すると、指定されたコマンド名のスラッシュコマンドを削除します。
    #     guild_id = ctx.guild.id  # コマンドを削除したいギルドのID
    #     guild = discord.Object(id=guild_id)
    #     for cmd in await bot.tree.fetch_commands(guild=guild):
    #         if cmd.name == command_name:
    #             await bot.tree.remove_command(cmd.name, guild=guild)
    #             await ctx.send(f"コマンド {command_name} を削除しました。")
    #             break
    #     else:
    #         await ctx.send(f"コマンド {command_name} が見つかりませんでした。")

    # @bot.command(name="remove_global_command")
    # async def remove_global_command(ctx, command_name: str):
    #     try:
    #         commands = await bot.tree.fetch_commands()  # Fetch all global commands
    #         for cmd in commands:
    #             if cmd.name == command_name:
    #                 if cmd is None:
    #                     await ctx.send("Error: Command object is None.")
    #                     return

    #                 # Attempt to remove the command
    #                 removal_result = bot.tree.remove_command(cmd)
    #                 if asyncio.iscoroutine(removal_result):
    #                     await removal_result
    #                 else:
    #                     # If it's not a coroutine, it's possible that the command was removed without needing to await anything
    #                     pass

    #                 await ctx.send(f"グローバルコマンド {command_name} を削除しました。")
    #                 return
    #         await ctx.send(f"グローバルコマンド {command_name} が見つかりませんでした。")
    #     except Exception as e:
    #         await ctx.send(f"コマンドを削除中にエラーが発生しました: {e}")
    # @bot.tree.command(
    #     name="display_current_settings",
    #     guilds=APPROVED_GUILD_IDS,
    #     description="現在のスタイル設定を表示します。",
    # )
    # async def display_current_settings(interaction: discord.Interaction):
    #     guild_id = str(interaction.guild_id)
    #     user_id = str(interaction.user.id)

    #     # Dictionary to map style types to more user-friendly descriptions
    #     voice_scope_descriptions = {
    #         "user": "ユーザー特有のスタイル",
    #         "announcement": "VC入退室時の通知",
    #         "user_default": "ユーザーデフォルト",
    #     }

    #     # Prepare messages for each style type
    #     messages = []
    #     for voice_scope, description in voice_scope_descriptions.items():
    #         style_id, speaker_name, style_name = get_current_style_details(
    #             guild_id, user_id, voice_scope
    #         )
    #         messages.append(
    #             f"**{description}**: {speaker_name} {style_name} (スタイルID: {style_id})"
    #         )

    #     # Send the compiled message
    #     if messages:
    #         await interaction.response.send_message(
    #             "以下は現在のスタイル設定です:\n" + "\n".join(messages)
    #         )
    #     else:
    #         await interaction.response.send_message("現在のスタイル設定はありません。")
