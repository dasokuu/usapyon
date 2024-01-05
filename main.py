import logging
import discord
from discord.ext import commands
import os
from utils import handle_message, handle_voice_state_update
from bot_commands import setup_commands
from settings import APPROVED_GUILD_IDS, BOT_PREFIX, GAME_NAME
from voice import VoiceSynthServer


if __name__ == "__main__":
    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix=BOT_PREFIX, intents=intents)
    server = VoiceSynthServer()
    setup_commands(server, bot)

    @bot.event
    async def on_ready():
        try:
            logging.info(f"Logged in as {bot.user.name}")
            await bot.change_presence(activity=discord.Game(name=GAME_NAME))
            for guild in APPROVED_GUILD_IDS:
                await bot.tree.sync(guild=guild)
            for guild in bot.guilds:
                bot.loop.create_task(server.process_playback_queue(str(guild.id)))
        except Exception as e:
            logging.error(f"Error occurred: {e}")

    @bot.event
    async def on_message(message):
        if message.author == bot.user:
            return
        await bot.process_commands(message)
        await handle_message(server, bot, message)

    @bot.event
    async def on_voice_state_update(member, before, after):
        await handle_voice_state_update(server, bot, member, before, after)

    bot.run(os.getenv("VOICECHATLOIDTEST_TOKEN"))
