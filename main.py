import discord
from discord.ext import commands
import os
from settings import USER_DEFAULT_STYLE_ID, NOTIFY_STYLE_ID, MAX_MESSAGE_LENGTH
from utils import (
    speakers,
    speaker_settings,
    get_style_details,
    save_style_settings,
    replace_content,
)
from voice import (
    process_playback_queue,
    text_to_speech,
    clear_playback_queue,
)


# Initialize bot
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.voice_states = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


current_voice_client = None


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    await bot.change_presence(activity=discord.Game(name="待機中 | !helpでヘルプ"))
    for guild in bot.guilds:
        bot.loop.create_task(process_playback_queue(str(guild.id)))


@bot.event
async def on_message(message):
    guild_id = str(message.guild.id)

    # ボット自身のメッセージは無視
    if message.author == bot.user:
        return

    # コマンド処理を妨げないようにする
    await bot.process_commands(message)

    # ボイスチャンネルに接続されていない、またはメッセージがコマンドの場合は無視
    voice_client = message.guild.voice_client
    # 設定されたテキストチャンネルIDを取得（存在しない場合はNone）
    allowed_text_channel_id = speaker_settings.get(guild_id, {}).get("text_channel")
    if (
        not voice_client
        or not voice_client.channel
        or not message.author.voice
        or message.author.voice.channel != voice_client.channel
        or message.content.startswith("!")
        or str(message.channel.id)
        != allowed_text_channel_id  # メッセージが指定されたテキストチャンネルからでなければ無視
    ):
        return

    if len(message.content) > MAX_MESSAGE_LENGTH:
        # テキストチャンネルに警告を送信
        await message.channel.send(
            f"申し訳ありません、メッセージが長すぎて読み上げられません！（最大 {MAX_MESSAGE_LENGTH} 文字）"
        )
        return  # このメッセージのTTS処理をスキップ

    guild_id = str(message.guild.id)
    # Initialize default settings for the server if none exist
    if guild_id not in speaker_settings:
        speaker_settings[guild_id] = {"user_default": USER_DEFAULT_STYLE_ID}

    # Use get to safely access 'user_default' key
    user_default_style_id = speaker_settings[guild_id].get(
        "user_default", USER_DEFAULT_STYLE_ID
    )

    style_id = speaker_settings.get(str(message.author.id), user_default_style_id)

    # メッセージ内容を置換
    message_content = await replace_content(message.content, message)
    # テキストメッセージがある場合、それに対する音声合成を行います。
    if message_content.strip():
        await text_to_speech(voice_client, message_content, style_id, guild_id)

    # 添付ファイルがある場合、「ファイルが投稿されました」というメッセージに対する音声合成を行います。
    if message.attachments:
        file_message = "ファイルが投稿されました。"
        await text_to_speech(voice_client, file_message, style_id, guild_id)


@bot.event
async def on_voice_state_update(member, before, after):
    guild_id = str(member.guild.id)
    # ボット自身の状態変更を無視
    if member == bot.user:
        return

    # ボットが接続しているボイスチャンネルを取得
    voice_client = member.guild.voice_client

    # ボットがボイスチャンネルに接続していなければ何もしない
    if not voice_client or not voice_client.channel:
        return

    # ボイスチャンネルに接続したとき
    if before.channel != voice_client.channel and after.channel == voice_client.channel:
        message = f"{member.display_name}さんが入室しました。"
        notify_style_id = speaker_settings.get(str(member.guild.id), {}).get(
            "notify", NOTIFY_STYLE_ID
        )
        await text_to_speech(voice_client, message, notify_style_id, guild_id)

    # ボイスチャンネルから切断したとき
    elif (
        before.channel == voice_client.channel and after.channel != voice_client.channel
    ):
        message = f"{member.display_name}さんが退出しました。"
        notify_style_id = speaker_settings.get(str(member.guild.id), {}).get(
            "notify", NOTIFY_STYLE_ID
        )
        await text_to_speech(voice_client, message, notify_style_id, guild_id)

    # ボイスチャンネルに誰もいなくなったら自動的に切断します。
    if after.channel is None and member.guild.voice_client:
        # ボイスチャンネルにまだ誰かいるか確認します。
        if not any(not user.bot for user in before.channel.members):
            # 現在の読み上げを停止する
            if current_voice_client and current_voice_client.is_playing():
                current_voice_client.stop()

            # キューをクリアする
            await clear_playback_queue(guild_id)
            if (
                guild_id in speaker_settings
                and "text_channel" in speaker_settings[guild_id]
            ):
                # テキストチャンネルIDの設定をクリア
                del speaker_settings[guild_id]["text_channel"]
                save_style_settings()  # 変更を保存
                print(f"テキストチャンネルの設定をクリアしました: サーバーID {guild_id}")
            await member.guild.voice_client.disconnect()


@bot.command(
    name="_userdefaultstyle",
    help="ユーザーのデフォルトスタイルを表示または設定します。使用法: !_userdefaultstyle [スタイルID]",
)
async def user_default_style(ctx, style_id: int = None):
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
    name="notifystyle", help="入退室通知のスタイルを表示または設定します。使用法: !notifystyle [スタイルID]"
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
    notify_style_id = speaker_settings.get(guild_id, {}).get("default", NOTIFY_STYLE_ID)
    notify_speaker, notify_default_name = get_style_details(notify_style_id, "デフォルト")

    response = f"**{ctx.guild.name}の通知スタイル:** {notify_speaker} {notify_default_name} (ID: {notify_style_id})\n"
    await ctx.send(response)


@bot.command(name="mystyle", help="あなたの現在のスタイルを表示または設定します。使用法: !mystyle [スタイルID]")
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
        await text_to_speech(voice_client, welcome_message, notify_style_id, guild_id)


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


@bot.command(name="showstyles", help="利用可能なスタイルIDの一覧を表示します。")
async def show_styles(ctx):
    message_lines = []
    for speaker in speakers:
        name = speaker["name"]
        styles = ", ".join(
            [f"{style['name']} (ID: {style['id']})" for style in speaker["styles"]]
        )
        message_lines.append(f"**{name}** {styles}")
    await ctx.send("\n".join(message_lines))


if __name__ == "__main__":
    bot.run(os.getenv("DISCORD_BOT_TOKEN"))
