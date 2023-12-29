import discord
from discord.ext import commands
from settings import USER_DEFAULT_STYLE_ID, NOTIFY_STYLE_ID, MAX_MESSAGE_LENGTH
from utils import speakers, speaker_settings, save_style_settings, get_style_details
from voice import text_to_speech


import discord
from discord.ext import commands


class CustomHelpCommand(commands.HelpCommand):
    def __init__(self):
        super().__init__(command_attrs={"help": "コマンドリストと説明を表示します。"})

    async def send_bot_help(self, mapping):
        embed = discord.Embed(title="利用可能なコマンド", color=0x00FF00)
        for cog, commands in mapping.items():
            filtered_commands = await self.filter_commands(commands, sort=True)
            command_entries = []
            for command in filtered_commands:
                command_name = f"!{command.name}"
                alias_text = (
                    f" (または: {'|'.join(f'`!{a}`' for a in command.aliases)})"
                    if command.aliases
                    else ""
                )
                command_entries.append(
                    f"`{command_name}`{alias_text}: {command.short_doc or '説明なし'}"
                )
            if command_entries:
                cog_name = cog.qualified_name if cog else "一般コマンド"
                embed.add_field(
                    name=cog_name, value="\n".join(command_entries), inline=False
                )

        channel = self.get_destination()
        await channel.send(embed=embed)

    async def send_command_help(self, command):
        alias_text = (
            f" (または: {'|'.join(f'`!{a}`' for a in command.aliases)})"
            if command.aliases
            else ""
        )
        embed = discord.Embed(
            title=f"!{command.name}{alias_text}",
            color=0x00FF00,
        )
        embed.add_field(name="説明", value=command.help or "説明が設定されていません。", inline=False)
        embed.add_field(
            name="使用法", value=f"`{self.get_command_signature(command)}`", inline=False
        )

        channel = self.get_destination()
        await channel.send(embed=embed)

    async def command_not_found(self, string):
        return f'"{string}"というコマンドは見つかりませんでした。'

    async def send_error_message(self, error):
        channel = self.get_destination()
        await channel.send(error)


