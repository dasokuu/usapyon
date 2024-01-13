import discord
from VoiceSynthConfig import VoiceSynthConfig


def create_info_message(interaction: discord.Interaction, text_channel_id, additional_channel_id, speaker_details):
    user_display_name = interaction.user.display_name
    user, announcement, default = (
        speaker_details["user"],
        speaker_details["announcement"],
        speaker_details["default"],
    )
    additional_channel_info = f"追加の読み上げチャンネル: <#{additional_channel_id}>" if additional_channel_id else "追加の読み上げチャンネル: なし"

    return (
        f"テキストチャンネル: <#{text_channel_id}>\n"
        f"{additional_channel_info}\n"
        f"{user_display_name}さんの読み上げ音声: [{user[0]}] - {user[1]}\n"
        f"入退室時等の音声（サーバー設定）: [{announcement[0]}] - {announcement[1]}\n"
        f"未設定ユーザーの読み上げ音声（サーバー設定）: [{default[0]}] - {default[1]}\n"
    )


async def info_logic(interaction: discord.Interaction, synth_config: VoiceSynthConfig):
    guild_id = interaction.guild_id
    guild_settings = synth_config.voice_synthesis_settings.get(guild_id, {})
    text_channel_id = guild_settings.get("text_channel", "未設定")
    additional_channel_id = guild_settings.get("additional_channel")
    style_ids = synth_config.get_style_ids(guild_id, interaction.user.id)
    speaker_details = synth_config.get_speaker_details(*style_ids)
    info_message = create_info_message(
        interaction, text_channel_id, additional_channel_id, speaker_details
    )
    await interaction.response.send_message(info_message, ephemeral=True)


def setup_info_command(bot, synth_config: VoiceSynthConfig):
    @bot.tree.command(name="info", description="現在の設定を表示します。")
    async def info(interaction: discord.Interaction):
        await info_logic(interaction, synth_config)
