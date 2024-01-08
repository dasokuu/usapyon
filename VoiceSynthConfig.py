import logging
import pickle
import discord
import requests
from settings import (
    CHARACTORS_INFO,
    USER_DEFAULT_STYLE_ID,
    ANNOUNCEMENT_DEFAULT_STYLE_ID,
    BotSettings,
    VoiceVoxSettings,
    CONFIG_PICKLE_FILE,
)


class VoiceSynthConfig:
    def __init__(self):
        self.speakers = self.fetch_json(VoiceVoxSettings.SPEAKERS_URL)
        self.voice_config_pickle = self.load_style_settings()

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
            pickle.dump(self.voice_config_pickle, f)  # config_pickleをpickleで保存

    def should_process_message(self, message: discord.Message, guild_id):
        """メッセージが処理対象かどうかを判断します。"""
        voice_client = message.guild.voice_client
        allowed_text_channel_id = self.voice_config_pickle.get(guild_id, {}).get(
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

    def get_user_style_id(self, user_id, guild_id):
        """指定されたユーザーのスタイルIDを取得します。"""
        # ユーザーに固有のスタイルIDが設定されていればそれを返し、そうでなければギルドのデフォルトを返します。
        return self.voice_config_pickle.get(
            user_id,
            self.voice_config_pickle.get(guild_id, {}).get(
                "user_default", USER_DEFAULT_STYLE_ID
            ),
        )

    def get_announcement_style_id(self, guild_id):
        """指定されたギルドのアナウンス用スタイルIDを取得します。"""
        # ギルドのアナウンス用スタイルIDを返します。設定されていない場合はデフォルトのアナウンススタイルIDを返します。
        return self.voice_config_pickle.get(guild_id, {}).get(
            "announcement", ANNOUNCEMENT_DEFAULT_STYLE_ID
        )

    def update_style_setting(self, guild_id, user_id, style_id, voice_scope):
        # Ensure the guild_id exists in the config_pickle
        if guild_id not in self.voice_config_pickle:
            self.voice_config_pickle[guild_id] = {}

        # Ensure the specific voice_scope exists for this guild
        if voice_scope not in self.voice_config_pickle[guild_id]:
            self.voice_config_pickle[guild_id][voice_scope] = {}
        if voice_scope == "user_default":
            self.voice_config_pickle[guild_id]["user_default"] = style_id
        elif voice_scope == "announcement":
            self.voice_config_pickle[guild_id]["announcement"] = style_id
        elif voice_scope == "user":
            self.voice_config_pickle[user_id] = style_id
        self.save_style_settings()

    def get_style_ids(self, guild_id, user_id):
        user_style_id = self.get_user_style_id(user_id, guild_id)
        announcement_style_id = self.get_announcement_style_id(guild_id)
        user_default_style_id = self.get_user_default_style_id(guild_id)
        return user_style_id, announcement_style_id, user_default_style_id

    def get_user_default_style_id(self, guild_id):
        """指定されたギルドのデフォルトユーザー読み上げスタイルIDを取得します。"""
        # ギルドに設定されているデフォルトのユーザースタイルIDを返します。設定されていない場合は、事前に定義されたデフォルトのユーザースタイルIDを返します。
        return self.voice_config_pickle.get(guild_id, {}).get(
            "user_default", USER_DEFAULT_STYLE_ID
        )

    def get_speaker_details(
        self,
        user_style_id,
        announcement_style_id,
        user_default_style_id,
    ):
        user_speaker_name, user_style_name = self.get_style_details(user_style_id)
        _, user_display_name = self.get_character_info(
            user_speaker_name
        )  # display_nameを取得

        announcement_speaker_name, announcement_style_name = self.get_style_details(
            announcement_style_id
        )
        _, announcement_display_name = self.get_character_info(
            announcement_speaker_name
        )  # display_nameを取得

        user_default_speaker_name, user_default_style_name = self.get_style_details(
            user_default_style_id
        )
        _, user_default_display_name = self.get_character_info(
            user_default_speaker_name
        )  # display_nameを取得

        return {
            "user": (user_display_name, user_style_name),
            "announcement": (announcement_display_name, announcement_style_name),
            "default": (user_default_display_name, user_default_style_name),
        }

    def get_and_update_guild_settings(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        text_channel_id = interaction.channel_id
        # Updated to clarify the intention and reduce complexity
        guild_settings = self.voice_config_pickle.setdefault(guild_id, {})
        guild_settings["text_channel"] = text_channel_id
        self.save_style_settings()
        return guild_id, text_channel_id

    def create_info_message(
        self, interaction: discord.Interaction, text_channel_id, speaker_details
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

    async def connect_to_voice_channel(self, interaction: discord.Interaction):
        try:
            channel = interaction.user.voice.channel
            if channel is None:
                raise ValueError("ユーザーがボイスチャンネルにいません。")
            voice_client = await channel.connect(self_deaf=True)
            return voice_client
        except Exception as e:
            logging.error(f"Voice channel connection error: {e}")
            raise

    def get_character_info(self, speaker_name):
        # もち子さんの特別な処理
        if speaker_name == "もち子さん":
            character_key = "もち子さん"  # CHARACTORS_INFOでのキー
            display_name = "VOICEVOX:もち子(cv 明日葉よもぎ)"  # 特別な表示名
        else:
            character_key = speaker_name  # その他のスピーカーは通常通り処理
            display_name = f"VOICEVOX:{speaker_name}"  # 標準の表示名

        character_id = CHARACTORS_INFO.get(character_key, "unknown")  # キャラクターIDを取得
        return character_id, display_name

    def fetch_json(self, url):
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

    def load_style_settings(self):
        """スタイル設定をロードします。"""
        try:
            with open(CONFIG_PICKLE_FILE, "rb") as f:  # rbモードで開く
                return pickle.load(f)  # ファイルからpickleオブジェクトをロード
        except (FileNotFoundError, pickle.UnpicklingError):
            return {}  # ファイルが見つからないか、pickle読み込みエラーの場合は空の辞書を返す
