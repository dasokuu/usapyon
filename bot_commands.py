import logging
from commands.config import setup_config_command
from commands.info import setup_info_command
from commands.join import setup_join_command
from commands.leave import setup_leave_command
from utils import VoiceSynthConfig
from voice import VoiceSynthServer
from discord.ext import commands


logging.basicConfig(level=logging.INFO)


def setup_commands(
    server: VoiceSynthServer, bot: commands.Bot, voice_config: VoiceSynthConfig
):
    setup_join_command(bot, server, voice_config)
    setup_leave_command(bot, server, voice_config)
    setup_config_command(bot, voice_config)
    setup_info_command(bot, voice_config)
