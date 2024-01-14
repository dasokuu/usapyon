import discord

from VoiceSynthConfig import VoiceSynthConfig


def setup_additional_channel_command(bot, synth_config: VoiceSynthConfig):
    @bot.tree.command(name="add_channel", description="このテキストチャンネルを読み上げ対象に追加します。")
    async def add_channel(interaction: discord.Interaction):
        # ユーザーがボイスチャンネルにいるかどうかを確認
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message("このコマンドを使用するには、ボイスチャンネルにいる必要があります。", ephemeral=True)
            return

        # 追加されたチャンネルの名前を取得
        current_channel_id = synth_config.voice_synthesis_settings.get(
            interaction.guild.id, {}).get('text_channel')

        if interaction.channel_id != current_channel_id:
            synth_config.add_additional_channel(
                interaction.guild.id, interaction.channel.id)
            await interaction.response.send_message(f"ボイスチャンネル <#{current_channel_id}> に接続済みです。チャンネル <#{interaction.channel_id}> を追加の読み上げ対象にしました。")
        else:
            await interaction.response.send_message(f"チャンネル <#{interaction.channel_id}> は既に読み上げ対象として設定されています。", ephemeral=True)

    @bot.tree.command(
        name="unlist_channel",
        description="追加の読み上げ対象チャンネルを削除します。"
    )
    async def unlist_channel(interaction: discord.Interaction):
        # 追加チャンネルの削除
        synth_config.unlist_channel(interaction.guild_id)
        await interaction.response.send_message("追加の読み上げ対象チャンネルを削除しました。")
