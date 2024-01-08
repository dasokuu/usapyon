import logging
import discord
from settings import APPROVED_GUILD_OBJECTS, ERROR_MESSAGES
from utils import VoiceSynthConfig, connect_to_voice_channel
from voice import VoiceSynthServer


def setup_join_command(bot, server: VoiceSynthServer, voice_config: VoiceSynthConfig):
    # ボットをボイスチャンネルに接続するコマンド
    @bot.tree.command(
        name="join",
        guilds=APPROVED_GUILD_OBJECTS,
        description="ボットをボイスチャンネルに接続し、読み上げを開始します。",
    )
    async def join(interaction: discord.Interaction):
        # defer the response to keep the interaction alive
        await interaction.response.defer()
        guild_id = interaction.guild.id
        text_channel_id = interaction.channel_id

        # ユーザーがボイスチャンネルにいない場合、エラーメッセージを表示
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.followup.send(ERROR_MESSAGES["connection"])
            return

        # VCにすでに接続されている場合
        if interaction.guild.voice_client:
            # 読み上げテキストチャンネルが既に設定されているが、異なる場合は更新
            if (
                guild_id in voice_config.config_pickle
                and voice_config.config_pickle[guild_id].get("text_channel") != text_channel_id
            ):
                voice_config.config_pickle[guild_id]["text_channel"] = text_channel_id
                voice_config.save_style_settings()
                # ユーザーに読み上げテキストチャンネルが変更されたことを通知
                await interaction.followup.send(
                    f"読み上げテキストチャンネルを<#{text_channel_id}>に変更しました。"
                )
            else:
                # テキストチャンネルが変更されていない場合
                await interaction.followup.send("ボットはすでにボイスチャンネルに接続されています。")
        else:
            # ボットがVCに接続されていない場合、通常の接続処理を実行
            try:
                voice_client = await connect_to_voice_channel(interaction)
                await voice_config.welcome_user(server, interaction, voice_client)
            except discord.ClientException as e:
                logging.error(f"Connection error: {e}")
                await interaction.followup.send(f"接続中にエラーが発生しました: {e}")
