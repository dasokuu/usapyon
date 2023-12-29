import discord
from discord.ext import commands
import os
from utils import handle_message, handle_voice_state_update
from voice import process_playback_queue
from bot_commands import setup_commands, CustomHelpCommand
from settings import BOT_PREFIX, GAME_NAME
from discord import app_commands

GUILD_ID = discord.Object(id='1189256965172514836')  # Replace 'your_guild_id' with your guild's ID

if __name__ == "__main__":
    # Initialize bot with intents and prefix
    intents = discord.Intents.default()
    intents.messages = True
    intents.guilds = True
    intents.voice_states = True
    intents.message_content = True
    bot = commands.Bot(
        command_prefix=BOT_PREFIX, intents=intents, help_command=CustomHelpCommand()
    )
    setup_commands(bot)

    @bot.event
    async def on_ready():
        print(f"Logged in as {bot.user.name}")
        await bot.change_presence(activity=discord.Game(name=GAME_NAME))
        await self.tree.sync(guild=GUILD_ID)
        for guild in bot.guilds:
            bot.loop.create_task(process_playback_queue(str(guild.id)))

    # tree = app_commands.CommandTree(bot)

    # Define a slash command using the bot's tree attribute
    @bot.tree.command(name='hello', description='Say hello!')
    async def slash_hello(interaction: discord.Interaction):
        await interaction.response.send_message(f'Hello {interaction.user.mention}!')

    @bot.event
    async def on_message(message):
        # ボット自身のメッセージは無視
        if message.author == bot.user:
            return

        # コマンド処理を妨げないようにする
        await bot.process_commands(message)
        await handle_message(bot, message)

    @bot.event
    async def on_voice_state_update(member, before, after):
        await handle_voice_state_update(bot, member, before, after)

    bot.run(os.getenv("VOICECHATLOIDTEST_TOKEN"))
