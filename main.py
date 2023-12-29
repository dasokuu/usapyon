import discord
from discord.ext import commands
import os
from settings import USER_DEFAULT_STYLE_ID, NOTIFY_STYLE_ID, MAX_MESSAGE_LENGTH
from utils import (
    speaker_settings,
    save_style_settings,
    replace_content,
)
from voice import (
    process_playback_queue,
    text_to_speech,
    clear_playback_queue,
)
from bot_commands import setup_commands


# Initialize bot
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.voice_states = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
# Setup bot commands
setup_commands(bot)

current_voice_client = None


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    await bot.change_presence(activity=discord.Game(name="待機中 | !helpでヘルプ"))
    for guild in bot.guilds:
        bot.loop.create_task(process_playback_queue(str(guild.id)))


@bot.event
async def on_message(message):
    guild_id = str(message.guild.id)

    # ボット自身のメッセージは無視
    if message.author == bot.user:
        return

    # コマンド処理を妨げないようにする
    await bot.process_commands(message)

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
        speaker_settings[guild_id] = {"user_default": USER_DEFAULT_STYLE_ID}

    # Use get to safely access 'user_default' key
    user_default_style_id = speaker_settings[guild_id].get(
        "user_default", USER_DEFAULT_STYLE_ID
    )

    style_id = speaker_settings.get(str(message.author.id), user_default_style_id)

    # メッセージ内容を置換
    message_content = await replace_content(message.content, message)
    # テキストメッセージがある場合、それに対する音声合成を行います。
    if message_content.strip():
        await text_to_speech(voice_client, message_content, style_id, guild_id)

    # 添付ファイルがある場合、「ファイルが投稿されました」というメッセージに対する音声合成を行います。
    if message.attachments:
        file_message = "ファイルが投稿されました。"
        await text_to_speech(voice_client, file_message, style_id, guild_id)


@bot.event
async def on_voice_state_update(member, before, after):
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
            "notify", NOTIFY_STYLE_ID
        )
        await text_to_speech(voice_client, message, notify_style_id, guild_id)

    # ボイスチャンネルから切断したとき
    elif (
        before.channel == voice_client.channel and after.channel != voice_client.channel
    ):
        message = f"{member.display_name}さんが退出しました。"
        notify_style_id = speaker_settings.get(str(member.guild.id), {}).get(
            "notify", NOTIFY_STYLE_ID
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


if __name__ == "__main__":
    bot.run(os.getenv("VOICECHATLOID_TOKEN"))
