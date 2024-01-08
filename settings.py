import os
import json
import discord

script_dir = os.path.dirname(os.path.abspath(__file__))
config_json_file = os.path.join(script_dir, "config.json")

# 設定ファイルの読み込み
with open(config_json_file, "r") as f:
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

error_messages = config["error_messages"]
info_messages = config["info_messages"]

TOKEN = os.getenv("VOICECHATLOIDTEST_TOKEN")


USER_DEFAULT_STYLE_ID = 3
ANNOUNCEMENT_DEFAULT_STYLE_ID = 8
CONFIG_PICKLE_FILE = os.path.join(script_dir, "config.pkl")

characters_info_file = os.path.join(script_dir, "characters_info.json")

with open(characters_info_file, "r") as f:
    CHARACTORS_INFO = json.load(f)

DORMITORY_URL_BASE = "https://voicevox.hiroshiba.jp/dormitory"
