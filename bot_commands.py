import discord
from discord.ext import commands
from settings import TEST_GUILD_ID, USER_DEFAULT_STYLE_ID, NOTIFY_DEFAULT_STYLE_ID
from utils import (
    speakers,
    speaker_settings,
    save_style_settings,
    get_style_details,
    validate_style_id,
)
from voice import text_to_speech
from discord import app_commands


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
                command_name = f"`!{command.name}`"
                alias_text = (
                    f" (または: {'|'.join(f'`!{a}`' for a in command.aliases)})"
                    if command.aliases
                    else ""
                )
                command_entries.append(
                    f"- {command_name}{alias_text}: {command.short_doc}"
                )
            if command_entries:
                cog_name = cog.qualified_name if cog else "一般コマンド"
                embed.add_field(
                    name=cog_name, value="\n".join(command_entries), inline=False
                )

        channel = self.get_destination()
        await channel.send(embed=embed)

    async def send_command_help(self, command):
        embed = discord.Embed(title=f"!{command.name}", color=0x00FF00)

        if command.name == "style":
            embed.description = (
                "`!style`コマンドの使用法:\n"
                "`!style [type] [style_id]`\n\n"
                "- `type`: 設定するスタイルのタイプ。`user_default`, `notify`, または `user` から選択。\n"
                "- `style_id`: 使用したいスタイルのID。省略すると現在の設定が表示されます。\n\n"
                "例:\n"
                "- サーバーのユーザーデフォルトスタイルをID 1に設定: `!style user_default 1`\n"
                "- サーバーの入退室通知スタイルをID 2に設定: `!style notify 2`\n"
                "- あなたのスタイルをID 3に設定: `!style user 3`\n\n"
                "`style_id`の詳細や一覧は `!list_styles` で確認できます。"
            )
        else:
            embed.add_field(name="説明", value=command.help, inline=False)
            embed.add_field(
                name="使用法",
                value=f"`{self.get_command_signature(command)}`",
                inline=False,
            )

        channel = self.get_destination()
        await channel.send(embed=embed)

    async def command_not_found(self, string):
        return f'"{string}"というコマンドは見つかりませんでした。'

    async def send_error_message(self, error):
        channel = self.get_destination()
        await channel.send(error)


async def handle_style_command(ctx, style_id: int, type: str = None):
    guild_id = str(ctx.guild.id)
    guild_name = ctx.guild.name  # ギルド名を取得
    user_id = str(ctx.author.id)
    user_display_namename = ctx.author.display_name  # ユーザー名を取得

    # スタイルタイプに応じた説明を定義
    type_description = {
        "user_default": f"ユーザーデフォルト",
        "notify": f"VC入退室時",
        "user": f"{user_display_namename}",
    }

    # スタイルIDが指定されていない場合、全ての設定を表示
    if style_id is None and type is None:
        messages = []
        for t in type_description.keys():
            style_id, speaker_name, style_name = get_current_style_details(
                guild_id, user_id, t
            )
            messages.append(
                f"**{type_description[t]}**: {speaker_name} {style_name} (スタイルID: {style_id})"
            )
        await ctx.send("🔊 以下は現在のスタイル設定です:\n" + "\n".join(messages))
        return
    # スタイルIDが指定されている場合は設定を更新
    if style_id is not None:
        valid, speaker_name, style_name = validate_style_id(style_id)
        if not valid:
            await ctx.send(f"⚠️ スタイルID {style_id} は無効です。正しいIDを入力してください。")
            return

        # スタイルを更新
        update_style_setting(guild_id, user_id, style_id, type)
        await ctx.send(
            f"✅ {type_description[type]}のスタイルが「{speaker_name} {style_name}」(スタイルID: {style_id})に更新されました。"
        )
        return

    # 現在のスタイル設定を表示
    current_style_id, speaker_name, style_name = get_current_style_details(
        guild_id, user_id, type
    )
    await ctx.send(
        f"ℹ️ 現在の{type_description[type]}のスタイルは「{speaker_name} {style_name}」(スタイルID: {current_style_id})です。"
    )


def update_style_setting(guild_id, user_id, style_id, type):
    if type == "user_default":
        speaker_settings[guild_id]["user_default"] = style_id
    elif type == "notify":
        speaker_settings[guild_id]["notify"] = style_id
    elif type == "user":
        speaker_settings[user_id] = style_id
    save_style_settings()


def get_current_style_details(guild_id, user_id, type):
    if type == "user_default":
        style_id = speaker_settings[guild_id].get("user_default", USER_DEFAULT_STYLE_ID)
    elif type == "notify":
        style_id = speaker_settings[guild_id].get("notify", NOTIFY_DEFAULT_STYLE_ID)
    elif type == "user":
        style_id = speaker_settings.get(user_id, USER_DEFAULT_STYLE_ID)

    speaker_name, style_name = get_style_details(style_id)
    return style_id, speaker_name, style_name


