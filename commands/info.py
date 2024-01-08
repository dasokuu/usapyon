import discord
from settings import APPROVED_GUILD_OBJECTS
from VoiceSynthConfig import VoiceSynthConfig


def setup_info_command(bot, voice_config: VoiceSynthConfig):
    @bot.tree.command(
        name="info",
        guilds=APPROVED_GUILD_OBJECTS,
        description="現在の読み上げ音声スコープと設定を表示します。",
    )
    async def info(interaction: discord.Interaction):
        guild_id = interaction.guild_id

        # サーバーの設定を取得
        guild_settings = voice_config.voice_config_pickle.get(guild_id, {})
        text_channel_id = guild_settings.get("text_channel", "未設定")
        style_ids = voice_config.get_style_ids(guild_id, interaction.user.id)
        speaker_details = voice_config.get_speaker_details(*style_ids)
        info_message = voice_config.create_info_message(
            interaction, text_channel_id, speaker_details
        )

        # ユーザーに設定の詳細を表示
        await interaction.response.send_message(info_message, ephemeral=True)
