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

# https://raw.githubusercontent.com/VOICEVOX/voicevox_blog/master/src/constants.ts
CHARACTORS_INFO = {
    "四国めたん": "shikoku_metan",
    "ずんだもん": "zundamon",
    "春日部つむぎ": "kasukabe_tsumugi",
    "雨晴はう": "amehare_hau",
    "波音リツ": "namine_ritsu",
    "玄野武宏": "kurono_takehiro",
    "白上虎太郎": "shirakami_kotarou",
    "青山龍星": "aoyama_ryusei",
    "冥鳴ひまり": "meimei_himari",
    "九州そら": "kyushu_sora",
    "もち子さん": "mochikosan",
    "剣崎雌雄": "kenzaki_mesuo",
    "WhiteCUL": "white_cul",
    "後鬼": "goki",
    "No.7": "number_seven",
    "ちび式じい": "chibishikiji",
    "櫻歌ミコ": "ouka_miko",
    "小夜/SAYO": "sayo",
    "ナースロボ＿タイプＴ": "nurserobo_typet",
    "†聖騎士 紅桜†": "horinaito_benizakura",
    "雀松朱司": "wakamatsu_akashi",
    "麒ヶ島宗麟": "kigashima_sourin",
    "春歌ナナ": "haruka_nana",
    "猫使アル": "nekotsuka_aru",
    "猫使ビィ": "nekotsuka_bi",
    "中国うさぎ": "chugoku_usagi",
    "栗田まろん": "kurita_maron",
    "あいえるたん": "aierutan",
    "満別花丸": "manbetsu_hanamaru",
    "琴詠ニア": "kotoyomi_nia",
}

DORMITORY_URL_BASE = "https://voicevox.hiroshiba.jp/dormitory"
