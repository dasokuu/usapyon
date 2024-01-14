import logging
import discord
from SpeechTextFormatter import SpeechTextFormatter
from VoiceSynthConfig import VoiceSynthConfig
from VoiceSynthService import VoiceSynthService
from commands.info import info_logic
from commands.leave import leave_logic
from commands.settings import settings_logic


def create_info_message(
    member: discord.Member, text_channel_id, guild_id, synth_config: VoiceSynthConfig
):
    style_ids = synth_config.get_style_ids(guild_id, member.id)
    speaker_details = synth_config.get_speaker_details(*style_ids)
    user_display_name = member.display_name
    user, announcement = (
        speaker_details["user"],
        speaker_details["announcement"],
    )
    return (
        f"読み上げチャンネル: <#{text_channel_id}>\n"
        f"{user_display_name}さんの読み上げ音声: [{user[0]}] - {user[1]}\n"
        f"入退室時等の音声（サーバー設定）: [{announcement[0]}] - {announcement[1]}\n"
        f"__VOICEVOXを使用するにはキャラクターのクレジットを記載する必要があります。__ご注意ください。"
    )


class ConnectionButtons(discord.ui.View):
    def __init__(self, synth_config, synth_service):
        super().__init__(timeout=43200)
        self.settings_logic = settings_logic
        self.leave_logic = leave_logic
        self.info_logic = info_logic  # infoコマンドのロジックを追加
        self.synth_config = synth_config
        self.synth_service = synth_service

    @discord.ui.button(label="設定", style=discord.ButtonStyle.primary, custom_id="settings_button")
    async def settings_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.settings_logic(interaction, self.synth_config)

    @discord.ui.button(label="切断", style=discord.ButtonStyle.danger, custom_id="leave_button")
    async def leave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.leave_logic(interaction, self.synth_config, self.synth_service)

    @discord.ui.button(label="情報", style=discord.ButtonStyle.secondary, custom_id="info_button")
    async def info_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.info_logic(interaction, self.synth_config)  # infoコマンドの実行


