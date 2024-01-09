import discord
from settings import APPROVED_GUILD_OBJECTS, info_messages
from VoiceSynthService import VoiceSynthService


def setup_skip_command(bot, synth_service: VoiceSynthService):
    @bot.tree.command(
        name="skip",
        guilds=APPROVED_GUILD_OBJECTS,
        description="現在の読み上げをスキップし、再生キューをクリアします。",
    )
    async def skip(interaction: discord.Interaction):
        await interaction.response.defer()  # 迅速な応答でインタラクションを保持

        guild_id = interaction.guild_id
        voice_client = interaction.guild.voice_client

        # ボイスクライアントが存在しない場合、何もせずに終了
        if not voice_client or not voice_client.is_connected():
            await interaction.followup.send("ボットはボイスチャンネルに接続されていません。")
            return

        # 再生中のオーディオがあれば停止する
        if voice_client.is_playing():
            voice_client.stop()

        # ギルドの再生キューを確認し、空の場合はユーザーに通知
        guild_queue = synth_service.get_guild_playback_queue(guild_id)
        if guild_queue.empty():
            await interaction.followup.send(info_messages["no_queue"])
        else:
            # キューが空ではない場合、キューをクリアしてスキップされたことをユーザーに通知
            await synth_service.clear_playback_queue(guild_id)
            await interaction.followup.send(info_messages["skip"])
