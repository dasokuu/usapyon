import logging
import discord
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
)

# voice_scope_description = {
#     "user": f"{user_display_name}さんのテキスト読み上げ音声",
#     "announcement": "アナウンス音声",
#     "user_default": "ユーザーデフォルトTTS音声",
# }

# # もち子さんの場合、特別なクレジット表記を使用
# if speaker_name == "もち子さん":
#     speaker_name = "もち子(cv 明日葉よもぎ)"
# コマンド設定関数
def setup_commands(server, bot):
    # ボットをボイスチャンネルから切断するコマンド
    @bot.tree.command(name="leave", guilds=APPROVED_GUILD_IDS, description="ボットをボイスチャンネルから切断します。")
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
    @bot.tree.command(name="join", guilds=APPROVED_GUILD_IDS, description="ボットをボイスチャンネルに接続し、読み上げを開始します。")
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
    announcement_speaker_name, announcement_style_name = get_style_details(announcement_style_id)
    announcement_character_id, announcement_display_name = get_character_info(announcement_speaker_name)
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
    await server.text_to_speech(voice_client, welcome_voice, announcement_style_id, guild_id)
    await interaction.followup.send(welcome_message)
