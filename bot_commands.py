import discord
from discord import app_commands
from settings import (
    FIRST_PERSON_DICTIONARY,
    TEST_GUILD_ID,
    USER_DEFAULT_STYLE_ID,
    NOTIFY_DEFAULT_STYLE_ID,
)
from utils import (
    speakers,
    speaker_settings,
    save_style_settings,
    get_style_details,
    validate_style_id,
)
from voice import clear_playback_queue, text_to_speech


class CharacterView(discord.ui.View):
    def __init__(self, characters, voice_scope):
        super().__init__()
        self.add_item(CharacterSelect(characters, voice_scope))


class CharacterSelect(discord.ui.Select):
    def __init__(self, characters, voice_scope):
        self.voice_scope = voice_scope
        options = [discord.SelectOption(label=char, value=char) for char in characters]
        super().__init__(placeholder="キャラクターを選択...", options=options)

    async def callback(self, interaction: discord.Interaction):
        selected_char = self.values[0]
        styles = [
            style
            for speaker in speakers
            if speaker["name"] == selected_char
            for style in speaker["styles"]
        ]
        await interaction.response.send_message(
            f"{selected_char}のスタイルを選んでください。",
            view=StyleView(styles, self.voice_scope),
        )


class StyleView(discord.ui.View):
    def __init__(self, styles, voice_scope):
        super().__init__()
        self.add_item(StyleSelect(styles, voice_scope))


class StyleSelect(discord.ui.Select):
    def __init__(self, styles, voice_scope):
        self.styles = styles
        self.voice_scope = voice_scope
        options = [
            discord.SelectOption(label=style["name"], value=style["id"])
            for style in styles
        ]
        super().__init__(placeholder="スタイルを選択...", options=options)

    async def callback(self, interaction: discord.Interaction):
        selected_style_id = int(self.values[0])
        update_message = await handle_style_command(
            interaction, selected_style_id, self.voice_scope
        )
        if update_message:
            await interaction.followup.send(update_message, ephemeral=True)


async def handle_style_command(interaction, style_id: int, voice_scope: str):
    guild_id = str(interaction.guild_id)
    user_id = str(interaction.user.id)
    voice_scope_description = {
        "user": interaction.user.display_name,
        "notify": "VC入退室時",
        "user_default": "ユーザーデフォルト",
    }

    try:
        if style_id is not None:
            valid, speaker_name, style_name = validate_style_id(style_id)
            if not valid:
                return f"スタイルID {style_id} は無効です。正しいIDを入力してください。"
            update_style_setting(guild_id, user_id, style_id, voice_scope)
            return f"{voice_scope_description[voice_scope]}の読み上げ音声が「{speaker_name} {style_name}」に更新されました。"

        current_style_id, speaker_name, style_name = get_current_style_details(
            guild_id, user_id, voice_scope
        )
        return f"現在の{voice_scope_description[voice_scope]}の読み上げ音声は「{speaker_name} {style_name}」です。"
    except Exception as e:
        return f"エラーが発生しました: {e}"


def update_style_setting(guild_id, user_id, style_id, voice_scope):
    if voice_scope == "user_default":
        speaker_settings[guild_id]["user_default"] = style_id
    elif voice_scope == "notify":
        speaker_settings[guild_id]["notify"] = style_id
    elif voice_scope == "user":
        speaker_settings[user_id] = style_id
    save_style_settings()


def get_current_style_details(guild_id, user_id, voice_scope):
    if voice_scope == "user_default":
        style_id = speaker_settings[guild_id].get("user_default", USER_DEFAULT_STYLE_ID)
    elif voice_scope == "notify":
        style_id = speaker_settings[guild_id].get("notify", NOTIFY_DEFAULT_STYLE_ID)
    elif voice_scope == "user":
        style_id = speaker_settings.get(user_id, USER_DEFAULT_STYLE_ID)

    speaker_name, style_name = get_style_details(style_id)
    return style_id, speaker_name, style_name


