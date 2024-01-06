import logging
import discord
from discord.ui import Button, View
from settings import (
    ANNOUNCEMENT_URL_BASE,
    APPROVED_GUILD_IDS,
    ERROR_MESSAGES,
    USER_DEFAULT_STYLE_ID,
    ANNOUNCEMENT_DEFAULT_STYLE_ID,
)
from utils import (
    get_character_info,
    speaker_settings,
    save_style_settings,
    get_style_details,
    speakers,
)


# # もち子さんの場合、特別なクレジット表記を使用
# if speaker_name == "もち子さん":
#     speaker_name = "もち子(cv 明日葉よもぎ)"
# コマンド設定関数
def setup_commands(server, bot):
    # ボットをボイスチャンネルから切断するコマンド
    @bot.tree.command(
        name="leave", guilds=APPROVED_GUILD_IDS, description="ボットをボイスチャンネルから切断します。"
    )
    async def leave(interaction: discord.Interaction):
        # ボイスクライアントが存在するか確認
        if interaction.guild.voice_client:
            guild_id = str(interaction.guild_id)
            await server.clear_playback_queue(guild_id)  # キューをクリア
            if "text_channel" in speaker_settings.get(guild_id, {}):
                del speaker_settings[guild_id]["text_channel"]
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
        name="set_voice_scope", guilds=APPROVED_GUILD_IDS, description="音声スコープを設定します。"
    )
    async def set_voice_scope(interaction: discord.Interaction):
        voice_scope_description = {
            "user": f"{interaction.user.display_name}さんのテキスト読み上げ音声",
            "announcement": "アナウンス音声",
            "user_default": "ユーザーデフォルトテキスト読み上げ音声",
        }
        # ボタンとビューの設定
        view = View()
        for scope, label in voice_scope_description.items():
            # 各スコープに対応するボタンを作成
            button = Button(style=discord.ButtonStyle.primary, label=label)

            # ボタンが押されたときの処理を定義
            async def on_button_click(
                interaction: discord.Interaction, button: Button, scope=scope
            ):
                # ここで話者のページングを開始
                await initiate_speaker_paging(interaction, scope)

            # on_button_click関数をボタンのコールバックとして設定
            button.callback = lambda interaction, button=button: on_button_click(
                interaction, button, scope
            )

            # ビューにボタンを追加
            view.add_item(button)

        # ユーザーにボタンを表示
        await interaction.response.send_message(
            "音声スコープを選んでください：", view=view, ephemeral=True
        )
    class PagingView(discord.ui.View):
        def __init__(self, speakers, scope):
            super().__init__()
            self.speakers = speakers
            self.scope = scope
            self.current_page = 0

        @discord.ui.button(label="Previous", style=discord.ButtonStyle.blurple)
        async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            # Correctly using 'interaction' to navigate pages
            if self.current_page > 0:
                self.current_page -= 1
                await self.update_speaker_list(interaction)

        @discord.ui.button(label="Next", style=discord.ButtonStyle.blurple)
        async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            # Correctly using 'interaction' to navigate pages
            if self.current_page < len(self.speakers) - 1:
                self.current_page += 1
                await self.update_speaker_list(interaction)

        async def update_speaker_list(self, interaction: discord.Interaction):
            # Properly using 'interaction' to edit the message
            speaker_name = self.speakers[self.current_page]["name"]
            content = f"Page {self.current_page + 1} of {len(self.speakers)}\n"
            speaker_character_id, speaker_display_name = get_character_info(speaker_name)
            speaker_url = f"{ANNOUNCEMENT_URL_BASE}/{speaker_character_id}/"

            # 歓迎メッセージを作成
            content += (
                f"[{speaker_display_name}]({speaker_url})"
            )
            # Remove old style buttons before adding new ones
            self.clear_items()

            # Add navigation buttons back
            self.add_item(self.previous_button)
            self.add_item(self.next_button)

            # Loop through each style of the current speaker and add a button for it
            for style in self.speakers[self.current_page]['styles']:
                style_button = discord.ui.Button(label=style['name'], style=discord.ButtonStyle.secondary)
                # Define what happens when the button is clicked
                async def on_style_button_click(interaction: discord.Interaction, button: discord.ui.Button):
                    # Handle style change here
                    pass
                style_button.callback = on_style_button_click
                self.add_item(style_button)
            await interaction.response.edit_message(content=content, view=self)


    async def initiate_speaker_paging(interaction: discord.Interaction, scope):

        # 初期ページングビューを作成
        view = PagingView(speakers, scope)
        # 最初の話者を表示
        first_speaker = speakers[0] if speakers else "No speakers available"
        content = f"Page 1 of {len(speakers)}\n"
        speaker_character_id, speaker_display_name = get_character_info(first_speaker["name"])
        speaker_url = f"{ANNOUNCEMENT_URL_BASE}/{speaker_character_id}/"

        # 歓迎メッセージを作成
        content += (
            f"[{speaker_display_name}]({speaker_url})"
        )
        # Loop through each style of the first speaker and add a button for it
        for style in speakers[0]['styles']:  # Assuming 'styles' is a list of style dicts for each speaker
            style_button = discord.ui.Button(label=style['name'], style=discord.ButtonStyle.secondary)
            # Define what happens when the button is clicked (You might want to define a separate function)
            async def on_style_button_click(interaction: discord.Interaction, button: discord.ui.Button):
                # Handle style change here
                pass
            style_button.callback = on_style_button_click
            view.add_item(style_button)
        await interaction.response.edit_message(content=content, view=view)


