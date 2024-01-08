import asyncio
import logging
import pickle
import requests
import jaconv
import re
import discord
from settings import (
    CHARACTORS_INFO,
    ERROR_MESSAGES,
    USER_DEFAULT_STYLE_ID,
    ANNOUNCEMENT_DEFAULT_STYLE_ID,
    BotSettings,
    VoiceVoxSettings,
    CONFIG_PICKLE_FILE,
)
import emoji
import alkana


from voice import VoiceSynthServer  # 絵文字の判定を行うためのライブラリ


class VoiceSynthConfig:
    def __init__(self):
        self.speakers = fetch_json(VoiceVoxSettings.SPEAKERS_URL)
        self.config_pickle = load_style_settings()

    def validate_style_id(self, style_id):
        valid_style_ids = [
            style["id"] for speaker in self.speakers for style in speaker["styles"]
        ]
        if style_id in valid_style_ids:
            speaker_name, style_name = self.get_style_details(style_id)
            return True, speaker_name, style_name
        return False, None, None

    def get_style_details(self, style_id, default_name="デフォルト"):
        """スタイルIDに対応するスピーカー名とスタイル名を返します。"""
        for speaker in self.speakers:
            for style in speaker["styles"]:
                if style["id"] == style_id:
                    speaker_name = speaker["name"]
                    return (speaker_name, style["name"])
        return (default_name, default_name)

    def save_style_settings(self):
        """スタイル設定を保存します。"""
        with open(CONFIG_PICKLE_FILE, "wb") as f:  # wbモードで開く
            pickle.dump(self.config_pickle, f)  # config_pickleをpickleで保存

    async def handle_voice_state_update(
        self, server: VoiceSynthServer, bot, member, before, after
    ):
        guild_id = member.guild.id
        # ボット自身の状態変更を無視
        if member == bot.user:
            return

        # ボットが接続しているボイスチャンネルを取得
        voice_client = member.guild.voice_client

        # ボットがボイスチャンネルに接続していなければ何もしない
        if not voice_client or not voice_client.channel:
            return

        if (
            before.channel != voice_client.channel
            and after.channel == voice_client.channel
        ):
            announcement_voice = f"{member.display_name}さんが入室しました。"
            # ユーザーのスタイルIDを取得
            user_style_id = self.config_pickle.get(
                member.id,
                self.config_pickle.get(guild_id, {}).get(
                    "user_default", USER_DEFAULT_STYLE_ID
                ),
            )
            user_speaker_name, user_style_name = self.get_style_details(user_style_id)
            user_character_id, user_display_name = get_character_info(user_speaker_name)
            # user_url = f"{DORMITORY_URL_BASE}//{user_character_id}/"
            announcement_message = f"「{member.display_name}」さんの読み上げ音声: [{user_display_name}] - {user_style_name}"

            # テキストチャンネルを取得してメッセージを送信
            text_channel_id = self.config_pickle.get(guild_id, {}).get("text_channel")
            if text_channel_id:
                text_channel = bot.get_channel(text_channel_id)
                if text_channel:
                    await text_channel.send(announcement_message)
            announcement_style_id = self.config_pickle.get(guild_id, {}).get(
                "announcement", ANNOUNCEMENT_DEFAULT_STYLE_ID
            )
            await server.text_to_speech(
                voice_client, announcement_voice, announcement_style_id, guild_id
            )

        # ボイスチャンネルから切断したとき
        elif (
            before.channel == voice_client.channel
            and after.channel != voice_client.channel
        ):
            announcement_voice = f"{member.display_name}さんが退室しました。"
            announcement_style_id = self.config_pickle.get(member.guild.id, {}).get(
                "announcement", ANNOUNCEMENT_DEFAULT_STYLE_ID
            )
            await server.text_to_speech(
                voice_client, announcement_voice, announcement_style_id, guild_id
            )

        # ボイスチャンネルに誰もいなくなったら自動的に切断します。
        if after.channel is None and member.guild.voice_client:
            # ボイスチャンネルにまだ誰かいるか確認します。
            if not any(not user.bot for user in before.channel.members):
                # キューをクリアする
                await server.clear_playback_queue(guild_id)
                if (
                    guild_id in self.config_pickle
                    and "text_channel" in self.config_pickle.get(guild_id, {})
                ):
                    # テキストチャンネルIDの設定をクリア
                    del self.config_pickle[guild_id]["text_channel"]
                    self.save_style_settings()  # 変更を保存
                    logging.info(f"テキストチャンネルの設定をクリアしました: サーバーID {guild_id}")
                await member.guild.voice_client.disconnect()

    async def handle_message(self, server: VoiceSynthServer, message):
        guild_id = message.guild.id
        try:
            logging.info(f"Handling message: {message.content}")

            if not isinstance(message.content, str):
                logging.error(f"Message content is not a string: {message.content}")
                return

            message_content = await replace_content(message.content, message)

            if not isinstance(message_content, str):
                logging.error(
                    f"Replaced message content is not a string: {message_content}"
                )
                return

            if message_content:
                await server.text_to_speech(
                    message.guild.voice_client,
                    message_content,
                    self.get_style_id(message.author.id, guild_id),
                    guild_id,
                )
            if message.attachments:
                await self.announce_file_post(server, message)
        except Exception as e:
            logging.error(f"Error in handle_message: {e}")

    async def announce_file_post(
        self, server: VoiceSynthServer, message: discord.Message
    ):
        """ファイル投稿をアナウンスします。"""
        file_message = "ファイルが投稿されました。"
        guild_id = message.guild.id
        announcement_style_id = self.config_pickle.get(message.guild.id, {}).get(
            "announcement", ANNOUNCEMENT_DEFAULT_STYLE_ID
        )
        await server.text_to_speech(
            message.guild.voice_client, file_message, announcement_style_id, guild_id
        )

    def should_process_message(self, message: discord.Message, guild_id):
        """メッセージが処理対象かどうかを判断します。"""
        voice_client = message.guild.voice_client
        allowed_text_channel_id = self.config_pickle.get(guild_id, {}).get(
            "text_channel"
        )
        return (
            voice_client
            and voice_client.channel
            and message.author.voice
            and message.author.voice.channel == voice_client.channel
            and not message.content.startswith(BotSettings.BOT_PREFIX)
            and message.channel.id == allowed_text_channel_id
        )

    def get_style_id(self, user_id, guild_id):
        """ユーザーまたはギルドのスタイルIDを取得します。"""
        return self.config_pickle.get(
            user_id,
            self.config_pickle.get(guild_id, {}).get(
                "user_default", USER_DEFAULT_STYLE_ID
            ),
        )

    def update_style_setting(self, guild_id, user_id, style_id, voice_scope):
        # Ensure the guild_id exists in the config_pickle
        if guild_id not in self.config_pickle:
            self.config_pickle[guild_id] = {}

        # Ensure the specific voice_scope exists for this guild
        if voice_scope not in self.config_pickle[guild_id]:
            self.config_pickle[guild_id][voice_scope] = {}
        if voice_scope == "user_default":
            self.config_pickle[guild_id]["user_default"] = style_id
        elif voice_scope == "announcement":
            self.config_pickle[guild_id]["announcement"] = style_id
        elif voice_scope == "user":
            self.config_pickle[user_id] = style_id
        self.save_style_settings()


