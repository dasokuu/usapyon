import asyncio
import discord
from discord.ext import commands
import json
import aiohttp
import re
import io
import os

# 非同期キューを作成します。
speech_queue = asyncio.Queue()

headers = {'Content-Type': 'application/json'}

async def audio_query(text, speaker):
    # 音声合成用のクエリを作成します。
    query_payload = {"text": text, "speaker": speaker}
    async with aiohttp.ClientSession() as session:
        async with session.post("http://localhost:50021/audio_query", headers=headers, params=query_payload) as response:
            if response.status == 200:
                return await response.json()
            elif response.status == 422:
                error_detail = await response.text()
                print(f"処理できないエンティティ: {error_detail}")
                return None

async def synthesis(speaker, query_data):
    # 音声合成を行います。
    synth_payload = {"speaker": speaker}
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'audio/wav'
    }
    async with aiohttp.ClientSession() as session:
        async with session.post("http://localhost:50021/synthesis", headers=headers, params=synth_payload, data=json.dumps(query_data)) as response:
            if response.status == 200:
                return await response.read()
            return None

async def text_to_speech(voice_client, text, speaker=8):
    query_data = await audio_query(text, speaker)
    if query_data:
        voice_data = await synthesis(speaker, query_data)
        if voice_data:
            audio_source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(io.BytesIO(voice_data), pipe=True))
            if voice_client.is_playing():
                voice_client.stop()
            voice_client.play(audio_source)

async def process_speech_queue():
    while True:
        # キューから次のアイテム（ボイスクライアントとテキスト）を待ちます。
        voice_client, text = await speech_queue.get()
        await text_to_speech(voice_client, text)
        speech_queue.task_done()  # タスク完了をマークします。



intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.voice_states = True
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')
    # バックグラウンドタスクとしてキュー処理関数を開始します。
    bot.loop.create_task(process_speech_queue())

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # ボットがボイスチャンネルに接続しているか確認します。
    voice_client = message.guild.voice_client
    if voice_client and voice_client.channel and message.author.voice and message.author.voice.channel == voice_client.channel:
        await text_to_speech(voice_client, message.content)
    
    await bot.process_commands(message)


@bot.command(name='join', help='ボットをボイスチャンネルに接続します。')
async def join(ctx):
    if ctx.author.voice and ctx.author.voice.channel:
        channel = ctx.author.voice.channel
        await channel.connect()

@bot.command(name='leave', help='ボットをボイスチャンネルから切断します。')
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()

@bot.command(name='speak', help='Reads the specified text aloud.')
async def speak(ctx, *, message=None):
    if message:
        # キューにボイスクライアントとメッセージを追加します。
        await speech_queue.put((ctx.voice_client, message))

if __name__ == "__main__":
    bot.run(os.getenv('DISCORD_BOT_TOKEN'))
