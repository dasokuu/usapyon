import logging

import discord
from VoiceSynthConfig import VoiceSynthConfig
from VoiceSynthServer import VoiceSynthServer
from settings import ANNOUNCEMENT_DEFAULT_STYLE_ID


class VoiceSynth:
    async def handle_voice_state_update(
        self,
        voice_config: VoiceSynthConfig,
        voice_server: VoiceSynthServer,
        bot,
        member: discord.Member,
        before,
        after,
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
            user_style_id = voice_config.get_user_style_id(member.id, guild_id)
            user_speaker_name, user_style_name = voice_config.get_style_details(
                user_style_id
            )
            user_character_id, user_display_name = voice_config.get_character_info(
                user_speaker_name
            )
            # user_url = f"{DORMITORY_URL_BASE}//{user_character_id}/"
            announcement_message = f"{member.display_name}さんの読み上げ音声: [{user_display_name}] - {user_style_name}"

            # テキストチャンネルを取得してメッセージを送信
            text_channel_id = voice_config.voice_config_pickle.get(guild_id, {}).get(
                "text_channel"
            )
            if text_channel_id:
                text_channel = bot.get_channel(text_channel_id)
                if text_channel:
                    await text_channel.send(announcement_message)
            announcement_style_id = voice_config.get_announcement_style_id(guild_id)
            await voice_server.text_to_speech(
                voice_client, announcement_voice, announcement_style_id, guild_id
            )

        # ボイスチャンネルから切断したとき
        elif (
            before.channel == voice_client.channel
            and after.channel != voice_client.channel
        ):
            announcement_voice = f"{member.display_name}さんが退室しました。"
            announcement_style_id = voice_config.get_announcement_style_id(
                member.guild.id
            )
            await voice_server.text_to_speech(
                voice_client, announcement_voice, announcement_style_id, guild_id
            )

        # ボイスチャンネルに誰もいなくなったら自動的に切断します。
        if after.channel is None and member.guild.voice_client:
            # ボイスチャンネルにまだ誰かいるか確認します。
            if not any(not user.bot for user in before.channel.members):
                # キューをクリアする
                await voice_server.clear_playback_queue(guild_id)
                if (
                    guild_id in voice_config.voice_config_pickle
                    and "text_channel"
                    in voice_config.voice_config_pickle.get(guild_id, {})
                ):
                    # テキストチャンネルIDの設定をクリア
                    del voice_config.voice_config_pickle[guild_id]["text_channel"]
                    voice_config.save_style_settings()  # 変更を保存
                    logging.info(f"テキストチャンネルの設定をクリアしました: サーバーID {guild_id}")
                await member.guild.voice_client.disconnect()

    async def handle_message(self,
        voice_config: VoiceSynthConfig,
        voice_server: VoiceSynthServer,
        message: discord.Message,
    ):
        guild_id = message.guild.id
        try:
            logging.info(f"Handling message: {message.content}")
            if not isinstance(message.content, str):
                logging.error(f"Message content is not a string: {message.content}")
                return

            message_content = await voice_config.replace_content(
                message.content, message
            )

            if not isinstance(message_content, str):
                logging.error(
                    f"Replaced message content is not a string: {message_content}"
                )
                return

            if message_content:
                await voice_server.text_to_speech(
                    message.guild.voice_client,
                    message_content,
                    voice_config.get_user_style_id(message.author.id, guild_id),
                    guild_id,
                )
            if message.attachments:
                await voice_config.announce_file_post(voice_server, message)

            # New Code: Announce sticker name if a sticker is posted
            if message.stickers:
                await voice_config.announce_sticker_post(voice_server, message)

        except Exception as e:
            logging.error(f"Error in handle_message: {e}")

    # New Method: Announce the name of the sticker
    async def announce_sticker_post(
        self,
        voice_config: VoiceSynthConfig,
        voice_server: VoiceSynthServer,
        message: discord.Message,
    ):
        """スタンプ投稿をアナウンスします。"""
        guild_id = message.guild.id
        announcement_style_id = voice_config.get_announcement_style_id(guild_id)

        for sticker in message.stickers:
            sticker_name = sticker.name
            announcement_message = f"{sticker_name}スタンプが投稿されました。"
            await voice_server.text_to_speech(
                message.guild.voice_client,
                announcement_message,
                announcement_style_id,
                guild_id,
            )

    async def announce_file_post(
        self,
        voice_config: VoiceSynthConfig,
        voice_server: VoiceSynthServer,
        message: discord.Message,
    ):
        """ファイル投稿をアナウンスします。"""
        guild_id = message.guild.id
        announcement_style_id = voice_config.voice_config_pickle.get(
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
            await voice_server.text_to_speech(
                message.guild.voice_client,
                file_message,
                announcement_style_id,
                guild_id,
            )

    async def welcome_user(
        self,
        voice_config: VoiceSynthConfig,
        voice_server: VoiceSynthServer,
        interaction: discord.Interaction,
        voice_client: discord.VoiceClient,
    ):
        guild_id, text_channel_id = voice_config.get_and_update_guild_settings(
            interaction
        )
        style_ids = voice_config.get_style_ids(guild_id, interaction.user.id)
        speaker_details = voice_config.get_speaker_details(*style_ids)
        info_message = voice_config.create_info_message(
            interaction, text_channel_id, speaker_details
        )
        await voice_server.execute_welcome_message(
            voice_client,
            guild_id,
            style_ids[1],
            info_message,
            interaction,
        )
