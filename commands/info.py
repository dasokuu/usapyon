import discord
from VoiceSynthEventProcessor import VoiceSynthEventProcessor
from settings import APPROVED_GUILD_OBJECTS
from VoiceSynthConfig import VoiceSynthConfig


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


def setup_info_command(bot, synth_config: VoiceSynthConfig):
    @bot.tree.command(
        name="info",
        guilds=APPROVED_GUILD_OBJECTS,
        description="現在の設定を表示します。",
    )
    async def info(interaction: discord.Interaction):
        guild_id = interaction.guild_id

        # サーバーの設定を取得
        guild_settings = synth_config.synth_config_pickle.get(guild_id, {})
        text_channel_id = guild_settings.get("text_channel", "未設定")
        style_ids = synth_config.get_style_ids(guild_id, interaction.user.id)
        speaker_details = synth_config.get_speaker_details(*style_ids)
        info_message = create_info_message(
            interaction, text_channel_id, speaker_details
        )

        # ユーザーに設定の詳細を表示
        await interaction.response.send_message(info_message, ephemeral=True)
