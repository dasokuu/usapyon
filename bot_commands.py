import asyncio
import logging
import discord
from discord.ui import Button, View
from settings import (
    DORMITORY_URL_BASE,
    APPROVED_GUILD_IDS,
    ERROR_MESSAGES,
    USER_DEFAULT_STYLE_ID,
    ANNOUNCEMENT_DEFAULT_STYLE_ID,
)
from utils import (
    get_character_info,
    load_style_settings,
    config_pickle,
    save_style_settings,
    get_style_details,
    speakers,
    update_style_setting,
    validate_style_id,
)

logging.basicConfig(level=logging.DEBUG)


def setup_commands(server, bot):
    # ボットをボイスチャンネルから切断するコマンド
    @bot.tree.command(
        name="leave", guilds=APPROVED_GUILD_IDS, description="ボットをボイスチャンネルから切断します。"
    )
    async def leave(interaction: discord.Interaction):
        # ボイスクライアントが存在するか確認
        if interaction.guild.voice_client:
            guild_id = interaction.guild_id
            await server.clear_playback_queue(guild_id)  # キューをクリア
            if "text_channel" in config_pickle.get(guild_id, {}):
                del config_pickle[guild_id]["text_channel"]
            await interaction.guild.voice_client.disconnect()  # 切断
            await interaction.response.send_message("ボイスチャンネルから切断しました。")

    # ボットをボイスチャンネルに接続するコマンド
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
            voice_client = await connect_to_voice_channel(interaction)
            await welcome_user(server, interaction, voice_client)
        except discord.ClientException as e:
            logging.error(f"Connection error: {e}")
            await interaction.followup.send(f"接続中にエラーが発生しました: {e}")

    @bot.tree.command(
        name="config", guilds=APPROVED_GUILD_IDS, description="読み上げ音声を設定します。"
    )
    async def config(interaction: discord.Interaction):
        voice_scope_description = {
            "user": f"{interaction.user.display_name}さん専用の読み上げ音声",
            "announcement": "入退出時のアナウンス音声",
            "user_default": "未設定ユーザーの読み上げ音声",
        }
        # ボタンとビューの設定
        view = View()
        for voice_scope, label in voice_scope_description.items():
            # 各スコープに対応するボタンを作成
            if voice_scope == "user":
                button = Button(style=discord.ButtonStyle.primary, label=label)
            else:
                button = Button(style=discord.ButtonStyle.secondary, label=label)

            # ボタンが押されたときの処理を定義
            async def on_button_click(
                interaction: discord.Interaction,
                button: Button,
                voice_scope,  # 引数名をvoice_scopeに変更
            ):
                # ここで話者のページングを開始
                await initiate_speaker_paging(interaction, voice_scope)

            # on_button_click関数をボタンのコールバックとして設定
            # Pythonのデフォルト引数の挙動を利用して、各ボタンに適切なvoice_scopeを渡す
            button.callback = lambda interaction, button=button, voice_scope=voice_scope: on_button_click(
                interaction, button, voice_scope
            )

            # ビューにボタンを追加
            view.add_item(button)

        # ユーザーにボタンを表示
        await interaction.response.send_message(
            "設定対象を選んでください：", view=view, ephemeral=True
        )

    class PagingView(discord.ui.View):
        def __init__(self, speakers, voice_scope):
            super().__init__()
            self.speakers = speakers
            self.voice_scope = voice_scope
            self.current_page = 0

        @discord.ui.button(label="<<", style=discord.ButtonStyle.blurple)
        async def first_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.current_page = 0
            await self.update_speaker_list(interaction)

        @discord.ui.button(label="<", style=discord.ButtonStyle.blurple)
        async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if self.current_page > 0:
                self.current_page -= 1
            else:
                self.current_page = len(self.speakers) - 1
            await self.update_speaker_list(interaction)

        @discord.ui.button(label=">", style=discord.ButtonStyle.blurple)
        async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if self.current_page < len(self.speakers) - 1:
                self.current_page += 1
            else:
                self.current_page = 0
            await self.update_speaker_list(interaction)

        @discord.ui.button(label=">>", style=discord.ButtonStyle.blurple)
        async def last_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.current_page = len(self.speakers) - 1
            await self.update_speaker_list(interaction)

        async def update_speaker_list(self, interaction: discord.Interaction):
            voice_scope_description = {
                "user": f"{interaction.user.display_name}さん専用の読み上げ音声",
                "announcement": "入退出時のアナウンス音声",
                "user_default": "未設定ユーザーの読み上げ音声",
            }
            # 'interaction'を正しく使ってメッセージを編集
            speaker_name = self.speakers[self.current_page]["name"]
            content = f"矢印ボタンで使用するキャラクターを選択し、スタイルを選んでください：\nページ {self.current_page + 1} / {len(self.speakers)}\n"
            speaker_character_id, speaker_display_name = get_character_info(
                speaker_name
            )
            speaker_url = f"{DORMITORY_URL_BASE}/{speaker_character_id}/"

            # 歓迎メッセージを作成
            content += f"[{speaker_display_name}]({speaker_url})"
            # 古いスタイルのボタンを削除して新しいものを追加
            self.clear_items()

            # ナビゲーションボタンを追加
            self.add_item(self.first_button)
            self.add_item(self.previous_button)
            self.add_item(self.next_button)
            self.add_item(self.last_button)

            # 現在の話者の各スタイルに対応するボタンを追加
            for style in self.speakers[self.current_page]["styles"]:
                style_button = discord.ui.Button(
                    label=style["name"], style=discord.ButtonStyle.secondary
                )

                # ボタンが押されたときの処理を定義
                async def handle_style_button_click(
                    interaction: discord.Interaction,
                    button: discord.ui.Button,
                    style_id=style["id"],
                ):
                    await on_style_button_click(interaction, button, style_id)

                async def on_style_button_click(
                    interaction: discord.Interaction,
                    button: Button,
                    style_id,
                ):
                    # スタイル変更をここで処理
                    valid, speaker_name, style_name = validate_style_id(style_id)
                    if not valid:
                        await interaction.response.edit_message(
                            f"スタイルID {style_id} は無効です。`/list`で有効なIDを確認し、正しいIDを入力してください。",
                            view=self,
                        )
                    update_style_setting(
                        interaction.guild.id,
                        interaction.user.id,
                        style_id,
                        self.voice_scope,
                    )
                    speaker_character_id, speaker_display_name = get_character_info(
                        speaker_name
                    )
                    speaker_url = f"{DORMITORY_URL_BASE}/{speaker_character_id}/"
                    await interaction.response.send_message(
                        f"{voice_scope_description[self.voice_scope]}が「[{speaker_display_name}]({speaker_url}) {style_name}」に更新されました。"
                    )

                # Capture the current button and style_id using default arguments
                style_button.callback = (
                    lambda interaction, button=style_button, style_id=style[
                        "id"
                    ]: asyncio.create_task(
                        handle_style_button_click(interaction, button, style_id)
                    )
                )

                self.add_item(style_button)
            await interaction.response.edit_message(content=content, view=self)

    async def initiate_speaker_paging(interaction: discord.Interaction, voice_scope):
        voice_scope_description = {
            "user": f"{interaction.user.display_name}さん専用の読み上げ音声",
            "announcement": "入退出時のアナウンス音声",
            "user_default": "未設定ユーザーの読み上げ音声",
        }
        # 初期ページングビューを作成
        view = PagingView(speakers, voice_scope)
        # 最初の話者を表示
        speaker_name = speakers[0]["name"] if speakers else "利用可能な話者がいません"
        content = f"矢印ボタンで使用するキャラクターを選択し、スタイルを選んでください：\nページ 1 / {len(speakers)}\n"
        speaker_character_id, speaker_display_name = get_character_info(speaker_name)
        speaker_url = f"{DORMITORY_URL_BASE}/{speaker_character_id}/"

        content += f"[{speaker_display_name}]({speaker_url})"
        # 最初の話者の各スタイルに対応するボタンを追加
        for style in speakers[0]["styles"]:  # 'styles'は各話者のスタイル辞書のリストと仮定
            style_button = discord.ui.Button(
                label=style["name"], style=discord.ButtonStyle.secondary
            )

            # Define an async function for handling button clicks
            async def handle_style_button_click(
                interaction: discord.Interaction,
                button: discord.ui.Button,
                style_id=style["id"],
            ):
                await on_style_button_click(interaction, button, style_id)

            # ボタンが押されたときの処理を定義（別の関数を定義することも検討してください）
            async def on_style_button_click(
                interaction: discord.Interaction,
                button: Button,
                style_id=style["id"],
            ):
                # スタイル変更をここで処理
                valid, speaker_name, style_name = validate_style_id(style_id)
                if not valid:
                    await interaction.response.edit_message(
                        f"スタイルID {style_id} は無効です。`/list`で有効なIDを確認し、正しいIDを入力してください。",
                        view=view,
                    )
                update_style_setting(
                    interaction.guild.id, interaction.user.id, style_id, voice_scope
                )
                speaker_character_id, speaker_display_name = get_character_info(
                    speaker_name
                )
                speaker_url = f"{DORMITORY_URL_BASE}/{speaker_character_id}/"
                await interaction.response.send_message(
                    f"{voice_scope_description[voice_scope]}が「[{speaker_display_name}]({speaker_url}) {style_name}」に更新されました。"
                )

            # Replace the existing 'style_button.callback' assignment with the following:
            style_button.callback = (
                lambda interaction, button=style_button, style_id=style[
                    "id"
                ]: asyncio.create_task(
                    handle_style_button_click(interaction, button, style_id)
                )
            )

            view.add_item(style_button)
        await interaction.response.edit_message(content=content, view=view)
    @bot.tree.command(
        name="info",
        guilds=APPROVED_GUILD_IDS,
        description="現在の読み上げ音声スコープと設定を表示します。",
    )
    async def info(interaction: discord.Interaction):
        guild_id = interaction.guild_id
        user_id = interaction.user.id
        
        # サーバーの設定を取得
        guild_settings = config_pickle.get(guild_id, {})
        text_channel_id = guild_settings.get("text_channel", "未設定")

        # 各スコープのスタイルIDを取得
        user_style_id = config_pickle.get(
            user_id, guild_settings.get("user_default", USER_DEFAULT_STYLE_ID)
        )
        announcement_style_id = guild_settings.get(
            "announcement", ANNOUNCEMENT_DEFAULT_STYLE_ID
        )
        user_default_style_id = guild_settings.get("user_default", USER_DEFAULT_STYLE_ID)

        # 各スコープのキャラクターとスタイルの詳細を取得
        user_speaker_name, user_style_name = get_style_details(user_style_id)
        user_character_id, user_display_name = get_character_info(user_speaker_name)

        announcement_speaker_name, announcement_style_name = get_style_details(
            announcement_style_id
        )
        announcement_character_id, announcement_display_name = get_character_info(
            announcement_speaker_name
        )

        user_default_speaker_name, user_default_style_name = get_style_details(
            user_default_style_id
        )
        user_default_character_id, user_default_display_name = get_character_info(
            user_default_speaker_name
        )

        # 設定の詳細を表示するメッセージを作成
        info_message = (
            f"テキストチャンネル: <#{text_channel_id}>\n"
            f"{interaction.user.display_name}さん専用の読み上げ音声: [{user_display_name}] - {user_style_name}\n"
            f"アナウンス音声: [{announcement_display_name}] - {announcement_style_name}\n"
            f"未設定ユーザーの読み上げ音声: [{user_default_display_name}] - {user_default_style_name}\n"
        )

        # ユーザーに設定の詳細を表示
        await interaction.response.send_message(info_message, ephemeral=True)

