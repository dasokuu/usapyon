import asyncio
import logging
import discord
from discord.ext import commands
from commands.config import setup_config_command
from commands.info import setup_info_command
from commands.join import setup_join_command
from commands.leave import setup_leave_command
from commands.skip import setup_skip_command
from utils import VoiceSynthConfig, wait_for_server
from settings import APPROVED_GUILD_IDS_INT, BotSettings, TOKEN, VoiceVoxSettings
from voice import VoiceSynthServer

# Improved logging format and level
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)


if __name__ == "__main__" and wait_for_server(VoiceVoxSettings.SPEAKERS_URL):
    intents = discord.Intents.default()
    intents.message_content = True
    voice_config = VoiceSynthConfig()
    bot = commands.Bot(command_prefix=BotSettings.BOT_PREFIX, intents=intents)
    server = VoiceSynthServer()

    setup_join_command(bot, server, voice_config)
    setup_leave_command(bot, server, voice_config)
    setup_config_command(bot, voice_config)
    setup_info_command(bot, voice_config)
    setup_skip_command(bot, server)
    @bot.event
    async def on_ready():
        try:
            logging.info(f"Logged in as {bot.user.name}")
            await bot.change_presence(activity=discord.Game(name=BotSettings.GAME_NAME))
            for guild_id in APPROVED_GUILD_IDS_INT:
                try:
                    guild = bot.get_guild(guild_id)
                    if guild:
                        await bot.tree.sync(guild=guild)
                        bot.loop.create_task(server.process_playback_queue(guild.id))
                    else:
                        logging.error(f"Unable to find guild with ID: {guild_id}")
                except Exception as e:
                    logging.error(f"Error syncing commands for guild {guild_id}: {e}")
        except Exception as e:
            logging.error(f"Error occurred in on_ready: {e}")

    @bot.event
    async def on_message(message):
        if message.author.bot:  # これでメッセージがボットからのものかどうかをチェック
            return
        await bot.process_commands(message)
        await voice_config.handle_message(server, message)

    @bot.event
    async def on_voice_state_update(member, before, after):
        await voice_config.handle_voice_state_update(server, bot, member, before, after)

    bot.run(TOKEN)
    asyncio.run(server.close_session())  # Bot停止時にセッションを閉じる
else:
    print("Server did not become available in time. Exiting.")
