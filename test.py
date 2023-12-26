import asyncio
import discord
from discord.ext import commands
import json
import aiohttp
import io
import os
import requests
import time

last_status_update = time.time()
update_interval = 60  # ステータス更新の間隔（秒）

# ユーザーのデフォルトスタイルID
USER_DEFAULT_STYLE_ID = 3
NOTIFY_STYLE_ID = 8

MAX_MESSAGE_LENGTH = 200  # 適切な最大長を定義

# グローバル変数を追加して、現在再生中の音声を追跡します。
current_voice_client = None


async def update_status(message):
    global last_status_update
    current_time = time.time()
    if current_time - last_status_update >= update_interval:
        await bot.change_presence(activity=discord.Game(name=message))
        last_status_update = current_time


def fetch_speakers():
    """スピーカー情報を取得します。"""
    url = "http://127.0.0.1:50021/speakers"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"データの取得に失敗しました: {e}")
        return None


speakers = fetch_speakers()
speech_queue = asyncio.Queue()
headers = {"Content-Type": "application/json"}


def get_style_details(style_id, default_name="デフォルト"):
    """スタイルIDに対応するスピーカー名とスタイル名を返します。"""
    for speaker in speakers:
        for style in speaker["styles"]:
            if style["id"] == style_id:
                return (speaker["name"], style["name"])
    return (default_name, default_name)


def save_style_settings():
    """スタイル設定を保存します。"""
    with open("style_settings.json", "w") as f:
        json.dump(speaker_settings, f)


def load_style_settings():
    """スタイル設定をロードします。"""
    try:
        with open("style_settings.json", "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


speaker_settings = load_style_settings()


async def audio_query(text, speaker):
    # 音声合成用のクエリを作成します。
    query_payload = {"text": text, "speaker": speaker}
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "http://127.0.0.1:50021/audio_query", headers=headers, params=query_payload
        ) as response:
            if response.status == 200:
                return await response.json()
            elif response.status == 422:
                error_detail = await response.text()
                print(f"処理できないエンティティ: {error_detail}")
                return None


async def synthesis(speaker, query_data):
    # 音声合成を行います。
    synth_payload = {"speaker": speaker}
    headers = {"Content-Type": "application/json", "Accept": "audio/wav"}
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "http://127.0.0.1:50021/synthesis",
            headers=headers,
            params=synth_payload,
            data=json.dumps(query_data),
        ) as response:
            if response.status == 200:
                return await response.read()
            return None


async def text_to_speech(voice_client, text, speaker):
    # 既に音声を再生中であれば、待機します。
    while voice_client.is_playing():
        await asyncio.sleep(0.5)

    # 音声合成のクエリデータを取得し、音声を再生します。
    query_data = await audio_query(text, speaker)
    if query_data:
        voice_data = await synthesis(speaker, query_data)
        if voice_data:
            try:
                audio_source = discord.FFmpegPCMAudio(io.BytesIO(voice_data), pipe=True)
                voice_client.play(audio_source)
                while voice_client.is_playing():
                    await asyncio.sleep(1)
            finally:
                # エラーが発生してもリソースを確実に解放します。
                audio_source.cleanup()


async def process_speech_queue():
    global current_voice_client
    while True:
        try:
            voice_client, text, style_id = await speech_queue.get()
            current_voice_client = voice_client
            await text_to_speech(voice_client, text, style_id)
        except Exception as e:
            print(f"Error processing speech queue: {e}")
        finally:
            speech_queue.task_done()
            current_voice_client = None


intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.voice_states = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    await bot.change_presence(activity=discord.Game(name="読み上げ中 | !helpでヘルプ"))
    # バックグラウンドタスクとしてキュー処理関数を開始します。
    bot.loop.create_task(process_speech_queue())


