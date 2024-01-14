
import discord


async def help_logic(interaction: discord.Interaction, bot):
    commands_description = "\n".join(
        f"`/{command.name}`: {command.description}"
        for command in bot.tree.get_commands()
    )
    await interaction.response.send_message(
        f"**利用可能なコマンド一覧:**\n{commands_description}",
        ephemeral=True
    )


def setup_help_command(bot):
    @bot.tree.command(
        name="help",
        description="使用可能なコマンドのリストと説明を表示します。"
    )
    async def help(interaction: discord.Interaction):
        help_logic(interaction, bot)
