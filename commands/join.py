import logging
import discord
from SpeechTextFormatter import SpeechTextFormatter
from settings_loader import error_messages
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
    synth_config: VoiceSynthConfig,
    bot,
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
        await interaction.response.send_message(
            message,
        )
    except Exception as e:
        logging.error(f"Welcome message execution failed: {e}")
        await interaction.response.send_message(
            error_messages["welcome"], ephemeral=True
        )


def create_info_message(
    interaction: discord.Interaction, text_channel_id, speaker_details
):
    user_display_name = interaction.user.display_name
    user, announcement = (
        speaker_details["user"],
        speaker_details["announcement"],
    )
    return (
        f"**読み上げを開始します。\n**"
        f"読み上げチャンネル: <#{text_channel_id}>\n"
        f"{user_display_name}さんの読み上げ音声: [{user[0]}]\n"
        f"入退室時等の音声（サーバー設定）: [{announcement[0]}]\n"
        f"__VOICEVOXを使用するにはキャラクタークレジットを記載する必要があります。__合成音声の配信や録画などはご注意ください。"
    )


async def connect_to_voice_channel(
    interaction: discord.Interaction, synth_config: VoiceSynthConfig
):
    try:
        channel = interaction.user.voice.channel
        if channel is None:
            raise ValueError("ユーザーがボイスチャンネルにいません。")

        # 追加の読み上げ対象チャンネルをクリア
        synth_config.unlist_channel(interaction.guild_id)

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
    bot,
):
    guild_id, text_channel_id = synth_config.get_and_update_guild_settings(
        interaction)
    style_ids = synth_config.get_style_ids(guild_id, interaction.user.id)
    speaker_details = synth_config.get_speaker_details(*style_ids)
    info_message = create_info_message(
        interaction, text_channel_id, speaker_details)
    await execute_welcome_message(
        voice_client,
        guild_id,
        style_ids[1],
        info_message,
        interaction,
        text_processor,
        synth_service,
        synth_config,
        bot,
    )


class MoveBotView(discord.ui.View):
    def __init__(
        self,
        synth_config: VoiceSynthConfig,
        synth_service: VoiceSynthService,
        text_processor: SpeechTextFormatter,
        bot,
    ):
        super().__init__()
        self.synth_config = synth_config
        self.synth_service = synth_service
        self.text_processor = text_processor
        self.bot = bot

    @discord.ui.button(label="はい", style=discord.ButtonStyle.success)
    async def yes_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await normal_join_procedure(interaction, self.synth_config, self.synth_service, self.text_processor, self.bot)

    @discord.ui.button(label="いいえ", style=discord.ButtonStyle.danger)
    async def no_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.edit_message(content="操作がキャンセルされました。", view=None)
        except Exception as e:
            logging.error(f"Error in no_button: {e}")
        finally:
            self.stop()


def setup_join_command(
    bot,
    synth_service: VoiceSynthService,
    synth_config: VoiceSynthConfig,
    text_processor: SpeechTextFormatter,
):
    @bot.tree.command(
        name="join",
        description="ボットをボイスチャンネルに接続し、読み上げを開始します。",
    )
    async def join(interaction: discord.Interaction):
        # ユーザーがボイスチャンネルにいない場合、エラーメッセージを表示
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message(
                error_messages["connection"], ephemeral=True
            )
            return

        # ユーザーがボイスチャンネルにいない場合、エラーメッセージを表示
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message(
                error_messages["connection"], ephemeral=True
            )
            return

        # Check if the bot is already connected
        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.channel:
            current_channel_id = synth_config.voice_synthesis_settings.get(
                interaction.guild.id, {}
            ).get("text_channel")
            # Check if the current channel is different from the stored channel
            if interaction.channel.id != current_channel_id:
                # ユーザーに既存のチャンネル情報を通知し、ボットを移動させるかどうかを尋ねる
                await interaction.response.send_message(
                    f"ボットは既にボイスチャンネル <#{voice_client.channel.id}> に接続しています。"
                    "新しいチャンネルにボットを移動させますか？",
                    view=MoveBotView(
                        synth_config, synth_service, text_processor, bot),
                    ephemeral=True,
                )
            else:
                # ボットが既に同じチャンネルに接続している場合
                await interaction.response.send_message(
                    "ボットは既にこのボイスチャンネルに接続しています。", ephemeral=True
                )

        else:
            # ボットが接続していない場合、通常の接続処理を行う
            await normal_join_procedure(
                interaction, synth_config, synth_service, text_processor, bot
            )


async def normal_join_procedure(
    interaction: discord.Interaction,
    synth_config: VoiceSynthConfig,
    synth_service: VoiceSynthService,
    text_processor: SpeechTextFormatter,
    bot,
):
    guild_id = interaction.guild_id
    voice_client = interaction.guild.voice_client

    try:
        # ボットが既にボイスチャンネルに接続している場合は、そのチャンネルを離脱する
        if voice_client and voice_client.is_connected():
            await voice_client.disconnect()

        # ボットを新しいボイスチャンネルに接続する
        voice_client = await interaction.user.voice.channel.connect(self_deaf=True)
        synth_config.set_manual_disconnection(
            guild_id, interaction.channel.id, False)
        await welcome_user(
            synth_config, synth_service, interaction, voice_client, text_processor, bot
        )

    except discord.ClientException as e:
        logging.error(f"Connection error: {e}")
        if not interaction.response.is_done():
            await interaction.response.send_message(f"接続中にエラーが発生しました: {e}")
