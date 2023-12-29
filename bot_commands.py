import discord
from discord.ext import commands
from settings import USER_DEFAULT_STYLE_ID, NOTIFY_DEFAULT_STYLE_ID
from utils import (
    speakers,
    speaker_settings,
    save_style_settings,
    get_style_details,
    validate_style_id,
)
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


async def handle_style_command(ctx, style_id: int, type: str):
    guild_id = str(ctx.guild.id)
    user_id = str(ctx.author.id)

    # スタイルタイプに応じた説明を定義
    type_description = {
        "default": "デフォルト",
        "notify": "通知",
        "user": "ユーザー"
    }

    # スタイルIDが指定されている場合は設定を更新
    if style_id is not None:
        valid, speaker_name, style_name = validate_style_id(style_id)
        if not valid:
            await ctx.send(f"スタイルID {style_id} は無効です。")
            return

        # スタイルを更新
        update_style_setting(guild_id, user_id, style_id, type)
        await ctx.send(
            f"{type_description[type]}スタイルを「{speaker_name} {style_name}」(スタイルID: {style_id})に設定しました。"
        )
        return
    
    # 現在のスタイル設定を表示
    current_style_id, speaker_name, style_name = get_current_style_details(
        guild_id, user_id, type
    )
    await ctx.send(f"現在の{type_description[type]}スタイル: {speaker_name} {style_name} (スタイルID: {current_style_id})")


def update_style_setting(guild_id, user_id, style_id, type):
    if type == "default":
        speaker_settings[guild_id]["user_default"] = style_id
    elif type == "notify":
        speaker_settings[guild_id]["notify"] = style_id
    elif type == "user":
        speaker_settings[user_id] = style_id
    save_style_settings()


def get_current_style_details(guild_id, user_id, type):
    if type == "default":
        style_id = speaker_settings[guild_id].get("user_default", USER_DEFAULT_STYLE_ID)
    elif type == "notify":
        style_id = speaker_settings[guild_id].get("notify", NOTIFY_DEFAULT_STYLE_ID)
    elif type == "user":
        style_id = speaker_settings.get(user_id, USER_DEFAULT_STYLE_ID)

    speaker_name, style_name = get_style_details(style_id)
    return style_id, speaker_name, style_name


def setup_commands(bot):
    @bot.command(name="style", help="スタイルを表示または設定します。")
    async def style(ctx, type: str = "user", style_id: int = None):
        valid_types = ["default", "notify", "user"]
        if type not in valid_types:
            await ctx.send(f"無効なタイプが指定されました。有効なタイプ: {', '.join(valid_types)}")
            return

        # コードを共通化し、異なるスタイルタイプに対応
        await handle_style_command(ctx, style_id, type)

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
                "notify", NOTIFY_DEFAULT_STYLE_ID
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
        message_lines = ["```"]  # コードブロックの開始
        # メッセージの説明を追加
        message_lines.append("以下のリストにおいて、カッコ内の数字はスタイルIDを表します。")
        for speaker in speakers:
            name = speaker["name"]
            styles = ", ".join(
                f"{style['name']}({style['id']})" for style in speaker["styles"]
            )
            message_lines.append(f"{name}: {styles}")
        message_lines.append("```")  # コードブロックの終了
        # メッセージを送信
        await ctx.send("\n".join(message_lines))
