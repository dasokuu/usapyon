import asyncio
import discord
from discord.ext import commands
import json
import aiohttp
import io
import os
import requests


def fetch_speakers():
    url = "http://127.0.0.1:50021/speakers"  # エンドポイントのURL
    try:
        response = requests.get(url)  # URLからデータを取得
        response.raise_for_status()  # ステータスコードをチェック
        speakers = response.json()  # JSONデータをPythonの辞書に変換
        return speakers  # 変換されたデータを返す
    except requests.RequestException as e:
        print(f"データの取得に失敗しました: {e}")
        return None


# 使用例
speakers = fetch_speakers()
if speakers:
    print("取得したスピーカー情報:", speakers)

# 非同期キューを作成します。
speech_queue = asyncio.Queue()

headers = {"Content-Type": "application/json"}


def get_style_details(style_id):
    """指定されたスタイルIDに対応するスピーカー名とスタイル名を返します。見つからない場合は ('不明', '不明') を返します。"""
    for speaker in speakers:
        for style in speaker["styles"]:
            if style["id"] == style_id:
                return (speaker["name"], style["name"])
    return ("不明", "不明")


def save_user_settings():
    with open("user_settings.json", "w") as f:
        json.dump(user_speaker_settings, f)


def load_user_settings():
    try:
        with open("user_settings.json", "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


user_speaker_settings = load_user_settings()
print("Loaded speaker settings:", user_speaker_settings)


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


async def text_to_speech(voice_client, text, speaker=8):
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
    while True:
        try:
            voice_client, text, style_id = await speech_queue.get()
            await text_to_speech(voice_client, text, style_id)
        except Exception as e:
            # エラーログを出力
            print(f"Error processing speech queue: {e}")
        finally:
            speech_queue.task_done()


intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.voice_states = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"{bot.user.name} has connected to Discord!")
    # バックグラウンドタスクとしてキュー処理関数を開始します。
    bot.loop.create_task(process_speech_queue())


@bot.command(name="style", help="現在のスタイルを表示または設定します。")
async def style(ctx, style_id: int = None):
    user_id = str(ctx.author.id)

    # スタイルIDが指定されている場合は設定を更新
    if style_id is not None:
        speaker_name, style_name = get_style_details(style_id)
        if speaker_name != "不明" and style_name != "不明":
            user_speaker_settings[user_id] = style_id
            save_user_settings()
            await ctx.send(
                f"{ctx.author.mention}さんのスタイルを「{speaker_name} {style_name}」(ID: {style_id})に設定しました。"
            )
            return
        else:
            await ctx.send(f"スタイルID {style_id} は無効です。")
            return

    # 現在のスタイル設定を表示
    user_style_id = user_speaker_settings.get(user_id, "未設定")

    user_speaker, user_style_name = (
        get_style_details(user_style_id) if user_style_id != "未設定" else ("未設定", "")
    )
    response = f"**{ctx.author.display_name}さんのスタイル:** {user_speaker} {user_style_name} (ID: {user_style_id})"
    await ctx.send(response)


@bot.command(name="defaultstyle", help="このサーバーのデフォルトのスタイルを表示または変更します。")
async def default_style(ctx, style_id: int = None):
    server_id = str(ctx.guild.id)

    # スタイルIDが指定されている場合は設定を更新
    if style_id is not None:
        valid_style_ids = [
            style["id"] for speaker in speakers for style in speaker["styles"]
        ]
        if style_id in valid_style_ids:
            if server_id not in user_speaker_settings:
                user_speaker_settings[server_id] = {}
            user_speaker_settings[server_id]["default"] = style_id
            save_user_settings()
            await ctx.send(f"このサーバーのデフォルトのスタイルIDを {style_id} に設定しました。")
            return
        else:
            await ctx.send(f"スタイルID {style_id} は無効です。")
            return

    # 現在のスタイル設定を表示
    server_default_id = user_speaker_settings.get(server_id, {}).get("default", "未設定")

    server_speaker, server_default_name = (
        get_style_details(server_default_id)
        if server_default_id != "未設定"
        else ("未設定", "")
    )

    response = f"**{ctx.guild.name}サーバーのデフォルトスタイル:** {server_speaker} {server_default_name} (ID: {server_default_id})\n"
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

    server_id = str(message.guild.id)
    default_style_id = 3  # グローバルデフォルトのスタイルID

    if (
        server_id in user_speaker_settings
        and "default" in user_speaker_settings[server_id]
    ):
        default_style_id = user_speaker_settings[server_id]["default"]

    style_id = user_speaker_settings.get(str(message.author.id), default_style_id)

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
        await text_to_speech(voice_client, welcome_message)


@bot.command(name="leave", help="ボットをボイスチャンネルから切断します。")
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()


@bot.command(name="liststyles", help="利用可能なスタイルIDの一覧を表示します。")
async def list_styles(ctx):
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
