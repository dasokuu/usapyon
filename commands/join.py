import logging
import discord
from SpeechTextFormatter import SpeechTextFormatter
from VoiceSynthEventProcessor import ConnectionButtons
from settings import error_messages
from VoiceSynthConfig import VoiceSynthConfig
from VoiceSynthService import VoiceSynthService


async def execute_welcome_message(
    voice_client,
    guild_id,
    style_id,
    message,
    interaction: discord.Interaction,
    text_processor: SpeechTextFormatter,
    synth_service: VoiceSynthService,
    synth_config: VoiceSynthConfig
):
    welcome_voice = "読み上げを開始します。"
    try:
        await synth_service.text_to_speech(
            voice_client,
            welcome_voice,
            style_id,
            guild_id,
            text_processor,
            message,
        )
        await interaction.response.send_message(message, view=ConnectionButtons(synth_config, synth_service))
    except Exception as e:
        logging.error(f"Welcome message execution failed: {e}")
        await interaction.response.send_message(error_messages["welcome"], ephemeral=True)


def create_info_message(
    interaction: discord.Interaction, text_channel_id, speaker_details
):
    user_display_name = interaction.user.display_name
    user, announcement = (
        speaker_details["user"],
        speaker_details["announcement"],
    )
    return (
        f"テキストチャンネル: <#{text_channel_id}>\n"
        f"{user_display_name}さんの読み上げ音声: [{user[0]}] - {user[1]}\n"
        f"入退室時等の音声（サーバー設定）: [{announcement[0]}] - {announcement[1]}\n"
    )


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


async def welcome_user(
    synth_config: VoiceSynthConfig,
    synth_service: VoiceSynthService,
    interaction: discord.Interaction,
    voice_client: discord.VoiceClient,
    text_processor: SpeechTextFormatter,
):
    guild_id, text_channel_id = synth_config.get_and_update_guild_settings(
        interaction
    )
    style_ids = synth_config.get_style_ids(guild_id, interaction.user.id)
    speaker_details = synth_config.get_speaker_details(*style_ids)
    info_message = create_info_message(
        interaction, text_channel_id, speaker_details
    )
    await execute_welcome_message(
        voice_client,
        guild_id,
        style_ids[1],
        info_message,
        interaction,
        text_processor,
        synth_service,
        synth_config
    )


def setup_join_command(
    bot,
    synth_service: VoiceSynthService,
    synth_config: VoiceSynthConfig,
    text_processor: SpeechTextFormatter
):
    @bot.tree.command(
        name="join",
        description="ボットをボイスチャンネルに接続し、読み上げを開始します。",
    )
    async def join(interaction: discord.Interaction):
        # ユーザーがボイスチャンネルにいない場合、エラーメッセージを表示
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message(error_messages["connection"], ephemeral=True)
            return

        # ボットが既に接続されている場合、エラーメッセージを表示して処理を終了
        if interaction.guild.voice_client:
            await interaction.response.send_message("ボットはすでにボイスチャンネルに接続されています。")
            return

        # ここから通常の接続処理
        try:
            voice_client = await connect_to_voice_channel(interaction)
            await welcome_user(
                synth_config, synth_service, interaction, voice_client, text_processor
            )
        except discord.ClientException as e:
            logging.error(f"Connection error: {e}")
            await interaction.response.send_message(f"接続中にエラーが発生しました: {e}")
