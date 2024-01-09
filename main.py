import asyncio
import logging
import aiohttp
import discord
from discord.ext import commands
import requests
from DiscordMessageHandler import DiscordMessageHandler
from DiscordEventHandler import DiscordEventHandler
from commands.settings import setup_settings_command
from commands.info import setup_info_command
from commands.join import setup_join_command
from commands.leave import setup_leave_command
from commands.skip import setup_skip_command
from VoiceSynthConfig import VoiceSynthConfig
from settings import APPROVED_GUILD_IDS_INT, BotSettings, TOKEN, VoiceVoxSettings
from VoiceSynthServer import VoiceSynthServer

# Improved logging format and level
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)


def is_voice_server_up(url):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return True
        else:
            return False
    except requests.ConnectionError:
        return False


async def wait_for_voice_server(url, max_attempts=10, delay=5):
    attempts = 0
    async with aiohttp.ClientSession() as session:  # 非同期HTTPセッションを作成
        while attempts < max_attempts:
            try:
                async with session.get(url) as response:  # 非同期にリクエストを送る
                    if response.status == 200:
                        print("Server is up!")
                        return True
            except aiohttp.ClientError as e:
                print(f"Attempt {attempts + 1}/{max_attempts} failed: {e}")

            print(f"Waiting for {delay} seconds...")
            await asyncio.sleep(delay)  # 非同期にウェイト
            attempts += 1
    return False


# 変更後
async def main():
    if await wait_for_voice_server(VoiceVoxSettings.SPEAKERS_URL):  # 非同期処理に変更
        intents = discord.Intents.default()
        intents.message_content = True
        bot = commands.Bot(command_prefix=BotSettings.BOT_PREFIX, intents=intents)
        voice_server = VoiceSynthServer()
        voice_config = VoiceSynthConfig()
        event_handler = DiscordEventHandler()
        message_handler = DiscordMessageHandler()

        setup_join_command(bot, event_handler, voice_server, voice_config, message_handler)
        setup_leave_command(bot, voice_server, voice_config)
        setup_settings_command(bot, voice_config)
        setup_info_command(bot, voice_config)
        setup_skip_command(bot, voice_server)

        @bot.event
        async def on_ready():
            try:
                logging.info(f"Logged in as {bot.user.name}")
                await bot.change_presence(
                    activity=discord.Game(name=BotSettings.GAME_NAME)
                )
                for guild_id in APPROVED_GUILD_IDS_INT:
                    try:
                        guild = bot.get_guild(guild_id)
                        if guild:
                            await bot.tree.sync(guild=guild)
                            bot.loop.create_task(
                                voice_server.process_playback_queue(guild.id)
                            )
                        else:
                            logging.error(f"Unable to find guild with ID: {guild_id}")
                    except Exception as e:
                        logging.error(
                            f"Error syncing commands for guild {guild_id}: {e}"
                        )
            except Exception as e:
                logging.error(f"Error occurred in on_ready: {e}")

        @bot.event
        async def on_message(message: discord.Message):
            if message.author.bot:  # これでメッセージがボットからのものかどうかをチェック
                return
            await bot.process_commands(message)
            await event_handler.handle_message(
                voice_config, voice_server, message, message_handler
            )

        @bot.event
        async def on_voice_state_update(member: discord.Member, before, after):
            await event_handler.handle_voice_state_update(
                voice_config, voice_server, bot, member, before, after, message_handler
            )

        await bot.start(TOKEN)  # bot.run()の代わりにbot.start()を使用します
        asyncio.run(voice_server.close_session())  # Bot停止時にセッションを閉じる
    else:
        print("Server did not become available in time. Exiting.")


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
