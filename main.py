import asyncio
import logging
import aiohttp
import discord
from discord.ext import commands
from SpeechTextFormatter import SpeechTextFormatter
from VoiceSynthEventProcessor import VoiceSynthEventProcessor
from commands.settings import setup_settings_command
from commands.info import setup_info_command
from commands.join import setup_join_command
from commands.leave import setup_leave_command
from commands.skip import setup_skip_command
from VoiceSynthConfig import VoiceSynthConfig
from settings import APPROVED_GUILD_IDS_INT, BotSettings, TOKEN, VOICEVOXSettings
from VoiceSynthService import VoiceSynthService

# Improved logging format and level
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)


async def is_synth_service_up(url):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                return response.status == 200
        except Exception as e:
            logging.error(f"Error checking service status: {e}")
            return False


async def wait_for_synth_service(url, max_attempts=10, delay=5):
    attempts = 0
    while attempts < max_attempts:
        if await is_synth_service_up(url):
            print("Server is up!")
            return True
        await asyncio.sleep(delay)
        attempts += 1
    return False


# 変更後
async def main():
    try:
        if await wait_for_synth_service(VOICEVOXSettings.SPEAKERS_URL):  # 非同期処理に変更
            intents = discord.Intents.default()
            intents.message_content = True
            bot = commands.Bot(
                command_prefix=BotSettings.BOT_PREFIX, intents=intents)
            synth_service = VoiceSynthService()
            await synth_service.start()
            synth_config = VoiceSynthConfig()
            await synth_config.async_init()
            synth_event_processor = VoiceSynthEventProcessor()
            text_processor = SpeechTextFormatter()

            setup_join_command(bot, synth_service,
                               synth_config, text_processor)
            setup_leave_command(bot, synth_service, synth_config)
            setup_settings_command(bot, synth_config)
            setup_info_command(bot, synth_config)
            setup_skip_command(bot, synth_service)

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
                            await bot.tree.sync()
                            if guild:
                                bot.loop.create_task(
                                    synth_service.process_playback_queue(
                                        guild.id)
                                )
                            else:
                                logging.error(
                                    f"Unable to find guild with ID: {guild_id}")
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
                await synth_event_processor.handle_message(
                    synth_config, synth_service, message, text_processor
                )

            @bot.event
            async def on_voice_state_update(member: discord.Member, before, after):
                await synth_event_processor.handle_voice_state_update(
                    synth_config, synth_service, bot, member, before, after, text_processor
                )

            await bot.start(TOKEN)  # bot.run()の代わりにbot.start()を使用します
            await synth_service.close()
        else:
            print("Server did not become available in time. Exiting.")
    except Exception as e:
        logging.error(f"Unexpected error in main function: {e}", exc_info=True)
        print("アプリケーションの起動中にエラーが発生しました。詳細はログを確認してください。")

if __name__ == "__main__":
    asyncio.run(main())