def setup_commands(bot):
    @bot.command(name="style", help="スタイルを表示または設定します。詳細は `!help style` で確認。")
    async def style(ctx, type: str = None, style_id: int = None):
        valid_types = ["user_default", "notify", "user", None]
        if type not in valid_types:
            await ctx.send(
                f"⚠️ 指定されたタイプが無効です。有効なタイプは以下の通りです: {', '.join(valid_types[:-1])}"
            )
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
        embeds = []
        embed = discord.Embed(title="利用可能なスタイルIDの一覧", color=0x00FF00)
        embed.description = "各スピーカーと利用可能なスタイルのIDです。"
        field_count = 0

        for speaker in speakers:
            name = speaker["name"]
            styles = "\n".join(
                f"- {style['name']} `{style['id']}`" for style in speaker["styles"]
            )

            if field_count < 25:
                embed.add_field(name=name, value=styles, inline=True)
                field_count += 1
            else:
                embeds.append(embed)
                embed = discord.Embed(title="利用可能なスタイルIDの一覧 (続き)", color=0x00FF00)
                embed.add_field(name=name, value=styles, inline=True)
                field_count = 1  # Reset for the new embed

        # Add the last embed
        embeds.append(embed)

        for embed in embeds:
            await ctx.send(embed=embed)

    # スタイルタイプに応じた説明を定義
    type_description = {
        "user_default": f"ユーザーデフォルト",
        "notify": f"VC入退室時",
        "user": f"あなた",
    }
    # Define choices for type
    type_choices = [
        app_commands.Choice(
            name="user_default", value=type_description["user_default"]
        ),
        app_commands.Choice(name="notify", value=type_description["notify"]),
        app_commands.Choice(name="user", value=type_description["user"]),
    ]
    # Dynamically generate style ID choices based on the speakers data
    gender_categories = {
        '男性': ['玄野武宏', '白上虎太郎', '青山龍星', '剣崎雌雄','ちび式じい','†聖騎士 紅桜†','雀松朱司','麒ヶ島宗麟','栗田まろん'],
        '女性': ['四国めたん', 'ずんだもん', '春日部つむぎ', '雨晴はう', '波音リツ', '冥鳴ひまり', '九州そら', 'もち子さん','WhiteCUL','後鬼','No.7','櫻歌ミコ','小夜/SAYO','ナースロボ＿タイプＴ','春歌ナナ','猫使アル','猫使ビィ','中国うさぎ','あいえるたん','満別花丸','琴詠ニア'],
    }
    first_persons = {
        'わたくし': ['四国めたん'],
        'ずんだもん': ['ずんだもん'],
        '僕': ['ずんだもん','雨晴はう', '剣崎雌雄','No.7','雀松朱司','栗田まろん'],
        'あーし': ['春日部つむぎ'],
        'あたし': ['波音リツ'],
        '俺': ['玄野武宏'],
        'おれ': ['白上虎太郎','猫使アル'],
        'オレ': ['青山龍星'],
        '私': ['冥鳴ひまり', 'もち子さん','No.7','櫻歌ミコ','麒ヶ島宗麟','猫使ビィ','琴詠ニア'],
        'まーくつー': ['九州そら'],
        'もち子さん': ['もち子さん'],
        'わたし': ['WhiteCUL','後鬼','ナースロボ＿タイプＴ','春歌ナナ','中国うさぎ','あいえるたん'],
        'ワテ': ['後鬼'],
        'わし': ['ちび式じい'],
        'ミコ': ['櫻歌ミコ'],
        '小夜':['小夜/SAYO'],
        '我':['†聖騎士 紅桜†'],
        'ナナ': ['春歌ナナ'],
        'アル':['猫使アル'],
        'ボク':['猫使アル','猫使ビィ'],
        'ビィ':['猫使ビィ'],
        'あいえるたん':['あいえるたん'],
        'ぼく': ['満別花丸']
    }
    # スピーカーごとに選択肢を作成
    speaker_choices = []
    style_id_choices = []
    for speaker in speakers:
        speaker_choice = app_commands.Choice(
            name=speaker["name"], value=speaker["name"]
        )
        speaker_choices.append(speaker_choice)
        # 各スピーカーのスタイルから選択肢を作成
        for _style in speaker["styles"]:
            style_choice = app_commands.Choice(  # 修正された変数名
                name=f"{_style['name']}", value=_style["id"]
            )
            style_id_choices.append(style_choice)  # 修正された行
    print(len(speaker_choices))
    print(len(style_id_choices))
    @bot.tree.command(name='choose_style',guild=TEST_GUILD_ID, description='スタイルを選択します。')
    async def choose_style(interaction: discord.Interaction):
        # Create first person selection options
        options = [discord.SelectOption(label=fp, value=fp) for fp in first_persons.keys()]
        # Prompt the user to select a first person
        await interaction.response.send_message('一人称を選択してください。', view=FirstPersonView(options))
    # @bot.tree.command(guild=TEST_GUILD_ID, description='一人称を選択します。')    
    # @bot.tree.command(guild=TEST_GUILD_ID, description="スタイルを表示または設定します。")
    # @app_commands.choices(
    #     type=type_choices, speaker=speaker_choices, style_id=style_id_choices
    # )
    # async def style(
    #     interaction: discord.Interaction,
    #     type: str = None,
    #     speaker: str = None,
    #     style_id: int = None,
    # ):
    #     valid_types = ["user_default", "notify", "user", None]
    #     # Check if the type is valid
    #     if type not in valid_types:
    #         await interaction.response.send_message(
    #             f"⚠️ 指定されたタイプが無効です。", ephemeral=True
    #         )
    #         return

    #     # Ensure a style_id is provided for certain types
    #     if type in ["notify", "user"] and not style_id:
    #         await interaction.response.send_message(f"⚠️ スタイルIDが必要です。", ephemeral=True)
    #         return

    #     # Define valid types
    #     valid_types = ["user_default", "notify", "user"]

    #     # Check if the type is valid
    #     if type not in valid_types:
    #         await interaction.response.send_message(
    #             f"⚠️ 指定されたタイプが無効です。", ephemeral=True
    #         )
    #         return

    #     if not validate_style_id(style_id):
    #         await interaction.response.send_message(
    #             f"⚠️ 指定されたスタイルIDが無効です。", ephemeral=True
    #         )
    #         return

    #     # Ensure a style_id is provided for certain types
    #     if type in ["notify", "user"] and not style_id:
    #         await interaction.response.send_message(f"⚠️ スタイルIDが必要です。", ephemeral=True)
    #         return

    #     # Check if the provided style_id is valid
    #     if style_id and style_id not in [choice.value for choice in style_id_choices]:
    #         await interaction.response.send_message(
    #             f"⚠️ 指定されたスタイルIDが無効です。", ephemeral=True
    #         )
    #         return

    #     # Handle the style setting logic here...
    #     # For example, update the user's preference in your database

    #     await interaction.response.send_message(
    #         f"✅ スタイルが更新されました。スタイルID: {style_id if style_id else 'Default'}",
    #         ephemeral=True,
    #     )
    class FirstPersonView(discord.ui.View):
        def __init__(self, options):
            super().__init__()
            self.add_item(FirstPersonSelect(options))

    class FirstPersonSelect(discord.ui.Select):
        def __init__(self, options):
            super().__init__(placeholder='一人称を選択...', min_values=1, max_values=1, options=options)

        async def callback(self, interaction: discord.Interaction):
            # Filter the characters based on the selected first person
            selected_fp = self.values[0]
            characters = first_persons[selected_fp]
            # Prompt the user to select a character next
            await interaction.response.send_message(f'{selected_fp}に対応するキャラクターを選んでください。', view=CharacterView(characters))

    class CharacterView(discord.ui.View):
        def __init__(self, characters):
            super().__init__()
            self.add_item(CharacterSelect(characters))

    class CharacterSelect(discord.ui.Select):
        def __init__(self, characters):
            options = [discord.SelectOption(label=char, value=char) for char in characters]
            super().__init__(placeholder='キャラクターを選択...', min_values=1, max_values=1, options=options)

        async def callback(self, interaction: discord.Interaction):
            # Filter the styles based on the selected character
            selected_char = self.values[0]
            styles = [style for speaker in speakers if speaker["name"] == selected_char for style in speaker["styles"]]
            # Prompt the user to select a style next
            await interaction.response.send_message(f'{selected_char}のスタイルを選んでください。', view=StyleView(styles))

    class StyleView(discord.ui.View):
        def __init__(self, styles):
            super().__init__()
            self.add_item(StyleSelect(styles))

    class StyleSelect(discord.ui.Select):
        def __init__(self, styles):
            options = [discord.SelectOption(label=style['name'], value=style['id']) for style in styles]
            super().__init__(placeholder='スタイルを選択...', min_values=1, max_values=1, options=options)

        async def callback(self, interaction: discord.Interaction):
            # Set the selected style for the user
            selected_style = self.values[0]
            # Implement your logic to update the user's style preference
            await interaction.response.send_message(f'スタイルID {selected_style} が選択されました。', ephemeral=True)

