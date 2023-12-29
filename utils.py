import requests
import json
import jaconv
import re
import discord
from settings import (
    USER_DEFAULT_STYLE_ID,
    NOTIFY_DEFAULT_STYLE_ID,
    MAX_MESSAGE_LENGTH,
    SPEAKERS_URL,
    STYLE_SETTINGS_FILE,
)
from voice import text_to_speech, clear_playback_queue

current_voice_client = None


def validate_style_id(style_id):
    valid_style_ids = [
        style["id"] for speaker in speakers for style in speaker["styles"]
    ]
    if style_id in valid_style_ids:
        speaker_name, style_name = get_style_details(style_id)
        return True, speaker_name, style_name
    return False, None, None


def fetch_speakers():
    try:
        response = requests.get(SPEAKERS_URL)
        response.raise_for_status()
        return response.json()
    except requests.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
    except Exception as err:
        print(f"An error occurred: {err}")
    return None


def get_style_details(style_id, default_name="デフォルト"):
    """スタイルIDに対応するスピーカー名とスタイル名を返します。"""
    for speaker in speakers:
        for style in speaker["styles"]:
            if style["id"] == style_id:
                return (speaker["name"], style["name"])
    return (default_name, default_name)


def save_style_settings():
    """スタイル設定を保存します。"""
    with open(STYLE_SETTINGS_FILE, "w") as f:
        json.dump(speaker_settings, f)


def load_style_settings():
    """スタイル設定をロードします。"""
    try:
        with open(STYLE_SETTINGS_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


async def replace_content(text, message):
    # ユーザーメンションを検出する正規表現パターン
    user_mention_pattern = re.compile(r"<@!?(\d+)>")
    # ロールメンションを検出する正規表現パターン
    role_mention_pattern = re.compile(r"<@&(\d+)>")
    # チャンネルを検出する正規表現パターン
    channel_pattern = re.compile(r"<#(\d+)>")
    # カスタム絵文字を検出する正規表現パターン
    custom_emoji_pattern = re.compile(r"<:(\w*):\d*>")
    # URLを検出する正規表現パターン
    url_pattern = re.compile(r"https?://\S+")

    def replace_user_mention(match):
        user_id = int(match.group(1))
        user = message.guild.get_member(user_id)
        return user.display_name + "さん" if user else match.group(0)

    def replace_role_mention(match):
        role_id = int(match.group(1))
        role = discord.utils.get(message.guild.roles, id=role_id)
        return role.name + "役職" if role else match.group(0)

    def replace_channel_mention(match):
        channel_id = int(match.group(1))
        channel = message.guild.get_channel(channel_id)
        return channel.name + "チャンネル" if channel else match.group(0)

    def replace_emoji_name_to_kana(match):
        emoji_name = match.group(1)
        return jaconv.alphabet2kana(emoji_name) + " "

    # ユーザーメンションを「○○さん」に置き換え
    text = user_mention_pattern.sub(replace_user_mention, text)
    # ロールメンションを「○○役職」に置き換え
    text = role_mention_pattern.sub(replace_role_mention, text)
    text = channel_pattern.sub(replace_channel_mention, text)
    text = custom_emoji_pattern.sub(replace_emoji_name_to_kana, text)
    text = url_pattern.sub("URL省略", text)

    return text


async def handle_message(bot, message):
    guild_id = str(message.guild.id)
    # ボイスチャンネルに接続されていない、またはメッセージがコマンドの場合は無視
    voice_client = message.guild.voice_client
    # 設定されたテキストチャンネルIDを取得（存在しない場合はNone）
    allowed_text_channel_id = speaker_settings.get(guild_id, {}).get("text_channel")
    if (
        not voice_client
        or not voice_client.channel
        or not message.author.voice
        or message.author.voice.channel != voice_client.channel
        or message.content.startswith("!")
        or str(message.channel.id)
        != allowed_text_channel_id  # メッセージが指定されたテキストチャンネルからでなければ無視
    ):
        return

    if len(message.content) > MAX_MESSAGE_LENGTH:
        # テキストチャンネルに警告を送信
        await message.channel.send(
            f"申し訳ありません、メッセージが長すぎて読み上げられません！（最大 {MAX_MESSAGE_LENGTH} 文字）"
        )
        return  # このメッセージのTTS処理をスキップ

    guild_id = str(message.guild.id)
    # Initialize default settings for the server if none exist
    if guild_id not in speaker_settings:
        speaker_settings[guild_id] = {"default": USER_DEFAULT_STYLE_ID}

    # Use get to safely access 'default' key
    default_style_id = speaker_settings[guild_id].get(
        "default", USER_DEFAULT_STYLE_ID
    )

    style_id = speaker_settings.get(str(message.author.id), default_style_id)

    # メッセージ内容を置換
    message_content = await replace_content(message.content, message)
    # テキストメッセージがある場合、それに対する音声合成を行います。
    if message_content.strip():
        await text_to_speech(voice_client, message_content, style_id, guild_id)

    # 添付ファイルがある場合、「ファイルを投稿しました」というメッセージに対する音声合成を行います。
    if message.attachments:
        file_message = "ファイルを投稿しました。"
        await text_to_speech(voice_client, file_message, style_id, guild_id)


async def handle_voice_state_update(bot, member, before, after):
    guild_id = str(member.guild.id)
    # ボット自身の状態変更を無視
    if member == bot.user:
        return

    # ボットが接続しているボイスチャンネルを取得
    voice_client = member.guild.voice_client

    # ボットがボイスチャンネルに接続していなければ何もしない
    if not voice_client or not voice_client.channel:
        return

    # ボイスチャンネルに接続したとき
    if before.channel != voice_client.channel and after.channel == voice_client.channel:
        message = f"{member.display_name}さんが入室しました。"
        notify_style_id = speaker_settings.get(str(member.guild.id), {}).get(
            "notify", NOTIFY_DEFAULT_STYLE_ID
        )
        await text_to_speech(voice_client, message, notify_style_id, guild_id)

    # ボイスチャンネルから切断したとき
    elif (
        before.channel == voice_client.channel and after.channel != voice_client.channel
    ):
        message = f"{member.display_name}さんが退室しました。"
        notify_style_id = speaker_settings.get(str(member.guild.id), {}).get(
            "notify", NOTIFY_DEFAULT_STYLE_ID
        )
        await text_to_speech(voice_client, message, notify_style_id, guild_id)

    # ボイスチャンネルに誰もいなくなったら自動的に切断します。
    if after.channel is None and member.guild.voice_client:
        # ボイスチャンネルにまだ誰かいるか確認します。
        if not any(not user.bot for user in before.channel.members):
            # 現在の読み上げを停止する
            if current_voice_client and current_voice_client.is_playing():
                current_voice_client.stop()

            # キューをクリアする
            await clear_playback_queue(guild_id)
            if (
                guild_id in speaker_settings
                and "text_channel" in speaker_settings[guild_id]
            ):
                # テキストチャンネルIDの設定をクリア
                del speaker_settings[guild_id]["text_channel"]
                save_style_settings()  # 変更を保存
                print(f"テキストチャンネルの設定をクリアしました: サーバーID {guild_id}")
            await member.guild.voice_client.disconnect()


# Initialize global variables
guild_playback_queues = {}
speakers = fetch_speakers()  # URL is now from settings
speaker_settings = load_style_settings()
