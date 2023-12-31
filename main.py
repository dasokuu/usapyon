import discord
from discord.ext import commands
import os
from utils import handle_message, handle_voice_state_update
from voice import process_playback_queue
from bot_commands import setup_commands
from settings import BOT_PREFIX, GAME_NAME, TEST_GUILD_ID


if __name__ == "__main__":
    # Initialize bot with intents and prefix
    intents = discord.Intents.default()
    intents.messages = True
    intents.guilds = True
    intents.voice_states = True
    intents.message_content = True
    bot = commands.Bot(
        command_prefix=BOT_PREFIX, intents=intents
    )
    setup_commands(bot)

    @bot.event
    async def on_ready():
        print(f"Logged in as {bot.user.name}")
        await bot.tree.sync(guild=TEST_GUILD_ID)
        for guild in bot.guilds:
            bot.loop.create_task(process_playback_queue(str(guild.id)))

    @bot.event
    async def on_message(message):
        # ボット自身のメッセージは無視
        if message.author == bot.user:
            return

        # コマンド処理を妨げないようにする
        await bot.process_commands(message)
        await handle_message(bot, message)

    @bot.event
    async def on_voice_state_update(member, before, after):
        await handle_voice_state_update(bot, member, before, after)

    bot.run(os.getenv("VOICECHATLOIDTEST_TOKEN"))
