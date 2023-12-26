import discord
from discord.ext import commands

# Discordクライアントの設定
intents = discord.Intents.default()
intents.messages = True  # メッセージイベントを受け取る
intents.guilds = True  # サーバー（ギルド）関連のイベントを受け取る
intents.voice_states = True  # ボイスチャンネル状態の変更を受け取る

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')

@bot.command(name='join', help='このコマンドはボットをボイスチャンネルに接続します。')
async def join(ctx):
    if ctx.author.voice and ctx.author.voice.channel:
        channel = ctx.author.voice.channel
        try:
            await channel.connect()
            await ctx.send(f"{channel} に接続しました。")
        except Exception as e:
            await ctx.send(f"接続中にエラーが発生しました: {e}")
    else:
        await ctx.send("先にボイスチャンネルに参加してください。")

if __name__ == "__main__":
    bot.run('YOUR_DISCORD_BOT_TOKEN')
