import discord
from discord.ext import commands
import json
import aiohttp
import re
import io
import os


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

async def text_to_speech(ctx, texts, speaker=8):
    if not texts:
        await ctx.send("読み上げるメッセージを指定してください。")
        return
    texts = re.split("(?<=！|。|？)", texts)
    for text in texts:
        query_data = await audio_query(text, speaker)
        if query_data:
            voice_data = await synthesis(speaker, query_data)
            if voice_data:
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
    print(f'{bot.user.name} がDiscordに接続しました!')

@bot.event
async def on_message(message):
    # ボット自身のメッセージには反応しないようにします。
    if message.author == bot.user:
        return
    
    # メッセージがボットの現在のボイスチャンネルと同じチャンネルであることを確認します。
    if message.guild.voice_client and message.guild.voice_client.channel == message.author.voice.channel:
        await text_to_speech(message.channel, message.content)
    
    # 他のコマンドも正しく動作するようにします。
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

@bot.command(name='speak', help='指定されたテキストを読み上げます。')
async def speak(ctx, *, message=None):
    await text_to_speech(ctx, message)

if __name__ == "__main__":
    bot.run(os.getenv('DISCORD_BOT_TOKEN'))