@bot.command(name="_userdefaultstyle", help="ユーザーのデフォルトスタイルを表示または設定します。")
async def user_default_style(ctx, style_id: int = None):
    server_id = str(ctx.guild.id)

    # Ensure server settings are initialized
    if server_id not in speaker_settings:
        speaker_settings[server_id] = {"user_default": USER_DEFAULT_STYLE_ID}

    # Use get to safely access 'user_default'
    current_default = speaker_settings[server_id].get(
        "user_default", USER_DEFAULT_STYLE_ID
    )

    if style_id is not None:
        valid_style_ids = [
            style["id"] for speaker in speakers for style in speaker["styles"]
        ]
        if style_id in valid_style_ids:
            speaker_name, style_name = get_style_details(style_id)
            speaker_settings[server_id]["user_default"] = style_id
            save_style_settings()
            await ctx.send(
                f"ユーザーのデフォルトスタイルを「{speaker_name} {style_name}」(ID: {style_id})に設定しました。"
            )
        else:
            await ctx.send(f"スタイルID {style_id} は無効です。")
    else:
        # Display current default style
        user_speaker, user_default_style_name = get_style_details(
            current_default, "デフォルト"
        )
        response = f"**ユーザーのデフォルトスタイル:** {user_speaker} {user_default_style_name} (ID: {current_default})"
        await ctx.send(response)


@bot.command(name="_notifystyle", help="入退室通知のスタイルを表示または設定します。")
async def notify_style(ctx, style_id: int = None):
    server_id = str(ctx.guild.id)

    # スタイルIDが指定されている場合は設定を更新
    if style_id is not None:
        valid_style_ids = [
            style["id"] for speaker in speakers for style in speaker["styles"]
        ]
        if style_id in valid_style_ids:
            speaker_name, style_name = get_style_details(style_id)
            if server_id not in speaker_settings:
                speaker_settings[server_id] = {}
            speaker_settings[server_id]["notify"] = style_id
            save_style_settings()
            await ctx.send(
                f"入退出通知スタイルを {style_id} 「{speaker_name} {style_name}」(ID: {style_id})に設定しました。"
            )
            return
        else:
            await ctx.send(f"スタイルID {style_id} は無効です。")
            return

    # 現在のサーバースタイル設定を表示
    notify_style_id = speaker_settings.get(server_id, {}).get(
        "default", NOTIFY_STYLE_ID
    )
    notify_speaker, notify_default_name = get_style_details(notify_style_id, "デフォルト")

    response = f"**{ctx.guild.name}の通知スタイル:** {notify_speaker} {notify_default_name} (ID: {notify_style_id})\n"
    await ctx.send(response)


@bot.command(name="mystyle", help="あなたの現在のスタイルを表示または設定します。")
async def my_style(ctx, style_id: int = None):
    user_id = str(ctx.author.id)

    # スタイルIDが指定されている場合は設定を更新
    if style_id is not None:
        valid_style_ids = [
            style["id"] for speaker in speakers for style in speaker["styles"]
        ]
        if style_id in valid_style_ids:
            speaker_name, style_name = get_style_details(style_id)
            speaker_settings[user_id] = style_id
            save_style_settings()
            await ctx.send(
                f"{ctx.author.mention}さんのスタイルを「{speaker_name} {style_name}」(ID: {style_id})に設定しました。"
            )
            return
        else:
            await ctx.send(f"スタイルID {style_id} は無効です。")
            return

    # 現在のスタイル設定を表示
    user_style_id = speaker_settings.get(user_id, USER_DEFAULT_STYLE_ID)
    user_speaker, user_style_name = get_style_details(user_style_id, "デフォルト")

    response = f"**{ctx.author.display_name}さんのスタイル:** {user_speaker} {user_style_name} (ID: {user_style_id})"
    await ctx.send(response)


