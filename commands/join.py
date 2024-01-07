import logging
import discord
from settings import APPROVED_GUILD_OBJECTS, ERROR_MESSAGES
from utils import VoiceSynthConfig, connect_to_voice_channel, welcome_user
from voice import VoiceSynthServer


def setup_join_command(bot, server: VoiceSynthServer, voice_config: VoiceSynthConfig):
    # ボットをボイスチャンネルに接続するコマンド
    @bot.tree.command(
        name="join",
        guilds=APPROVED_GUILD_OBJECTS,
        description="ボットをボイスチャンネルに接続し、読み上げを開始します。",
    )
    async def join(interaction: discord.Interaction):
        # defer the response to keep the interaction alive
        await interaction.response.defer()
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.followup.send(ERROR_MESSAGES["connection"])
        try:
            voice_client = await connect_to_voice_channel(interaction)
            await welcome_user(server, interaction, voice_client, voice_config)
        except discord.ClientException as e:
            logging.error(f"Connection error: {e}")
            await interaction.followup.send(f"接続中にエラーが発生しました: {e}")
