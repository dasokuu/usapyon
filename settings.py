import os
import json
import discord

# 設定ファイルの読み込み
with open("config.json", "r") as f:
    config = json.load(f)


class BotSettings:
    BOT_PREFIX = config["bot_settings"]["bot_prefix"]
    GAME_NAME = config["bot_settings"]["game_name"]
    MAX_MESSAGE_LENGTH = config["bot_settings"]["max_message_length"]


class VoiceVoxSettings:
    ENGINE_URL = config["voicevox_settings"]["engine_url"]
    SPEAKERS_URL = config["voicevox_settings"]["speakers_url"]
    AUDIO_QUERY_URL = config["voicevox_settings"]["audio_query_url"]
    SYNTHESIS_URL = config["voicevox_settings"]["synthesis_url"]


APPROVED_GUILD_IDS_INT = config["guild_settings"]["approved_guild_ids"]
APPROVED_GUILD_OBJECTS = [
    discord.Object(id=guild_id) for guild_id in APPROVED_GUILD_IDS_INT
]

ERROR_MESSAGES = config["error_messages"]
INFO_MESSAGES = config["info_messages"]

TOKEN = os.getenv("VOICECHATLOIDTEST_TOKEN")


USER_DEFAULT_STYLE_ID = 3
ANNOUNCEMENT_DEFAULT_STYLE_ID = 8
script_dir = os.path.dirname(os.path.abspath(__file__))
CONFIG_PICKLE_FILE = os.path.join(script_dir, "config.pkl")

with open("characters_info.json", "r") as f:
    CHARACTORS_INFO = json.load(f)

DORMITORY_URL_BASE = "https://voicevox.hiroshiba.jp/dormitory"