# ボイスチャンネルに接続する関数
async def connect_to_voice_channel(interaction):
    channel = interaction.user.voice.channel
    voice_client = await channel.connect(self_deaf=True)
    return voice_client


async def welcome_user(server, interaction, voice_client):
    # 接続成功時の処理
    # 接続メッセージの読み上げ
    welcome_voice = "読み上げを開始します。"

    guild_id = str(interaction.guild_id)
    user_id = str(interaction.user.id)  # コマンド使用者のユーザーID
    user_display_name = interaction.user.display_name  # コマンド使用者の表示名
    text_channel_id = str(interaction.channel_id)  # コマンドを使用したテキストチャンネルID

    # サーバー設定が存在しない場合は初期化
    if guild_id not in speaker_settings:
        speaker_settings[guild_id] = {"text_channel": text_channel_id}
    else:
        # 既にサーバー設定が存在する場合はテキストチャンネルIDを更新
        speaker_settings[guild_id]["text_channel"] = text_channel_id
    try:
        # 設定を保存
        save_style_settings()
    except IOError as e:
        logging.error(f"Failed to save settings: {e}")

    # 通知スタイルIDを取得
    announcement_style_id = speaker_settings.get(guild_id, {}).get(
        "announcement", ANNOUNCEMENT_DEFAULT_STYLE_ID
    )
    # ユーザーのスタイルIDを取得
    user_style_id = speaker_settings.get(
        user_id,
        speaker_settings[guild_id].get("user_default", USER_DEFAULT_STYLE_ID),
    )

    # キャラクターとスタイルの詳細を取得
    announcement_speaker_name, announcement_style_name = get_style_details(
        announcement_style_id
    )
    announcement_character_id, announcement_display_name = get_character_info(
        announcement_speaker_name
    )
    announcement_url = f"{ANNOUNCEMENT_URL_BASE}/{announcement_character_id}/"
    user_speaker_name, user_style_name = get_style_details(user_style_id)
    user_character_id, user_tts_display_name = get_character_info(user_speaker_name)
    user_url = f"{ANNOUNCEMENT_URL_BASE}/{user_character_id}/"

    # 歓迎メッセージを作成
    welcome_message = (
        f"アナウンス音声「[{announcement_display_name}]({announcement_url}) {announcement_style_name}」\n"
        f"{user_display_name}さんのテキスト読み上げ音声「[{user_tts_display_name}]({user_url}) {user_style_name}」"
    )

    # メッセージとスタイルIDをキューに追加し、読み上げ
    await server.text_to_speech(
        voice_client, welcome_voice, announcement_style_id, guild_id
    )
    await interaction.followup.send(welcome_message)
