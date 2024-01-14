import discord
from settings import error_messages, info_messages
from VoiceSynthConfig import VoiceSynthConfig
from VoiceSynthService import VoiceSynthService


async def leave_logic(interaction: discord.Interaction, synth_config: VoiceSynthConfig, synth_service: VoiceSynthService):
    # ボイスクライアントが存在しない場合、何もせずに終了
    if not interaction.guild.voice_client:
        await interaction.response.send_message(error_messages["not_connected"], ephemeral=True)
        return

    # ユーザーがボイスチャンネルにいるかどうか確認
    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.response.send_message(error_messages["no_vc_user"], ephemeral=True)
        return

    guild_id = interaction.guild_id
    # キューをクリア
    await synth_service.clear_playback_queue(guild_id)
    # テキストチャンネル設定を削除
    if "text_channel" in synth_config.voice_synthesis_settings.get(guild_id, {}):
        del synth_config.voice_synthesis_settings[guild_id]["text_channel"]
    # 追加チャンネル設定の削除
    synth_config.unlist_channel(interaction.guild_id)
    # ボイスクライアントを切断
    await interaction.guild.voice_client.disconnect()
    synth_config.set_manual_disconnection(interaction.guild_id, True)
    # ボットが手動で切断されたことをユーザーに通知
    await interaction.response.send_message("ボットは手動で切断されました。再接続するには `/join` コマンドを使用してください。")


def setup_leave_command(
    bot, synth_service: VoiceSynthService, synth_config: VoiceSynthConfig
):
    # ボットをボイスチャンネルから切断するコマンド
    @bot.tree.command(
        name="leave", description="ボットをボイスチャンネルから切断します。"
    )
    async def leave(interaction: discord.Interaction):
        await leave_logic(interaction, synth_config, synth_service)
