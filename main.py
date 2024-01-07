import asyncio
import logging
import discord
from discord.ext import commands
from utils import VoiceSynthConfig
from bot_commands import setup_commands
from settings import APPROVED_GUILD_IDS_INT, BOT_PREFIX, GAME_NAME, TOKEN
from voice import VoiceSynthServer


if __name__ == "__main__":
    intents = discord.Intents.default()
    intents.message_content = True
    voice_config = VoiceSynthConfig()
    bot = commands.Bot(command_prefix=BOT_PREFIX, intents=intents)
    server = VoiceSynthServer()
    setup_commands(server, bot, voice_config)

    @bot.event
    async def on_ready():
        try:
            logging.info(f"Logged in as {bot.user.name}")
            await bot.change_presence(activity=discord.Game(name=GAME_NAME))
            for guild_id in APPROVED_GUILD_IDS_INT:
                try:
                    guild = bot.get_guild(guild_id)
                    if guild:  # ギルドが見つかった場合のみ処理を行う
                        await bot.tree.sync(guild=guild)
                        bot.loop.create_task(server.process_playback_queue(guild.id))
                    else:
                        logging.error(f"Unable to find guild with ID: {guild_id}")
                except Exception as e:
                    logging.error(
                        f"Error occurred syncing commands for guild {guild_id}: {e}"
                    )
        except Exception as e:
            logging.error(f"Error occurred in on_ready: {e}")

    @bot.event
    async def on_message(message):
        if message.author == bot.user:
            return
        await bot.process_commands(message)
        await voice_config.handle_message(server, bot, message)

    @bot.event
    async def on_voice_state_update(member, before, after):
        await voice_config.handle_voice_state_update(server, bot, member, before, after)

    bot.run(TOKEN)
    asyncio.run(server.close_session())  # Bot停止時にセッションを閉じる
