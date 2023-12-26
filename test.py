import discord
from discord.ext import commands
import json
import asyncio
import aiohttp
import re
import io
import os

async def audio_query(text, speaker, max_retry):
    query_payload = {"text": text, "speaker": speaker}
    async with aiohttp.ClientSession() as session:
        for _ in range(max_retry):
            async with session.post(f"http://localhost:50021/audio_query", params=query_payload) as response:
                if response.status == 200:
                    query_data = await response.json()
                    return query_data
                await asyncio.sleep(1)
        raise ConnectionError("リトライ回数が上限に到達しました。 audio_query")

async def synthesis(speaker, query_data, max_retry):
    synth_payload = {"speaker": speaker}
    async with aiohttp.ClientSession() as session:
        for _ in range(max_retry):
            async with session.post("http://localhost:50021/synthesis", params=synth_payload, data=json.dumps(query_data)) as response:
                if response.status == 200:
                    return await response.read()
                await asyncio.sleep(1)
        raise ConnectionError("音声エラー：リトライ回数が上限に到達しました。 synthesis")

async def text_to_speech(ctx, texts, speaker=8, max_retry=20):
    if not texts:
        await ctx.send("メッセージを指定してください。")
        return
    texts = re.split("(?<=！|。|？)", texts)
    for text in texts:
        query_data = await audio_query(text, speaker, max_retry)
        voice_data = await synthesis(speaker, query_data, max_retry)
        audio_source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(io.BytesIO(voice_data), pipe=True))
        if ctx.voice_client.is_playing():
            ctx.voice_client.stop()
        ctx.voice_client.play(audio_source)

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.voice_states = True
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')

@bot.command(name='join', help='このコマンドはボットをボイスチャンネルに接続します。')
async def join(ctx):
    if ctx.author.voice and ctx.author.voice.channel:
        channel = ctx.author.voice.channel
        await channel.connect()

@bot.command(name='leave', help='このコマンドはボットをボイスチャンネルから切断します。')
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()

@bot.command(name='speak', help='指定したテキストを読み上げます。')
async def speak(ctx, *, message=None):
    await text_to_speech(ctx, message)

if __name__ == "__main__":
    bot.run(os.getenv('DISCORD_BOT_TOKEN'))
