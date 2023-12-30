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
from voice import clear_playback_queue, text_to_speech
from discord import app_commands


import discord
from discord.ext import commands


async def handle_style_command(interaction, style_id: int, type: str = None):
    guild_id = str(interaction.guild_id)
    user_id = str(interaction.user.id)
    user_display_namename = interaction.user.display_name  # ユーザー名を取得

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
        await interaction.response.send_message(
            "🔊 以下は現在のスタイル設定です:\n" + "\n".join(messages)
        )
        return
    # スタイルIDが指定されている場合は設定を更新
    if style_id is not None:
        valid, speaker_name, style_name = validate_style_id(style_id)
        if not valid:
            await interaction.response.send_message(
                f"⚠️ スタイルID {style_id} は無効です。正しいIDを入力してください。"
            )
            return

        # スタイルを更新
        update_style_setting(guild_id, user_id, style_id, type)
        await interaction.response.send_message(
            f"✅ {type_description[type]}のスタイルが「{speaker_name} {style_name}」(スタイルID: {style_id})に更新されました。"
        )
        return

    # 現在のスタイル設定を表示
    current_style_id, speaker_name, style_name = get_current_style_details(
        guild_id, user_id, type
    )
    await interaction.response.send_message(
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
    # @bot.tree.command(
    #     name="style",
    #     guild=TEST_GUILD_ID,
    #     description="スタイルを表示または設定します。",
    # )
    # async def style(interaction, type: str = None, style_id: int = None):
    #     valid_types = ["user_default", "notify", "user", None]
    #     if type not in valid_types:
    #         await interaction.response.send_message(
    #             f"⚠️ 指定されたタイプが無効です。有効なタイプは以下の通りです: {', '.join(valid_types[:-1])}"
    #         )
    #         return

    #     # コードを共通化し、異なるスタイルタイプに対応
    #     await handle_style_command(interaction, style_id, type)
    @bot.command(name="remove_command")
    async def remove_command(ctx, command_name: str):
        # このコマンドを使用すると、指定されたコマンド名のスラッシュコマンドを削除します。
        guild_id = ctx.guild.id  # コマンドを削除したいギルドのID
        guild = discord.Object(id=guild_id)
        for cmd in await bot.tree.fetch_commands(guild=guild):
            if cmd.name == command_name:
                await bot.tree.remove_command(cmd.name, guild=guild)
                await ctx.send(f"コマンド {command_name} を削除しました。")
                break
        else:
            await ctx.send(f"コマンド {command_name} が見つかりませんでした。")
    @bot.command(name="remove_global_command")
    async def remove_global_command(ctx, command_name: str):
        try:
            # Fetch all global commands
            commands = await bot.tree.fetch_commands()  
            for cmd in commands:
                if cmd.name == command_name:
                    # Remove the command
                    await bot.tree.remove_command(cmd)  
                    await ctx.send(f"グローバルコマンド {command_name} を削除しました。")
                    return
            # If the command wasn't found
            await ctx.send(f"グローバルコマンド {command_name} が見つかりませんでした。")
        except Exception as e:
            # If there was an error during the process
            await ctx.send(f"コマンドを削除中にエラーが発生しました: {e}")




    @bot.tree.command(
        name="join", guild=TEST_GUILD_ID, description="ボットをボイスチャンネルに接続し、読み上げを開始します。"
    )
    async def join(interaction: discord.Interaction):
        # defer the response to keep the interaction alive
        await interaction.response.defer()

        try:
            if interaction.user.voice and interaction.user.voice.channel:
                channel = interaction.user.voice.channel
                voice_client = await channel.connect(self_deaf=True)
                # 接続成功時の処理
                # 接続メッセージの読み上げ
                welcome_message = "読み上げを開始します。"

                guild_id = str(interaction.guild_id)
                text_channel_id = str(interaction.channel_id)  # このコマンドを使用したテキストチャンネルID

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
                await interaction.followup.send("ボイスチャンネルに接続し、読み上げを開始しました。")
            else:
                await interaction.followup.send(
                    "ボイスチャンネルに接続できませんでした。ユーザーがボイスチャンネルにいることを確認してください。"
                )
        except Exception as e:
            # エラーメッセージをユーザーに通知
            await interaction.followup.send(f"接続中にエラーが発生しました: {e}")

    @bot.tree.command(
        name="leave", guild=TEST_GUILD_ID, description="ボットをボイスチャンネルから切断します。"
    )
    async def leave(interaction: discord.Interaction):
        if interaction.guild.voice_client:
            guild_id = str(interaction.guild_id)
            await clear_playback_queue(guild_id)  # キューをクリア
            if "text_channel" in speaker_settings.get(guild_id, {}):
                del speaker_settings[guild_id]["text_channel"]
            await interaction.guild.voice_client.disconnect()  # 切断
            await interaction.response.send_message("ボイスチャンネルから切断しました。")

    @bot.tree.command(
        name="list_styles", guild=TEST_GUILD_ID, description="利用可能なスタイルIDの一覧を表示します。"
    )
    async def list_styles(interaction: discord.Interaction):
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
            await interaction.response.send_message(embed=embed)

    # gender_categories = {
    #     "男性": [
    #         "玄野武宏",
    #         "白上虎太郎",
    #         "青山龍星",
    #         "剣崎雌雄",
    #         "ちび式じい",
    #         "†聖騎士 紅桜†",
    #         "雀松朱司",
    #         "麒ヶ島宗麟",
    #         "栗田まろん",
    #     ],
    #     "女性": [
    #         "四国めたん",
    #         "ずんだもん",
    #         "春日部つむぎ",
    #         "雨晴はう",
    #         "波音リツ",
    #         "冥鳴ひまり",
    #         "九州そら",
    #         "もち子さん",
    #         "WhiteCUL",
    #         "後鬼",
    #         "No.7",
    #         "櫻歌ミコ",
    #         "小夜/SAYO",
    #         "ナースロボ＿タイプＴ",
    #         "春歌ナナ",
    #         "猫使アル",
    #         "猫使ビィ",
    #         "中国うさぎ",
    #         "あいえるたん",
    #         "満別花丸",
    #         "琴詠ニア",
    #     ],
    # }
    # first_persons = {
    #     "わたくし": ["四国めたん"],
    #     "ずんだもん": ["ずんだもん"],
    #     "僕": ["ずんだもん", "雨晴はう", "剣崎雌雄", "No.7", "雀松朱司", "栗田まろん", "猫使アル", "猫使ビィ", "満別花丸"],
    #     "あーし": ["春日部つむぎ"],
    #     "あたし": ["波音リツ"],
    #     "おれ": ["白上虎太郎", "猫使アル", "玄野武宏", "青山龍星"],
    #     "私": [
    #         "冥鳴ひまり",
    #         "もち子さん",
    #         "No.7",
    #         "櫻歌ミコ",
    #         "麒ヶ島宗麟",
    #         "猫使ビィ",
    #         "琴詠ニア",
    #         "WhiteCUL",
    #         "後鬼",
    #         "ナースロボ＿タイプＴ",
    #         "春歌ナナ",
    #         "中国うさぎ",
    #         "あいえるたん",
    #     ],
    #     "まーくつー": ["九州そら"],
    #     "もち子さん": ["もち子さん"],
    #     "ワテ": ["後鬼"],
    #     "わし": ["ちび式じい"],
    #     "ミコ": ["櫻歌ミコ"],
    #     "小夜": ["小夜/SAYO"],
    #     "我": ["†聖騎士 紅桜†"],
    #     "ナナ": ["春歌ナナ"],
    #     "アル": ["猫使アル"],
    #     "ビィ": ["猫使ビィ"],
    #     "あいえるたん": ["あいえるたん"],
    # }
    first_persons = {
        "私": ["冥鳴ひまり", "もち子さん", "No.7", "櫻歌ミコ", "麒ヶ島宗麟", "猫使ビィ", "琴詠ニア"],
        "わたし": ["WhiteCUL", "後鬼", "ナースロボ＿タイプＴ", "春歌ナナ", "中国うさぎ", "あいえるたん"],
        "わたくし": ["四国めたん"],
        "あーし": ["春日部つむぎ"],
        "あたし": ["波音リツ"],
        "僕": ["ずんだもん", "雨晴はう", "剣崎雌雄", "No.7", "雀松朱司", "栗田まろん"],
        "ぼく": ["満別花丸"],
        "ボク": ["猫使アル", "猫使ビィ"],
        "おれ": ["白上虎太郎", "猫使アル"],
        "俺": ["玄野武宏"],
        "オレ": ["青山龍星"],
        "ワテ": ["後鬼"],
        "我": ["†聖騎士 紅桜†"],
        "わし": ["ちび式じい"],
        "ずんだもん": ["ずんだもん"],
        "まーくつー": ["九州そら"],
        "もち子さん": ["もち子さん"],
        "ミコ": ["櫻歌ミコ"],
        "小夜": ["小夜/SAYO"],
        "ナナ": ["春歌ナナ"],
        "アル": ["猫使アル"],
        "ビィ": ["猫使ビィ"],
        "あいえるたん": ["あいえるたん"],
    }

    @bot.tree.command(
        name="choose_first_person", guild=TEST_GUILD_ID, description="一人称を選択します。"
    )
    @app_commands.choices(
        first_person=[
            app_commands.Choice(name=fp, value=fp) for fp in first_persons.keys()
        ]
    )
    async def choose_first_person(interaction: discord.Interaction, first_person: str):
        selected_fp = first_person
        characters = first_persons[selected_fp]

        # キャラクターが一つだけの場合、自動的に選択
        if len(characters) == 1:
            selected_char = characters[0]
            styles = [
                style
                for speaker in speakers
                if speaker["name"] == selected_char
                for style in speaker["styles"]
            ]
            # スタイルも一つだけならそれも自動選択
            if len(styles) == 1:
                selected_style = styles[0]
                await interaction.response.send_message(
                    f"{selected_char}のスタイル「{selected_style['name']}」(ID: {selected_style['id']})が自動的に選択されました。",
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    f"一人称「{first_person}」には{selected_char}が該当します。スタイルを選んでください。",
                    view=StyleView(styles),
                )
        else:
            await interaction.response.send_message(
                f"{selected_fp}に対応するキャラクターを選んでください。", view=CharacterView(characters)
            )

    class CharacterView(discord.ui.View):
        def __init__(self, characters):
            super().__init__()
            self.add_item(CharacterSelect(characters))

    class CharacterSelect(discord.ui.Select):
        def __init__(self, characters):
            options = [
                discord.SelectOption(label=char, value=char) for char in characters
            ]
            super().__init__(
                placeholder="キャラクターを選択...", min_values=1, max_values=1, options=options
            )

        async def callback(self, interaction: discord.Interaction):
            selected_char = self.values[0]
            styles = [
                style
                for speaker in speakers
                if speaker["name"] == selected_char
                for style in speaker["styles"]
            ]

            # スタイルが一つだけの場合、自動的に選択
            if len(styles) == 1:
                selected_style = styles[0]
                await interaction.response.send_message(
                    f"{selected_char}のスタイル「{selected_style['name']}」(ID: {selected_style['id']})が自動的に選択されました。",
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    f"{selected_char}のスタイルを選んでください。", view=StyleView(styles)
                )

    class StyleView(discord.ui.View):
        def __init__(self, styles):
            super().__init__()
            self.add_item(StyleSelect(styles))

    class StyleSelect(discord.ui.Select):
        def __init__(self, styles):
            self.styles = styles  # ここでスタイル情報を保存します
            options = [
                discord.SelectOption(label=style["name"], value=style["id"])
                for style in styles
            ]
            super().__init__(
                placeholder="スタイルを選択...", min_values=1, max_values=1, options=options
            )

        async def callback(self, interaction: discord.Interaction):
            selected_style = self.values[0]
            # データ型を確認し、必要に応じて変換
            selected_style = int(selected_style)  # これでselected_styleを整数に変換

            # 保存されたスタイル情報からスタイル名を取得
            style_name = next(
                (
                    style["name"]
                    for style in self.styles
                    if int(style["id"]) == selected_style  # ここでstyle["id"]も整数に変換
                ),
                f"不明なスタイル (ID: {selected_style})",
            )

            # ユーザーのスタイル選択を更新するロジックをここに実装
            await interaction.response.send_message(
                f"スタイル「{style_name}」(ID: {selected_style})が選択されました。", ephemeral=True
            )

    class SpeakerSelect(discord.ui.Select):
        def __init__(self, speakers):
            options = [
                discord.SelectOption(label=speaker["name"], value=speaker["name"])
                for speaker in speakers
            ]
            super().__init__(
                placeholder="スピーカーを選択...", min_values=1, max_values=1, options=options
            )

        async def callback(self, interaction: discord.Interaction):
            selected_speaker = self.values[0]
            styles = next(
                (
                    speaker["styles"]
                    for speaker in speakers
                    if speaker["name"] == selected_speaker
                ),
                [],
            )
            self.view.clear_items()
            self.view.add_item(StyleSelect(styles))
            await interaction.response.edit_message(view=self.view)

    class StyleSelect(discord.ui.Select):
        def __init__(self, styles):
            options = [
                discord.SelectOption(label=style["name"], value=str(style["id"]))
                for style in styles
            ]
            super().__init__(
                placeholder="スタイルを選択...", min_values=1, max_values=1, options=options
            )

        async def callback(self, interaction: discord.Interaction):
            selected_style_id = int(self.values[0])
            # Update user's settings here with the selected style ID
            await interaction.response.send_message(
                f"スタイルが更新されました。ID: {selected_style_id}", ephemeral=True
            )

    class StyleView(discord.ui.View):
        def __init__(self, speakers):
            super().__init__()
            self.add_item(SpeakerSelect(speakers))

    @bot.tree.command(name="style", description="スタイルを表示または設定します。")
    @app_commands.choices(
        style_type=[
            app_commands.Choice(name="ユーザーデフォルト", value="user_default"),
            app_commands.Choice(name="VC入退室時", value="notify"),
            app_commands.Choice(name="ユーザー", value="user"),
        ]
    )
    async def style(interaction: discord.Interaction, style_type: str):
        # Here, you can handle the initial response based on the style_type selected
        # For instance, fetch the current setting for the user or provide additional instructions
        # ...
        await interaction.response.send_message(
            f"{style_type}のスピーカーを選択してください。", view=StyleView(speakers)
        )
