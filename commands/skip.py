import discord
from settings import APPROVED_GUILD_OBJECTS, INFO_MESSAGES
from voice import VoiceSynthServer


def setup_skip_command(bot, server: VoiceSynthServer):
    @bot.tree.command(
        name="skip",
        guilds=APPROVED_GUILD_OBJECTS,
        description="現在の読み上げをスキップし、次の項目に移動します。",
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

        # ギルドの再生キューを取得して次の項目を再生
        guild_queue = server.get_guild_playback_queue(guild_id)
        if not guild_queue.empty():
            voice_client, line, style_id = await guild_queue.get()
            guild_queue.task_done()  # 現在のタスクを完了としてマーク
            await server.speak_line(voice_client, line, style_id)  # 次の行を読み上げる

        await interaction.followup.send(INFO_MESSAGES["skip"])