# ボイスチャンネルに接続する関数
async def connect_to_voice_channel(interaction):
    channel = interaction.user.voice.channel
    voice_client = await channel.connect(self_deaf=True)
    return voice_client


async def welcome_user(server, interaction, voice_client):
    # 接続成功時の処理
    # 接続メッセージの読み上げ
    welcome_voice = "読み上げを開始します。"

    guild_id = interaction.guild_id
    user_id = interaction.user.id  # コマンド使用者のユーザーID
    user_display_name = interaction.user.display_name  # コマンド使用者の表示名
    text_channel_id = interaction.channel_id  # コマンドを使用したテキストチャンネルID

    # サーバー設定が存在しない場合は初期化
    if guild_id not in config_pickle:
        config_pickle[guild_id] = {"text_channel": text_channel_id}
    else:
        # 既にサーバー設定が存在する場合はテキストチャンネルIDを更新
        config_pickle[guild_id]["text_channel"] = text_channel_id
    try:
        # 設定を保存
        save_style_settings()
    except IOError as e:
        logging.error(f"Failed to save settings: {e}")

    # 通知スタイルIDを取得
    announcement_style_id = config_pickle[guild_id].get(
        "announcement", ANNOUNCEMENT_DEFAULT_STYLE_ID
    )
    # ユーザーのスタイルIDを取得
    user_style_id = config_pickle.get(
        user_id, config_pickle[guild_id].get("user_default", USER_DEFAULT_STYLE_ID)
    )

    # キャラクターとスタイルの詳細を取得
    announcement_speaker_name, announcement_style_name = get_style_details(
        announcement_style_id
    )
    announcement_character_id, announcement_display_name = get_character_info(
        announcement_speaker_name
    )
    announcement_url = f"{DORMITORY_URL_BASE}/{announcement_character_id}/"
    user_speaker_name, user_style_name = get_style_details(user_style_id)
    user_character_id, user_tts_display_name = get_character_info(user_speaker_name)
    user_url = f"{DORMITORY_URL_BASE}/{user_character_id}/"

    # 歓迎メッセージを作成
    welcome_message = (
        f"アナウンス音声「[{announcement_display_name}]({announcement_url}) {announcement_style_name}」\n"
        f"{user_display_name}さん専用の読み上げ音声「[{user_tts_display_name}]({user_url}) {user_style_name}」"
    )

    # メッセージとスタイルIDをキューに追加し、読み上げ
    await server.text_to_speech(
        voice_client, welcome_voice, announcement_style_id, guild_id
    )
    await interaction.followup.send(welcome_message)
