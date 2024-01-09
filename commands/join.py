import logging
import discord
from SpeechTextFormatter import SpeechTextFormatter
from VoiceSynthEventProcessor import VoiceSynthEventProcessor
from settings import APPROVED_GUILD_OBJECTS, error_messages
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
        await interaction.followup.send(message)
    except Exception as e:
        logging.error(f"Welcome message execution failed: {e}")
        await interaction.followup.send(error_messages["welcome"])


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
        f"未設定ユーザーの読み上げ音声（サーバー設定）: [{default[0]}] - {default[1]}\n"
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
    )


def setup_join_command(
    bot,
    synth_service: VoiceSynthService,
    synth_config: VoiceSynthConfig,
    text_processor: SpeechTextFormatter
):
    # ボットをボイスチャンネルに接続するコマンド
    @bot.tree.command(
        name="join",
        guilds=APPROVED_GUILD_OBJECTS,
        description="ボットをボイスチャンネルに接続し、読み上げを開始します。",
    )
    async def join(interaction: discord.Interaction):
        # defer the response to keep the interaction alive
        await interaction.response.defer()
        guild_id = interaction.guild.id
        text_channel_id = interaction.channel_id

        # ユーザーがボイスチャンネルにいない場合、エラーメッセージを表示
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.followup.send(error_messages["connection"])
            return

        # VCにすでに接続されている場合
        if interaction.guild.voice_client:
            # 読み上げテキストチャンネルが既に設定されているが、異なる場合は更新
            if (
                guild_id in synth_config.voice_synthesis_settings
                and synth_config.voice_synthesis_settings[guild_id].get("text_channel")
                != text_channel_id
            ):
                synth_config.voice_synthesis_settings[guild_id]["text_channel"] = text_channel_id
                synth_config.save_style_settings()
                # ユーザーに読み上げテキストチャンネルが変更されたことを通知
                await interaction.followup.send(
                    f"読み上げテキストチャンネルを<#{text_channel_id}>に変更しました。"
                )
            else:
                # テキストチャンネルが変更されていない場合
                await interaction.followup.send("ボットはすでにボイスチャンネルに接続されています。")
        else:
            # ボットがVCに接続されていない場合、通常の接続処理を実行
            try:
                voice_client = await connect_to_voice_channel(interaction)
                await welcome_user(
                    synth_config, synth_service, interaction, voice_client, text_processor
                )
            except discord.ClientException as e:
                logging.error(f"Connection error: {e}")
                await interaction.followup.send(f"接続中にエラーが発生しました: {e}")
