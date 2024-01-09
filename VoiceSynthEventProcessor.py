import logging
import discord
from SpeechTextFormatter import SpeechTextFormatter
from VoiceSynthConfig import VoiceSynthConfig
from VoiceSynthService import VoiceSynthService
from settings import ANNOUNCEMENT_DEFAULT_STYLE_ID, BotSettings, error_messages


class VoiceSynthEventProcessor:
    async def handle_voice_state_update(
        self,
        synth_config: VoiceSynthConfig,
        synth_service: VoiceSynthService,
        bot,
        member: discord.Member,
        before,
        after,
        text_processor: SpeechTextFormatter,
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
                synth_service,
                text_processor,
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
                synth_service,
                text_processor,
                "left",
            )

        # ボイスチャンネルに誰もいなくなったら自動的に切断します。
        if after.channel is None and member.guild.voice_client:
            # ボイスチャンネルにまだ誰かいるか確認します。
            if not any(not user.bot for user in before.channel.members):
                # キューをクリアする
                await synth_service.clear_playback_queue(guild_id)
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
        synth_service: VoiceSynthService,
        message: discord.Message,
        text_processor: SpeechTextFormatter,
    ):
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
                await self.speach_gif(
                    message, synth_config, text_processor, synth_service
                )
                return
            if message_content:
                await synth_service.text_to_speech(
                    message.guild.voice_client,
                    message_content,
                    synth_config.get_user_style_id(
                        message.author.id, guild_id),
                    guild_id,
                    text_processor,
                    message,
                )
            if message.attachments:
                await self.announce_file_post(
                    synth_config, synth_service, message, text_processor
                )
            if message.stickers:
                await self.speach_sticker(
                    synth_config, synth_service, message, text_processor
                )
        except Exception as e:
            logging.error(f"Error in handle_message: {e}")

    async def speach_gif(
        self,
        message: discord.Message,
        synth_config: VoiceSynthConfig,
        text_processor: SpeechTextFormatter,
        synth_service: VoiceSynthService,
    ):
        """TenorのGIFが投稿された場合"""
        guild_id = message.guild.id
        user_style_id = synth_config.get_user_style_id(
            message.author.id, guild_id)
        text = "GIF画像"
        await synth_service.text_to_speech(
            message.guild.voice_client,
            text,
            user_style_id,
            guild_id,
            text_processor,
            message,
        )

    async def speach_sticker(
        self,
        synth_config: VoiceSynthConfig,
        synth_service: VoiceSynthService,
        message: discord.Message,
        text_processor: SpeechTextFormatter,
    ):
        """スタンプ投稿"""
        guild_id = message.guild.id
        user_style_id = synth_config.get_user_style_id(
            message.author.id, guild_id)

        for sticker in message.stickers:
            sticker_name = sticker.name
            text = f"{sticker_name} のスタンプ"
            await synth_service.text_to_speech(
                message.guild.voice_client,
                text,
                user_style_id,
                guild_id,
                text_processor,
                message,
            )

    async def announce_presence(
        self,
        member: discord.Member,
        voice_client,
        synth_config: VoiceSynthConfig,
        synth_service: VoiceSynthService,
        text_processor: SpeechTextFormatter,
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
        await synth_service.text_to_speech(
            voice_client,
            announcement_voice,
            announcement_style_id,
            member.guild.id,
            text_processor,
        )

    async def announce_file_post(
        self,
        synth_config: VoiceSynthConfig,
        synth_service: VoiceSynthService,
        message: discord.Message,
        text_processor: SpeechTextFormatter,
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
            await synth_service.text_to_speech(
                message.guild.voice_client,
                file_message,
                announcement_style_id,
                guild_id,
                text_processor,
                message,
            )
