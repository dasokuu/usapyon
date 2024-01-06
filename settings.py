import discord

BOT_PREFIX = "!"
GAME_NAME = f"/helpでヘルプを表示。/listでIDを確認。/voice_configで音声変更。"
USER_DEFAULT_STYLE_ID = 3
ANNOUNCEMENT_DEFAULT_STYLE_ID = 8
MAX_MESSAGE_LENGTH = 200
VOICEVOX_ENGINE_URL = "http://127.0.0.1:50021/"
SPEAKERS_URL = VOICEVOX_ENGINE_URL + "speakers"
AUDIO_QUERY_URL = VOICEVOX_ENGINE_URL + "audio_query"
SYNTHESIS_URL = VOICEVOX_ENGINE_URL + "synthesis"
CONFIG_PICKLE_FILE = "config.pkl"
TEST_GUILD_ID = discord.Object(id="1189256965172514836")
APPROVED_GUILD_IDS = [
    discord.Object(id="1189256965172514836"),  # くーさーばー１
    discord.Object(id="1190673139072516096"),  # くーさーばー２
    # discord.Object(id="1129051248574869617"),  # めぞんどとわいらいと
    # discord.Object(id="1156189448288079882"),  # ばろ
    # 他の承認されたギルドIDを追加する場合は、以下のようにリストに追加します。
    # discord.Object(id="他のギルドID"),
    # ...
]
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
EMOJI_JA_URL = "https://raw.githubusercontent.com/yagays/emoji-ja/master/data/emoji_ja.json"

DORMITORY_URL_BASE = "https://voicevox.hiroshiba.jp/dormitory"

ITEMS_PER_PAGE = 10  # 1ページあたりのアイテム数
# エラーメッセージを一元管理
ERROR_MESSAGES = {
    "connection": "ボイスチャンネルに接続できませんでした。ユーザーがボイスチャンネルにいることを確認してください。",
    "invalid_style": "選択したスタイルIDが無効です。",
}