def setup_commands(bot):
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
        name="voice_config",
        guild=TEST_GUILD_ID,
        description="現在の読み上げキャラクターを表示、または一人称を選択し設定します。",
    )
    @app_commands.choices(
        voice_scope=[
            app_commands.Choice(name="あなた", value="user"),
            app_commands.Choice(name="VC入退室時", value="notify"),
            app_commands.Choice(name="ユーザーデフォルト", value="user_default"),
        ],
        first_person=[
            app_commands.Choice(name=fp, value=fp)
            for fp in FIRST_PERSON_DICTIONARY.keys()
        ],
    )
    async def voice_config(
        interaction: discord.Interaction,
        voice_scope: str = None,
        first_person: str = None,
    ):
        if first_person is None:
            await handle_style_command(interaction, None, voice_scope)
            return
        if voice_scope is None:
            characters = FIRST_PERSON_DICTIONARY[first_person]
            character_message = "\n".join(characters)
            await interaction.response.send_message(
                f"一人称「{first_person}」のキャラクター:\n{character_message}\n読み上げキャラクターを変更するには、その対象を指定してください。"
            )
            return

        selected_fp = first_person
        characters = FIRST_PERSON_DICTIONARY[selected_fp]

        if len(characters) == 1:
            selected_char = characters[0]
            styles = [  # stylesをここで定義
                style
                for speaker in speakers
                if speaker["name"] == selected_char
                for style in speaker["styles"]
            ]

            if len(styles) == 1:
                selected_style_id = styles[0]["id"]
                update_message = await handle_style_command(
                    interaction, selected_style_id, voice_scope
                )
                if update_message:
                    if interaction.response.is_done():
                        await interaction.followup.send(update_message)
                    else:
                        await interaction.response.send_message(update_message)

            else:
                # If there are multiple styles to choose from, let the user select
                await interaction.response.send_message(
                    f"一人称「{first_person}」のキャラクターは{selected_char}が該当します。スタイルを選んでください。",
                    view=StyleView(styles, voice_scope),
                )
        else:
            # If there are multiple characters to choose from, let the user select
            await interaction.response.send_message(
                f"一人称「{selected_fp}」のキャラクターに絞り込みました。キャラクターを選んでください。",
                view=CharacterView(characters, voice_scope),
            )

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

    # @bot.tree.command(
    #     name="list_style_ids",
    #     guild=TEST_GUILD_ID,
    #     description="利用可能なスタイルIDの一覧を表示します。",
    # )
    # async def list_style_ids(interaction: discord.Interaction):
    #     # 応答を遅延させる
    #     await interaction.response.defer()

    #     embeds = []
    #     embed = discord.Embed(title="利用可能なスタイルIDの一覧", color=0x00FF00)
    #     embed.description = "各スピーカーと利用可能なスタイルのIDです。"
    #     field_count = 0

    #     for speaker in speakers:
    #         name = speaker["name"]
    #         styles = "\n".join(
    #             f"- {style['name']} `{style['id']}`" for style in speaker["styles"]
    #         )

    #         if field_count < 25:
    #             embed.add_field(name=name, value=styles, inline=True)
    #             field_count += 1
    #         else:
    #             embeds.append(embed)
    #             embed = discord.Embed(title="利用可能なスタイルIDの一覧 (続き)", color=0x00FF00)
    #             embed.add_field(name=name, value=styles, inline=True)
    #             field_count = 1  # Reset for the new embed

    #     # Add the last embed
    #     embeds.append(embed)

    #     # フォローアップメッセージを使用して複数の埋め込みを送信
    #     for embed in embeds:
    #         await interaction.followup.send(embed=embed)
    # @bot.tree.command(
    #     name="style_id",
    #     guild=TEST_GUILD_ID,
    #     description="スタイルを表示または設定します。",
    # )
    # @app_commands.choices(
    #     voice_scope=[
    #         app_commands.Choice(name="ユーザー", value="user"),
    #         app_commands.Choice(name="VC入退室時", value="notify"),
    #         app_commands.Choice(name="ユーザーデフォルト", value="user_default"),
    #     ]
    # )
    # async def style_id(interaction, voice_scope: str, style_id: int = None):
    #     if voice_scope and not style_id:
    #         # If only voice_scope is provided, display the current settings for that type.
    #         update_message = await handle_style_command(interaction, None, voice_scope)
    #     else:
    #         # handle_style_command from the response
    #         update_message = await handle_style_command(
    #             interaction, style_id, voice_scope
    #         )

    #     # Sending the response or follow-up message
    #     if update_message:
    #         if interaction.response.is_done():
    #             await interaction.followup.send(update_message)
    #         else:
    #             await interaction.response.send_message(update_message)

    # @bot.command(name="remove_command")
    # async def remove_command(ctx, command_name: str):
    #     # このコマンドを使用すると、指定されたコマンド名のスラッシュコマンドを削除します。
    #     guild_id = ctx.guild.id  # コマンドを削除したいギルドのID
    #     guild = discord.Object(id=guild_id)
    #     for cmd in await bot.tree.fetch_commands(guild=guild):
    #         if cmd.name == command_name:
    #             await bot.tree.remove_command(cmd.name, guild=guild)
    #             await ctx.send(f"コマンド {command_name} を削除しました。")
    #             break
    #     else:
    #         await ctx.send(f"コマンド {command_name} が見つかりませんでした。")

    # @bot.command(name="remove_global_command")
    # async def remove_global_command(ctx, command_name: str):
    #     try:
    #         commands = await bot.tree.fetch_commands()  # Fetch all global commands
    #         for cmd in commands:
    #             if cmd.name == command_name:
    #                 if cmd is None:
    #                     await ctx.send("Error: Command object is None.")
    #                     return

    #                 # Attempt to remove the command
    #                 removal_result = bot.tree.remove_command(cmd)
    #                 if asyncio.iscoroutine(removal_result):
    #                     await removal_result
    #                 else:
    #                     # If it's not a coroutine, it's possible that the command was removed without needing to await anything
    #                     pass

    #                 await ctx.send(f"グローバルコマンド {command_name} を削除しました。")
    #                 return
    #         await ctx.send(f"グローバルコマンド {command_name} が見つかりませんでした。")
    #     except Exception as e:
    #         await ctx.send(f"コマンドを削除中にエラーが発生しました: {e}")
    # @bot.tree.command(
    #     name="display_current_settings",
    #     guild=TEST_GUILD_ID,
    #     description="現在のスタイル設定を表示します。",
    # )
    # async def display_current_settings(interaction: discord.Interaction):
    #     guild_id = str(interaction.guild_id)
    #     user_id = str(interaction.user.id)

    #     # Dictionary to map style types to more user-friendly descriptions
    #     voice_scope_descriptions = {
    #         "user": "ユーザー特有のスタイル",
    #         "notify": "VC入退室時の通知",
    #         "user_default": "ユーザーデフォルト",
    #     }

    #     # Prepare messages for each style type
    #     messages = []
    #     for voice_scope, description in voice_scope_descriptions.items():
    #         style_id, speaker_name, style_name = get_current_style_details(
    #             guild_id, user_id, voice_scope
    #         )
    #         messages.append(
    #             f"**{description}**: {speaker_name} {style_name} (スタイルID: {style_id})"
    #         )

    #     # Send the compiled message
    #     if messages:
    #         await interaction.response.send_message(
    #             "以下は現在のスタイル設定です:\n" + "\n".join(messages)
    #         )
    #     else:
    #         await interaction.response.send_message("現在のスタイル設定はありません。")
