import discord
from settings import APPROVED_GUILD_OBJECTS, error_messages, info_messages
from VoiceSynthConfig import VoiceSynthConfig
from VoiceSynthService import VoiceSynthService


def setup_leave_command(
    bot, synth_server: VoiceSynthService, synth_config: VoiceSynthConfig
):
    # ボットをボイスチャンネルから切断するコマンド
    @bot.tree.command(
        name="leave", guilds=APPROVED_GUILD_OBJECTS, description="ボットをボイスチャンネルから切断します。"
    )
    async def leave(interaction: discord.Interaction):
        # ボイスクライアントが存在しない場合、何もせずに終了
        if not interaction.guild.voice_client:
            await interaction.response.send_message(error_messages["not_connected"])
            return

        guild_id = interaction.guild_id
        # キューをクリア
        await synth_server.clear_playback_queue(guild_id)

        # テキストチャンネル設定を削除
        if "text_channel" in synth_config.synth_config_pickle.get(guild_id, {}):
            del synth_config.synth_config_pickle[guild_id]["text_channel"]
        synth_config.save_style_settings()

        # ボイスクライアントを切断
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message(info_messages["disconnect"])
