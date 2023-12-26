import os
import discord
import asyncio
import io
from discord.ext import commands

# グローバル変数と関数 (上記のコードから) はここに含まれます...

# Discordクライアントを初期化します。
bot = commands.Bot(command_prefix='!')

@bot.event
async def on_ready():
    print(f'ログインしました: {bot.user.name} (ID: {bot.user.id})')

@bot.command(pass_context=True, brief="!join でボットをボイスチャンネルに参加させます")
async def join(ctx):
    channel = ctx.message.author.voice.channel
    await channel.connect()

@bot.command(pass_context=True, brief="!leave でボットをボイスチャンネルから退出させます")
async def leave(ctx):
    server = ctx.message.guild.voice_client
    await server.disconnect()

@bot.command(pass_context=True, brief="!speak <メッセージ> でメッセージを読み上げます")
async def speak(ctx, *, message):
    speaker = DEFAULT_SPEAKER  # or any other speaker ID you want to use
    query_data = audio_query(message, speaker)
    voice_data = synthesis(speaker, query_data)

    # Discordの音声チャンネルで再生するためのファイルオブジェクトを作成します。
    source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(io.BytesIO(voice_data), pipe=True))
    ctx.message.guild.voice_client.play(source)

if __name__ == "__main__":
    bot.run(os.environ['DISCORD_BOT_TOKEN'])
