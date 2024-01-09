import logging
import discord
from DiscordMessageHandler import DiscordMessageHandler
from VoiceSynthConfig import VoiceSynthConfig
from VoiceSynthServer import VoiceSynthServer
from settings import ANNOUNCEMENT_DEFAULT_STYLE_ID, BotSettings, error_messages


class VoiceSynthHandler:
    async def handle_voice_state_update(
        self,
        synth_config: VoiceSynthConfig,
        synth_server: VoiceSynthServer,
        bot,
        member: discord.Member,
        before,
        after,
        message_handler: DiscordMessageHandler,
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
            await self.announce_presence(
                member,
                voice_client,
                synth_config,
                synth_server,
                message_handler,
                "entered",
            )
        elif (
            before.channel == voice_client.channel
            and after.channel != voice_client.channel
        ):
            await self.announce_presence(
                member,
                voice_client,
                synth_config,
                synth_server,
                message_handler,
                "left",
            )

        # ボイスチャンネルに誰もいなくなったら自動的に切断します。
        if after.channel is None and member.guild.voice_client:
            # ボイスチャンネルにまだ誰かいるか確認します。
            if not any(not user.bot for user in before.channel.members):
                # キューをクリアする
                await synth_server.clear_playback_queue(guild_id)
                if (
                    guild_id in synth_config.synth_config_pickle
                    and "text_channel"
                    in synth_config.synth_config_pickle.get(guild_id, {})
                ):
                    # テキストチャンネルIDの設定をクリア
                    del synth_config.synth_config_pickle[guild_id]["text_channel"]
                    synth_config.save_style_settings()  # 変更を保存
                    logging.info(f"テキストチャンネルの設定をクリアしました: サーバーID {guild_id}")
                await member.guild.voice_client.disconnect()

    async def handle_message(
        self,
        synth_config: VoiceSynthConfig,
        synth_server: VoiceSynthServer,
        message: discord.Message,
        message_handler: DiscordMessageHandler,
    ):
        # この行を追加
        if not synth_config.should_process_message(message, message.guild.id):
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
                await self.announce_gif_post(
                    message, synth_config, message_handler, synth_server
                )
                return
            if message_content:
                await self.text_to_speech(
                    message.guild.voice_client,
                    message_content,
                    synth_config.get_user_style_id(
                        message.author.id, guild_id),
                    guild_id,
                    message_handler,
                    synth_server,
                    message,
                )
            if message.attachments:
                await self.announce_file_post(
                    synth_config, synth_server, message, message_handler
                )
            # New Code: Announce sticker name if a sticker is posted
            if message.stickers:
                await self.announce_sticker_post(
                    synth_config, synth_server, message, message_handler
                )
        except Exception as e:
            logging.error(f"Error in handle_message: {e}")

    async def announce_gif_post(
        self,
        message: discord.Message,
        synth_config: VoiceSynthConfig,
        message_handler: DiscordMessageHandler,
        synth_server: VoiceSynthServer,
    ):
        """TenorのGIFリンクが投稿された場合にアナウンスする。"""
        guild_id = message.guild.id
        announcement_style_id = synth_config.get_announcement_style_id(
            guild_id)
        announcement_message = "GIF画像が投稿されました。"
        await self.text_to_speech(
            message.guild.voice_client,
            announcement_message,
            announcement_style_id,
            guild_id,
            message_handler,
            synth_server,
            message,
        )

    async def announce_presence(
        self,
        member: discord.Member,
        voice_client,
        synth_config: VoiceSynthConfig,
        synth_server: VoiceSynthServer,
        message_handler: DiscordMessageHandler,  # message_handlerを追加
        action="entered",
    ):
        action_texts = {"entered": "が入室しました。", "left": "が退室しました。"}
        action_text = action_texts.get(action, "が行動しました。")

        # 入室アクション時にVOICEVOXのスピーカー名を使用
        if action == "entered":
            user_style_id = synth_config.get_user_style_id(
                member.id, member.guild.id)
            user_speaker_name, user_style_name = synth_config.get_style_details(
                user_style_id
            )
            _, user_display_name = synth_config.get_character_info(
                user_speaker_name
            )  # display_nameを取得
            send_message = f"{member.display_name}さんの読み上げ音声: [{user_display_name}] - {user_style_name}"
            # テキストチャンネルへのメッセージ送信
            text_channel_id = synth_config.synth_config_pickle.get(
                member.guild.id, {}
            ).get("text_channel")
            if text_channel_id:
                text_channel = member.guild.get_channel(text_channel_id)
                if text_channel:
                    await text_channel.send(send_message)
        announcement_voice = f"{member.display_name}さん{action_text}"
        announcement_style_id = synth_config.get_announcement_style_id(
            member.guild.id)
        await self.text_to_speech(
            voice_client,
            announcement_voice,
            announcement_style_id,
            member.guild.id,
            message_handler,
            synth_server,
        )

    # New Method: Announce the name of the sticker
    async def announce_sticker_post(
        self,
        synth_config: VoiceSynthConfig,
        synth_server: VoiceSynthServer,
        message: discord.Message,
        message_handler: DiscordMessageHandler,
    ):
        """スタンプ投稿をアナウンスします。"""
        guild_id = message.guild.id
        announcement_style_id = synth_config.get_announcement_style_id(
            guild_id)

        for sticker in message.stickers:
            sticker_name = sticker.name
            announcement_message = f"{sticker_name} のスタンプが投稿されました。"
            await self.text_to_speech(
                message.guild.voice_client,
                announcement_message,
                announcement_style_id,
                guild_id,
                message_handler,
                synth_server,
                message,
            )

    async def announce_file_post(
        self,
        synth_config: VoiceSynthConfig,
        synth_server: VoiceSynthServer,
        message: discord.Message,
        message_handler: DiscordMessageHandler,
    ):
        """ファイル投稿をアナウンスします。"""
        guild_id = message.guild.id
        announcement_style_id = synth_config.synth_config_pickle.get(
            message.guild.id, {}
        ).get("announcement", ANNOUNCEMENT_DEFAULT_STYLE_ID)

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
            await self.text_to_speech(
                message.guild.voice_client,
                file_message,
                announcement_style_id,
                guild_id,
                message_handler,
                synth_server,
                message,
            )

    async def welcome_user(
        self,
        synth_config: VoiceSynthConfig,
        synth_server: VoiceSynthServer,
        interaction: discord.Interaction,
        voice_client: discord.VoiceClient,
        message_handler: DiscordMessageHandler,
    ):
        guild_id, text_channel_id = synth_config.get_and_update_guild_settings(
            interaction
        )
        style_ids = synth_config.get_style_ids(guild_id, interaction.user.id)
        speaker_details = synth_config.get_speaker_details(*style_ids)
        info_message = self.create_info_message(
            interaction, text_channel_id, speaker_details
        )
        await self.execute_welcome_message(
            voice_client,
            guild_id,
            style_ids[1],
            info_message,
            interaction,
            message_handler,
            synth_server,
        )

    async def text_to_speech(
        self,
        voice_client: discord.VoiceClient,
        text,
        style_id,
        guild_id,
        message_handler: DiscordMessageHandler,
        synth_server: VoiceSynthServer,
        message: discord.Message = None,
    ):
        if not voice_client or not voice_client.is_connected():
            logging.error("Voice client is not connected.")
            return

        try:
            lines = text.split("\n")
            for line in filter(None, lines):
                # DiscordMessageHandlerを用いてテキストを処理
                processed_line = await message_handler.replace_content(line, message)
                guild_queue = synth_server.get_guild_playback_queue(guild_id)
                await guild_queue.put((voice_client, processed_line, style_id))
        except Exception as e:
            logging.error(f"Error in text_to_speech: {e}")
            # Handle specific exceptions and add remediation here.

    async def execute_welcome_message(
        self,
        voice_client,
        guild_id,
        style_id,
        message,
        interaction: discord.Interaction,
        message_handler: DiscordMessageHandler,
        synth_server: VoiceSynthServer,
    ):
        welcome_voice = "読み上げを開始します。"
        try:
            await self.text_to_speech(
                voice_client,
                welcome_voice,
                style_id,
                guild_id,
                message_handler,
                synth_server,
                message,
            )
            await interaction.followup.send(message)
        except Exception as e:
            logging.error(f"Welcome message execution failed: {e}")
            await interaction.followup.send(error_messages["welcome"])

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
            f"未設定ユーザーの読み上げ音声（サーバー設定）: [{default[0]}] - {default[1]}\n"
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