@bot.event
async def on_message(message):
    # ボット自身のメッセージは無視
    if message.author == bot.user:
        return

    # コマンド処理を妨げないようにする
    await bot.process_commands(message)

    # ボイスチャンネルに接続されていない、またはメッセージがコマンドの場合は無視
    voice_client = message.guild.voice_client
    if (
        not voice_client
        or not voice_client.channel
        or not message.author.voice
        or message.author.voice.channel != voice_client.channel
        or message.content.startswith("!")
    ):
        return

    if len(message.content) > MAX_MESSAGE_LENGTH:
        # テキストチャンネルに警告を送信
        await message.channel.send(
            f"申し訳ありません、メッセージが長すぎて読み上げられません！（最大 {MAX_MESSAGE_LENGTH} 文字）"
        )
        return  # このメッセージのTTS処理をスキップ

    server_id = str(message.guild.id)
    # Initialize default settings for the server if none exist
    if server_id not in speaker_settings:
        speaker_settings[server_id] = {"user_default": USER_DEFAULT_STYLE_ID}

    # Use get to safely access 'user_default' key
    user_default_style_id = speaker_settings[server_id].get(
        "user_default", USER_DEFAULT_STYLE_ID
    )

    style_id = speaker_settings.get(str(message.author.id), user_default_style_id)

    await speech_queue.put((voice_client, message.content, style_id))


@bot.event
async def on_voice_state_update(member, before, after):
    # ボット自身の状態変更は無視します。
    if member == bot.user:
        return

    # ボイスチャンネルに接続したとき
    if before.channel is None and after.channel is not None:
        message = f"{member.display_name}さんが{after.channel.name}に入室しました。"
        if member.guild.voice_client:
            # キューにボイスクライアントとメッセージを追加します。
            await speech_queue.put((member.guild.voice_client, message))

    # ボイスチャンネルから切断したとき
    elif before.channel is not None and after.channel is None:
        message = f"{member.display_name}さんが{before.channel.name}から退出しました。"
        if member.guild.voice_client:
            # キューにボイスクライアントとメッセージを追加します。
            await speech_queue.put((member.guild.voice_client, message))

    # ボイスチャンネルに誰もいなくなったら自動的に切断します。
    if after.channel is None and member.guild.voice_client:
        # ボイスチャンネルにまだ誰かいるか確認します。
        if not any(not user.bot for user in before.channel.members):
            await member.guild.voice_client.disconnect()


@bot.command(name="join", help="ボットをボイスチャンネルに接続し、読み上げを開始します。")
async def join(ctx):
    if ctx.author.voice and ctx.author.voice.channel:
        channel = ctx.author.voice.channel
        voice_client = await channel.connect()
        # 接続メッセージの読み上げ
        welcome_message = "読み上げを開始します。"

        # ctxからギルドIDを取得
        server_id = str(ctx.guild.id)

        # Use get to safely access 'notify' key
        notify_style_id = speaker_settings.get(server_id, {}).get(
            "notify", NOTIFY_STYLE_ID
        )

        # メッセージとスタイルIDをキューに追加
        await speech_queue.put((voice_client, welcome_message, notify_style_id))


@bot.command(name="leave", help="ボットをボイスチャンネルから切断します。")
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()


@bot.command(name="skip", help="現在再生中の音声をスキップします。")
async def skip(ctx):
    global current_voice_client
    if current_voice_client and current_voice_client.is_playing():
        current_voice_client.stop()
        await ctx.send("現在の読み上げをスキップしました。")
    else:
        await ctx.send("再生中の音声はありません。")


@bot.command(name="showstyles", help="利用可能なスタイルIDの一覧を表示します。")
async def show_styles(ctx):
    message_lines = []
    for speaker in speakers:
        name = speaker["name"]
        styles = ", ".join(
            [f"{style['name']} (ID: {style['id']})" for style in speaker["styles"]]
        )
        message_lines.append(f"**{name}** {styles}")
    await ctx.send("\n".join(message_lines))


if __name__ == "__main__":
    bot.run(os.getenv("DISCORD_BOT_TOKEN"))
