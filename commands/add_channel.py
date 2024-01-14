import discord

from VoiceSynthConfig import VoiceSynthConfig


def setup_additional_channel_command(bot, synth_config: VoiceSynthConfig):
    @bot.tree.command(name="add_channel", description="このテキストチャンネルを読み上げ対象に追加します。")
    async def add_channel(interaction: discord.Interaction):
        # ユーザーがボイスチャンネルにいるかどうかを確認
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message("このコマンドを使用するには、ボイスチャンネルにいる必要があります。", ephemeral=True)
            return

        # 現在のチャンネルIDを使用
        is_different = synth_config.add_additional_channel(
            interaction.guild_id, interaction.channel_id)

        # 追加されたチャンネルの名前を取得
        channel_name = interaction.guild.get_channel(
            interaction.channel_id).name

        if is_different:
            await interaction.response.send_message(f"ボイスチャンネル `{interaction.user.voice.channel.name}` に接続済みです。チャンネル `{channel_name}` を追加の読み上げ対象にしました。")
        else:
            await interaction.response.send_message(f"チャンネル `{channel_name}` は既に読み上げ対象として設定されています。", ephemeral=True)

    @bot.tree.command(
        name="unlist_channel",
        description="追加の読み上げ対象チャンネルを削除します。"
    )
    async def unlist_channel(interaction: discord.Interaction):
        # 追加チャンネルの削除
        synth_config.unlist_channel(interaction.guild_id)
        await interaction.response.send_message("追加の読み上げ対象チャンネルを削除しました。")