def setup_commands(bot):
    @bot.command(
        name="default_style",
        aliases=["ds"],
        help="ユーザーのデフォルトスタイルを表示または設定します。",
    )
    async def default_style(ctx, style_id: int = None):
        guild_id = str(ctx.guild.id)

        # Ensure server settings are initialized
        if guild_id not in speaker_settings:
            speaker_settings[guild_id] = {"user_default": USER_DEFAULT_STYLE_ID}

        # Use get to safely access 'user_default'
        current_default = speaker_settings[guild_id].get(
            "user_default", USER_DEFAULT_STYLE_ID
        )

        if style_id is not None:
            valid_style_ids = [
                style["id"] for speaker in speakers for style in speaker["styles"]
            ]
            if style_id in valid_style_ids:
                speaker_name, style_name = get_style_details(style_id)
                speaker_settings[guild_id]["user_default"] = style_id
                save_style_settings()
                await ctx.send(
                    f"ユーザーのデフォルトスタイルを「{speaker_name} {style_name}」(ID: {style_id})に設定しました。"
                )
            else:
                await ctx.send(f"スタイルID {style_id} は無効です。")
        else:
            # Display current default style
            user_speaker, user_default_style_name = get_style_details(
                current_default, "デフォルト"
            )
            response = f"**ユーザーのデフォルトスタイル:** {user_speaker} {user_default_style_name} (ID: {current_default})"
            await ctx.send(response)

    @bot.command(
        name="notify_style",
        aliases=["ns"],
        help="入退室読み上げのスタイルを表示または設定します。",
    )
    async def notify_style(ctx, style_id: int = None):
        guild_id = str(ctx.guild.id)

        # スタイルIDが指定されている場合は設定を更新
        if style_id is not None:
            valid_style_ids = [
                style["id"] for speaker in speakers for style in speaker["styles"]
            ]
            if style_id in valid_style_ids:
                speaker_name, style_name = get_style_details(style_id)
                if guild_id not in speaker_settings:
                    speaker_settings[guild_id] = {}
                speaker_settings[guild_id]["notify"] = style_id
                save_style_settings()
                await ctx.send(
                    f"入退出通知スタイルを {style_id} 「{speaker_name} {style_name}」(ID: {style_id})に設定しました。"
                )
                return
            else:
                await ctx.send(f"スタイルID {style_id} は無効です。")
                return

        # 現在のサーバースタイル設定を表示
        notify_style_id = speaker_settings.get(guild_id, {}).get(
            "default", NOTIFY_STYLE_ID
        )
        notify_speaker, notify_default_name = get_style_details(
            notify_style_id, "デフォルト"
        )

        response = f"**{ctx.guild.name}の通知スタイル:** {notify_speaker} {notify_default_name} (ID: {notify_style_id})\n"
        await ctx.send(response)

    @bot.command(
        name="my_style",
        aliases=["ms"],
        help="あなたの現在のスタイルを表示または設定します。",
    )
    async def my_style(ctx, style_id: int = None):
        user_id = str(ctx.author.id)

        # スタイルIDが指定されている場合は設定を更新
        if style_id is not None:
            valid_style_ids = [
                style["id"] for speaker in speakers for style in speaker["styles"]
            ]
            if style_id in valid_style_ids:
                speaker_name, style_name = get_style_details(style_id)
                speaker_settings[user_id] = style_id
                save_style_settings()
                await ctx.send(
                    f"{ctx.author.mention}さんのスタイルを「{speaker_name} {style_name}」(ID: {style_id})に設定しました。"
                )
                return
            else:
                await ctx.send(f"スタイルID {style_id} は無効です。")
                return

        # 現在のスタイル設定を表示
        user_style_id = speaker_settings.get(user_id, USER_DEFAULT_STYLE_ID)
        user_speaker, user_style_name = get_style_details(user_style_id, "デフォルト")

        response = f"**{ctx.author.display_name}さんのスタイル:** {user_speaker} {user_style_name} (ID: {user_style_id})"
        await ctx.send(response)

    @bot.command(name="join", help="ボットをボイスチャンネルに接続し、読み上げを開始します。")
    async def join(ctx):
        if ctx.author.voice and ctx.author.voice.channel:
            channel = ctx.author.voice.channel
            voice_client = await channel.connect(self_deaf=True)
            # 接続メッセージの読み上げ
            welcome_message = "読み上げを開始します。"

            guild_id = str(ctx.guild.id)
            text_channel_id = str(ctx.channel.id)  # このコマンドを使用したテキストチャンネルID

            # サーバー設定が存在しない場合は初期化
            if guild_id not in speaker_settings:
                speaker_settings[guild_id] = {"text_channel": text_channel_id}
            else:
                # 既にサーバー設定が存在する場合はテキストチャンネルIDを更新
                speaker_settings[guild_id]["text_channel"] = text_channel_id

            save_style_settings()  # 変更を保存

            # 通知スタイルIDを取得
            notify_style_id = speaker_settings.get(guild_id, {}).get(
                "notify", NOTIFY_STYLE_ID
            )

            # メッセージとスタイルIDをキューに追加
            await text_to_speech(
                voice_client, welcome_message, notify_style_id, guild_id
            )

    @bot.command(name="leave", help="ボットをボイスチャンネルから切断します。")
    async def leave(ctx):
        if ctx.voice_client:
            guild_id = str(ctx.guild.id)
            # テキストチャンネルIDの設定をクリア
            if "text_channel" in speaker_settings.get(guild_id, {}):
                del speaker_settings[guild_id]["text_channel"]
                save_style_settings()  # 変更を保存
            await ctx.voice_client.disconnect()
            await ctx.send("ボイスチャンネルから切断しました。")

    @bot.command(name="skip", help="現在再生中の音声をスキップします。")
    async def skip(ctx):
        voice_client = ctx.guild.voice_client
        if voice_client and voice_client.is_playing():
            voice_client.stop()
            await ctx.send("現在の読み上げをスキップしました。")
        else:
            await ctx.send("再生中の音声はありません。")

    @bot.command(name="list_styles", aliases=["ls"], help="利用可能なスタイルIDの一覧を表示します。")
    async def list_styles(ctx):
        message_lines = []
        for speaker in speakers:
            name = speaker["name"]
            styles = ", ".join(
                [f"{style['name']} (ID: {style['id']})" for style in speaker["styles"]]
            )
            message_lines.append(f"**{name}** {styles}")
        await ctx.send("\n".join(message_lines))
