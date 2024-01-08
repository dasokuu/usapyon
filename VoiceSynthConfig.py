import logging
import pickle
import re
import discord
import emoji
import jaconv
import requests
import alkana
from settings import (
    CHARACTORS_INFO,
    ERROR_MESSAGES,
    USER_DEFAULT_STYLE_ID,
    ANNOUNCEMENT_DEFAULT_STYLE_ID,
    BotSettings,
    VoiceVoxSettings,
    CONFIG_PICKLE_FILE,
)


from VoiceSynthServer import VoiceSynthServer  # 絵文字の判定を行うためのライブラリ


class VoiceSynthConfig:
    def __init__(self):
        self.speakers = self.fetch_json(VoiceVoxSettings.SPEAKERS_URL)
        self.config_pickle = self.load_style_settings()
        # 正規表現パターンをグローバル変数として一度コンパイル
        self.user_mention_pattern = re.compile(r"<@!?(\d+)>")
        self.role_mention_pattern = re.compile(r"<@&(\d+)>")
        self.channel_pattern = re.compile(r"<#(\d+)>")
        self.custom_emoji_pattern = re.compile(r"<:(\w*):\d*>")
        self.url_pattern = re.compile(r"https?://\S+")
        self.english_word_pattern = re.compile(r"\b[a-zA-Z_]+\b")
        self.laugh_pattern = re.compile("[ｗwW]+$")

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
            user_style_id = self.get_user_style_id(member.id, guild_id)
            user_speaker_name, user_style_name = self.get_style_details(user_style_id)
            user_character_id, user_display_name = self.get_character_info(
                user_speaker_name
            )
            # user_url = f"{DORMITORY_URL_BASE}//{user_character_id}/"
            announcement_message = f"{member.display_name}さんの読み上げ音声: [{user_display_name}] - {user_style_name}"

            # テキストチャンネルを取得してメッセージを送信
            text_channel_id = self.config_pickle.get(guild_id, {}).get("text_channel")
            if text_channel_id:
                text_channel = bot.get_channel(text_channel_id)
                if text_channel:
                    await text_channel.send(announcement_message)
            announcement_style_id = self.get_announcement_style_id(guild_id)
            await server.text_to_speech(
                voice_client, announcement_voice, announcement_style_id, guild_id
            )

        # ボイスチャンネルから切断したとき
        elif (
            before.channel == voice_client.channel
            and after.channel != voice_client.channel
        ):
            announcement_voice = f"{member.display_name}さんが退室しました。"
            announcement_style_id = self.get_announcement_style_id(member.guild.id)
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

            message_content = await self.replace_content(message.content, message)

            if not isinstance(message_content, str):
                logging.error(
                    f"Replaced message content is not a string: {message_content}"
                )
                return

            if message_content:
                await server.text_to_speech(
                    message.guild.voice_client,
                    message_content,
                    self.get_user_style_id(message.author.id, guild_id),
                    guild_id,
                )
            if message.attachments:
                await self.announce_file_post(server, message)

            # New Code: Announce sticker name if a sticker is posted
            if message.stickers:
                await self.announce_sticker_post(server, message)

        except Exception as e:
            logging.error(f"Error in handle_message: {e}")

    # New Method: Announce the name of the sticker
    async def announce_sticker_post(
        self, server: VoiceSynthServer, message: discord.Message
    ):
        """スタンプ投稿をアナウンスします。"""
        guild_id = message.guild.id
        announcement_style_id = self.get_announcement_style_id(guild_id)

        for sticker in message.stickers:
            sticker_name = sticker.name
            announcement_message = f"{sticker_name}スタンプが投稿されました。"
            await server.text_to_speech(
                message.guild.voice_client,
                announcement_message,
                announcement_style_id,
                guild_id,
            )

    async def announce_file_post(
        self, server: VoiceSynthServer, message: discord.Message
    ):
        """ファイル投稿をアナウンスします。"""
        guild_id = message.guild.id
        announcement_style_id = self.config_pickle.get(message.guild.id, {}).get(
            "announcement", ANNOUNCEMENT_DEFAULT_STYLE_ID
        )

        file_messages = []
        for attachment in message.attachments:
            if attachment.content_type.startswith("image/"):
                file_messages.append("画像")
            elif attachment.content_type.startswith("video/"):
                file_messages.append("動画")
            elif attachment.content_type.startswith("audio/"):
                file_messages.append("音声ファイル")
            elif attachment.content_type.startswith("text/"):
                file_messages.append("テキストファイル")
            else:
                file_messages.append("ファイル")

        if file_messages:
            file_message = f"{', '.join(file_messages)}が投稿されました。"
            await server.text_to_speech(
                message.guild.voice_client,
                file_message,
                announcement_style_id,
                guild_id,
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

    def get_user_style_id(self, user_id, guild_id):
        """指定されたユーザーのスタイルIDを取得します。"""
        # ユーザーに固有のスタイルIDが設定されていればそれを返し、そうでなければギルドのデフォルトを返します。
        return self.config_pickle.get(
            user_id,
            self.config_pickle.get(guild_id, {}).get(
                "user_default", USER_DEFAULT_STYLE_ID
            ),
        )

    def get_announcement_style_id(self, guild_id):
        """指定されたギルドのアナウンス用スタイルIDを取得します。"""
        # ギルドのアナウンス用スタイルIDを返します。設定されていない場合はデフォルトのアナウンススタイルIDを返します。
        return self.config_pickle.get(guild_id, {}).get(
            "announcement", ANNOUNCEMENT_DEFAULT_STYLE_ID
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

    def get_style_ids(self, guild_id, user_id):
        user_style_id = self.get_user_style_id(user_id, guild_id)
        announcement_style_id = self.get_announcement_style_id(guild_id)
        user_default_style_id = self.get_user_default_style_id(guild_id)
        return user_style_id, announcement_style_id, user_default_style_id

    def get_user_default_style_id(self, guild_id):
        """指定されたギルドのデフォルトユーザー読み上げスタイルIDを取得します。"""
        # ギルドに設定されているデフォルトのユーザースタイルIDを返します。設定されていない場合は、事前に定義されたデフォルトのユーザースタイルIDを返します。
        return self.config_pickle.get(guild_id, {}).get(
            "user_default", USER_DEFAULT_STYLE_ID
        )

    async def welcome_user(
        self,
        server: VoiceSynthServer,
        interaction: discord.Interaction,
        voice_client: discord.VoiceClient,
    ):
        guild_id, text_channel_id = self.get_and_update_guild_settings(interaction)
        style_ids = self.get_style_ids(guild_id, interaction.user.id)
        speaker_details = self.get_speaker_details(*style_ids)
        info_message = self.create_info_message(
            interaction, text_channel_id, speaker_details
        )
        await self.execute_welcome_message(
            server, voice_client, guild_id, style_ids[1], info_message, interaction
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
        guild_settings = self.config_pickle.setdefault(guild_id, {})
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

    async def execute_welcome_message(
        self,
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

    def replace_user_mention(self, match, message: discord.Message):
        user_id = int(match.group(1))
        user = message.guild.get_member(user_id)
        return user.display_name if user else match.group(0)

    def replace_role_mention(self, match, message: discord.Message):
        role_id = int(match.group(1))
        role = discord.utils.get(message.guild.roles, id=role_id)
        return role.name if role else match.group(0)

    def replace_channel_mention(self, match, message: discord.Message):
        channel_id = int(match.group(1))
        channel = message.guild.get_channel(channel_id)
        return channel.name if channel else match.group(0)

    def replace_custom_emoji_name_to_kana(self, match):
        emoji_name = match.group(1)
        return jaconv.alphabet2kana(emoji_name) + " "

    def replace_english_to_kana(self, text):
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
    def laugh_replace(self, match):
        return "わら" * len(match.group(0))

    async def replace_content(self, text, message: discord.Message):
        # 一括置換のための関数定義
        def replace_patterns(text):
            # Change the order here
            text = self.replace_english_to_kana(text)  # First replace English words
            text = self.user_mention_pattern.sub(
                lambda m: self.replace_user_mention(m, message), text
            )
            text = self.role_mention_pattern.sub(
                lambda m: self.replace_role_mention(m, message), text
            )
            text = self.channel_pattern.sub(
                lambda m: self.replace_channel_mention(m, message), text
            )
            text = self.custom_emoji_pattern.sub(
                self.replace_custom_emoji_name_to_kana, text
            )
            text = self.url_pattern.sub("URL省略", text)
            text = self.laugh_pattern.sub(self.laugh_replace, text)
            return text

        text = emoji.demojize(text, language="ja")
        # 文章を一括で置換
        replaced_text = replace_patterns(text)
        return replaced_text