class VoiceSynthEventProcessor:
    def __init__(self, synth_config: VoiceSynthConfig, synth_service: VoiceSynthService, text_processor: SpeechTextFormatter):
        self.synth_config = synth_config
        self.synth_service = synth_service
        self.text_processor = text_processor

    async def handle_voice_state_update(
        self,
        bot,
        member: discord.Member,
        before,
        after,
    ):
        guild_id = member.guild.id
        if self.synth_config.get_manual_disconnection(guild_id):
            return  # マニュアル切断が有効な場合は何もしない
        # ボット自身の状態変更を無視
        if member == bot.user:
            return

        # ボットが接続しているボイスチャンネルを取得
        voice_client = member.guild.voice_client

        # ボットが新しいVCに接続した場合の処理
        if before.channel != after.channel and after.channel is not None:
            if voice_client is None or not voice_client.is_connected():
                # ボットが接続していない場合、新しいVCに接続を試みる
                try:
                    voice_client = await after.channel.connect(self_deaf=True)
                    # テキストチャンネルの設定を更新
                    self.synth_config.voice_synthesis_settings[guild_id][
                        "text_channel"
                    ] = after.channel.id
                    self.synth_config.save_style_settings()
                    # 追加の読み上げ対象チャンネルをクリア
                    self.synth_config.unlist_channel(guild_id)
                    announcement_style_id = self.synth_config.get_announcement_style_id(
                        guild_id
                    )
                    message = create_info_message(
                        member, after.channel.id, guild_id, self.synth_config
                    )
                    await voice_client.channel.send(
                        "**読み上げを開始します。\n**" + message,
                        view=ConnectionButtons(
                            self.synth_config, self.synth_service),
                    )
                    await self.synth_service.clear_playback_queue(guild_id)
                    # 接続成功時の読み上げメッセージ
                    welcome_message = "読み上げを開始します。"
                    await self.synth_service.text_to_speech(
                        voice_client,
                        welcome_message,
                        announcement_style_id,
                        guild_id,
                        self.text_processor,
                    )

                except discord.ClientException as e:
                    logging.error(f"Connection error: {e}")
                return
        if not voice_client or not voice_client.channel:
            return

        if (
            before.channel != voice_client.channel
            and after.channel == voice_client.channel
        ):
            await self.announce_presence(
                member,
                voice_client,
                "entered",
            )
        # ユーザーがボイスチャンネルから退出した場合の処理
        elif (
            before.channel == voice_client.channel
            and after.channel != voice_client.channel
        ):
            # ボイスチャンネルに他の非ボットユーザーがまだいるか確認
            if any(not user.bot for user in before.channel.members if user != member):
                await self.announce_presence(
                    member,
                    voice_client,
                    "left",
                )
        if after.channel is None and voice_client and voice_client.channel:
            # ボイスチャンネルにまだ非ボットユーザーがいるか確認します。
            if not any(not user.bot for user in voice_client.channel.members):
                # キューをクリアする
                await self.synth_service.clear_playback_queue(guild_id)
                # テキストチャンネルIDと追加チャンネルIDの設定をクリア
                guild_settings = self.synth_config.voice_synthesis_settings.get(
                    guild_id, {})
                if "text_channel" in guild_settings:
                    del guild_settings["text_channel"]
                if "additional_channel" in guild_settings:
                    del guild_settings["additional_channel"]
                self.synth_config.save_style_settings()  # 変更を保存
                await voice_client.disconnect()
        # ボットがボイスチャンネルに接続しているかどうかを確認
        voice_client = member.guild.voice_client
        if not voice_client or not voice_client.channel:
            return

        # ボットのいるチャンネルに他にユーザーがいないか確認
        if not any(not user.bot for user in voice_client.channel.members):
            # 移動先のボイスチャンネルを決定（ここでは単純にメンバーが移動したチャンネルを使用）
            new_channel = after.channel

            if new_channel:
                # 新しいチャンネルにボットを接続
                await voice_client.move_to(new_channel)
                # 新しいチャンネルのテキストチャンネルIDを更新
                self.synth_config.voice_synthesis_settings[member.guild.id][
                    "text_channel"
                ] = new_channel.id
                # 追加の読み上げチャンネルをクリア
                if "additional_channel" in self.synth_config.voice_synthesis_settings[member.guild.id]:
                    del self.synth_config.voice_synthesis_settings[member.guild.id]["additional_channel"]
                self.synth_config.save_style_settings()
                # 新しいチャンネルへの移動をアナウンス
                announcement_style_id = self.synth_config.get_announcement_style_id(
                    member.guild.id
                )
                await self.synth_service.clear_playback_queue(guild_id)
                await self.synth_service.text_to_speech(
                    voice_client,
                    f"読み上げボットが移動しました。",
                    announcement_style_id,
                    member.guild.id,
                    self.text_processor,
                )
                await new_channel.send(
                    "**読み上げボットが移動しました。**\n"
                    + create_info_message(
                        member, new_channel.id, guild_id, self.synth_config
                    ),
                    view=ConnectionButtons(
                        self.synth_config, self.synth_service),
                )

    async def handle_message(
        self,
        message: discord.Message,
    ):
        if not self.synth_config.should_process_message(message, message.guild.id):
            return
        guild_id = message.guild.id
        try:
            logging.info(f"Handling message: {message.content}")
            if not isinstance(message.content, str):
                logging.error(
                    f"Message content is not a string: {message.content}")
                return

            message_content = message.content

            if not isinstance(message_content, str):
                logging.error(
                    f"Replaced message content is not a string: {message_content}"
                )
                return
            # TenorのGIFリンクをチェック
            if "tenor.com/view/" in message.content:
                await self.speach_gif(
                    message
                )
                return
            if message_content:
                await self.synth_service.text_to_speech(
                    message.guild.voice_client,
                    message_content,
                    self.synth_config.get_user_style_id(
                        message.author.id, guild_id),
                    guild_id,
                    self.text_processor,
                    message,
                )
            if message.attachments:
                await self.announce_file_post(
                    message
                )
            if message.stickers:
                await self.speach_sticker(
                    message
                )
        except discord.DiscordException as e:
            logging.error(f"Discord specific error: {e}")
        except Exception as e:
            logging.error(f"General error in handle_message: {e}")

    async def speach_gif(
        self,
        message: discord.Message,
    ):
        """TenorのGIFが投稿された場合"""
        guild_id = message.guild.id
        user_style_id = self.synth_config.get_user_style_id(
            message.author.id, guild_id)
        text = "GIF画像"
        await self.synth_service.text_to_speech(
            message.guild.voice_client,
            text,
            user_style_id,
            guild_id,
            self.text_processor,
            message,
        )

    async def speach_sticker(
        self,
        message: discord.Message,
    ):
        """スタンプ投稿"""
        guild_id = message.guild.id
        user_style_id = self.synth_config.get_user_style_id(
            message.author.id, guild_id)

        for sticker in message.stickers:
            sticker_name = sticker.name
            text = f"{sticker_name} のスタンプ"
            await self.synth_service.text_to_speech(
                message.guild.voice_client,
                text,
                user_style_id,
                guild_id,
                self.text_processor,
                message,
            )

    async def announce_presence(
        self,
        member: discord.Member,
        voice_client,
        action="entered",
    ):
        action_texts = {"entered": "が入室しました。", "left": "が退室しました。"}
        action_text = action_texts.get(action, "が行動しました。")

        # 入室アクション時にVOICEVOXのスピーカー名を使用
        if action == "entered":
            user_style_id = self.synth_config.get_user_style_id(
                member.id, member.guild.id)
            user_speaker_name, user_style_name = self.synth_config.get_style_details(
                user_style_id
            )
            _, user_display_name = self.synth_config.get_character_info(
                user_speaker_name
            )  # display_nameを取得
            send_message = f"{member.display_name}さんの読み上げ音声: [{user_display_name}] - {user_style_name}"
            # テキストチャンネルへのメッセージ送信
            text_channel_id = self.synth_config.voice_synthesis_settings.get(
                member.guild.id, {}
            ).get("text_channel")
            if text_channel_id:
                text_channel = member.guild.get_channel(text_channel_id)
                if text_channel:
                    await text_channel.send(send_message)
        try:
            announcement_voice = f"{member.display_name}さん{action_text}"
            announcement_style_id = self.synth_config.get_announcement_style_id(
                member.guild.id)
            await self.synth_service.text_to_speech(
                voice_client,
                announcement_voice,
                announcement_style_id,
                member.guild.id,
                self.text_processor,
            )
        except Exception as e:
            logging.error(f"Failed to announce presence: {e}")
            # 必要に応じて、復旧処理や追加のエラーメッセージをここに追加

    async def announce_file_post(self, message: discord.Message):
        """ファイル投稿をアナウンスします。"""
        file_messages = self._get_file_messages(message.attachments)
        if file_messages:
            file_message = f"{'と'.join(file_messages)}が投稿されました。"
            await self._announce_message(file_message, message)

    def _get_file_messages(self, attachments):
        file_counts = {"image/": 0, "video/": 0,
                       "audio/": 0, "text/": 0, "other": 0}
        for attachment in attachments:
            file_type = next(
                (ft for ft in file_counts if attachment.content_type.startswith(ft)), "other")
            file_counts[file_type] += 1

        return [self._format_file_message(ft, count) for ft, count in file_counts.items() if count > 0]

    @staticmethod
    def _format_file_message(file_type, count):
        type_names = {"image/": "画像", "video/": "動画",
                      "audio/": "音声ファイル", "text/": "テキストファイル", "other": "ファイル"}
        return f"{count}個の{type_names[file_type]}" if count > 1 else type_names[file_type]

    async def _announce_message(self, message, discord_message):
        guild_id = discord_message.guild.id
        announcement_style_id = self.synth_config.get_announcement_style_id(
            guild_id)
        await self.synth_service.text_to_speech(
            discord_message.guild.voice_client,
            message,
            announcement_style_id,
            guild_id,
            self.text_processor,
            discord_message,
        )