def get_character_info(speaker_name):
    # もち子さんの特別な処理
    if speaker_name == "もち子さん":
        character_key = "もち子さん"  # CHARACTORS_INFOでのキー
        display_name = "VOICEVOX:もち子(cv 明日葉よもぎ)"  # 特別な表示名
    else:
        character_key = speaker_name  # その他のスピーカーは通常通り処理
        display_name = f"VOICEVOX:{speaker_name}"  # 標準の表示名

    character_id = CHARACTORS_INFO.get(character_key, "unknown")  # キャラクターIDを取得
    return character_id, display_name


def fetch_json(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.ConnectionError as e:
        logging.error(f"Connection error: {e}")
    except requests.Timeout as e:
        logging.error(f"Timeout error: {e}")
    except requests.RequestException as e:
        logging.error(f"General Request error: {e}")
    return None


def load_style_settings():
    """スタイル設定をロードします。"""
    try:
        with open(CONFIG_PICKLE_FILE, "rb") as f:  # rbモードで開く
            return pickle.load(f)  # ファイルからpickleオブジェクトをロード
    except (FileNotFoundError, pickle.UnpicklingError):
        return {}  # ファイルが見つからないか、pickle読み込みエラーの場合は空の辞書を返す


# 正規表現パターンをグローバル変数として一度コンパイル
user_mention_pattern = re.compile(r"<@!?(\d+)>")
role_mention_pattern = re.compile(r"<@&(\d+)>")
channel_pattern = re.compile(r"<#(\d+)>")
custom_emoji_pattern = re.compile(r"<:(\w*):\d*>")
url_pattern = re.compile(r"https?://\S+")
english_word_pattern = re.compile(r"\b[a-zA-Z_]+\b")
laugh_pattern = re.compile("[ｗwW]+$")


def replace_user_mention(match, message: discord.Message):
    user_id = int(match.group(1))
    user = message.guild.get_member(user_id)
    return user.display_name + "さん" if user else match.group(0)


def replace_role_mention(match, message: discord.Message):
    role_id = int(match.group(1))
    role = discord.utils.get(message.guild.roles, id=role_id)
    return role.name + "役職" if role else match.group(0)


def replace_channel_mention(match, message: discord.Message):
    channel_id = int(match.group(1))
    channel = message.guild.get_channel(channel_id)
    return channel.name + "チャンネル" if channel else match.group(0)


def replace_custom_emoji_name_to_kana(match):
    emoji_name = match.group(1)
    return jaconv.alphabet2kana(emoji_name) + " "


def replace_english_to_kana(text):
    # 英単語を検出する正規表現パターン
    english_word_pattern = re.compile(r"\b[a-zA-Z_]+\b")

    def replace_to_kana(match):
        # 英単語をかなに変換
        word = match.group(0)

        # アンダースコアでつながった単語を分割
        sub_words = word.split("_")
        kana_words = []

        for sub_word in sub_words:
            kana = alkana.get_kana(sub_word)
            # alkanaが変換できなかった場合は、元の単語をそのまま使用
            kana_words.append(kana if kana is not None else sub_word)

        # かなに変換された単語を結合
        return "".join(kana_words)

    # 英単語をかなに置き換え
    return english_word_pattern.sub(replace_to_kana, text)


# 文末の連続する「ｗ」を「わら」と置き換える
def laugh_replace(match):
    return "わら" * len(match.group(0))


async def replace_content(text, message: discord.Message):
    # 一括置換のための関数定義
    def replace_patterns(text):
        # Change the order here
        text = replace_english_to_kana(text)  # First replace English words
        text = user_mention_pattern.sub(
            lambda m: replace_user_mention(m, message), text
        )
        text = role_mention_pattern.sub(
            lambda m: replace_role_mention(m, message), text
        )
        text = channel_pattern.sub(
            lambda m: replace_channel_mention(m, message), text
        )
        text = custom_emoji_pattern.sub(replace_custom_emoji_name_to_kana, text)
        text = url_pattern.sub("URL省略", text)
        text = laugh_pattern.sub(laugh_replace, text)
        return text

    # 文章を一括で置換
    replaced_text = replace_patterns(text)
    return replaced_text

async def welcome_user(
    server: VoiceSynthServer,
    interaction: discord.Interaction,
    voice_client: discord.VoiceClient,
    voice_config: VoiceSynthConfig,
):
    guild_id, text_channel_id = get_and_update_guild_settings(interaction, voice_config)
    style_ids = get_style_ids(guild_id, interaction.user.id, voice_config)
    speaker_details = get_speaker_details(voice_config, *style_ids)
    info_message = create_info_message(interaction, text_channel_id, speaker_details)
    await execute_welcome_message(
        server, voice_client, guild_id, style_ids[1], info_message, interaction
    )


def get_and_update_guild_settings(
    interaction: discord.Interaction, voice_config: VoiceSynthConfig
):
    guild_id = interaction.guild_id
    text_channel_id = interaction.channel_id
    # Updated to clarify the intention and reduce complexity
    guild_settings = voice_config.config_pickle.setdefault(guild_id, {})
    guild_settings["text_channel"] = text_channel_id
    voice_config.save_style_settings()
    return guild_id, text_channel_id


def get_style_ids(guild_id, user_id, voice_config: VoiceSynthConfig):
    guild_settings = voice_config.config_pickle.get(guild_id, {})
    user_style_id = voice_config.config_pickle.get(
        user_id, guild_settings.get("user_default", USER_DEFAULT_STYLE_ID)
    )
    announcement_style_id = guild_settings.get(
        "announcement", ANNOUNCEMENT_DEFAULT_STYLE_ID
    )
    user_default_style_id = guild_settings.get("user_default", USER_DEFAULT_STYLE_ID)
    return user_style_id, announcement_style_id, user_default_style_id


def get_speaker_details(
    voice_config: VoiceSynthConfig,
    user_style_id,
    announcement_style_id,
    user_default_style_id,
):
    user_speaker_name, user_style_name = voice_config.get_style_details(user_style_id)
    _, user_display_name = get_character_info(user_speaker_name)  # display_nameを取得

    announcement_speaker_name, announcement_style_name = voice_config.get_style_details(
        announcement_style_id
    )
    _, announcement_display_name = get_character_info(
        announcement_speaker_name
    )  # display_nameを取得

    user_default_speaker_name, user_default_style_name = voice_config.get_style_details(
        user_default_style_id
    )
    _, user_default_display_name = get_character_info(
        user_default_speaker_name
    )  # display_nameを取得

    return {
        "user": (user_display_name, user_style_name),
        "announcement": (announcement_display_name, announcement_style_name),
        "default": (user_default_display_name, user_default_style_name),
    }


def create_info_message(
    interaction: discord.Interaction, text_channel_id, speaker_details
):
    user_display_name = interaction.user.display_name
    user, announcement, default = (
        speaker_details["user"],
        speaker_details["announcement"],
        speaker_details["default"],
    )
    return (
        f"テキストチャンネル: <#{text_channel_id}>\n"
        f"{user_display_name}さんの読み上げ音声: [{user[0]}] - {user[1]}\n"
        f"アナウンス音声（サーバー設定）: [{announcement[0]}] - {announcement[1]}\n"
        f"デフォルト読み上げ音声（サーバー設定）: [{default[0]}] - {default[1]}\n"
    )


async def execute_welcome_message(
    server: VoiceSynthServer,
    voice_client,
    guild_id,
    style_id,
    message,
    interaction: discord.Interaction,
):
    welcome_voice = "読み上げを開始します。"
    try:
        await server.text_to_speech(voice_client, welcome_voice, style_id, guild_id)
        await interaction.followup.send(message)
    except Exception as e:
        logging.error(f"Welcome message execution failed: {e}")
        await interaction.followup.send(ERROR_MESSAGES["welcome"])


async def connect_to_voice_channel(interaction: discord.Interaction):
    try:
        channel = interaction.user.voice.channel
        if channel is None:
            raise ValueError("ユーザーがボイスチャンネルにいません。")
        voice_client = await channel.connect(self_deaf=True)
        return voice_client
    except Exception as e:
        logging.error(f"Voice channel connection error: {e}")
        raise
