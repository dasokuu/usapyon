import discord
from settings import APPROVED_GUILD_OBJECTS
from utils import VoiceSynthConfig
from voice import VoiceSynthServer


def setup_leave_command(bot, server: VoiceSynthServer, voice_config: VoiceSynthConfig):
    # ボットをボイスチャンネルから切断するコマンド
    @bot.tree.command(
        name="leave", guilds=APPROVED_GUILD_OBJECTS, description="ボットをボイスチャンネルから切断します。"
    )
    async def leave(interaction: discord.Interaction):
        # ボイスクライアントが存在しない場合、何もせずに終了
        if not interaction.guild.voice_client:
            await interaction.response.send_message("ボットはボイスチャンネルに接続されていません。")
            return

        guild_id = interaction.guild_id
        # キューをクリア
        await server.clear_playback_queue(guild_id)

        # テキストチャンネル設定を削除
        if "text_channel" in voice_config.config_pickle.get(guild_id, {}):
            del voice_config.config_pickle[guild_id]["text_channel"]
        voice_config.save_style_settings()

        # ボイスクライアントを切断
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("ボイスチャンネルから切断しました。")
