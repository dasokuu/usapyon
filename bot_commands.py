import asyncio
import discord
from settings import (
    CHARACTORS_INFO,
    TEST_GUILD_ID,
    USER_DEFAULT_STYLE_ID,
    announcement_DEFAULT_STYLE_ID,
)
from utils import (
    speakers,
    speaker_settings,
    save_style_settings,
    get_style_details,
    validate_style_id,
)
from voice import clear_playback_queue, text_to_speech
from discord import app_commands


async def handle_voice_config_command(interaction, style_id: int, voice_scope: str):
    guild_id = str(interaction.guild_id)
    user_id = str(interaction.user.id)
    user_display_name = interaction.user.display_name  # Corrected variable name

    # Define descriptions for each voice style scope
    voice_scope_description = {
        "user": f"{user_display_name}のテキスト読み上げ音声",  # Corrected variable name
        "announcement": "アナウンス音声",
        "user_default": "ユーザーデフォルトTTS音声",
    }

    try:
        # If style_id and voice_scope are None, display all settings
        if style_id is None and voice_scope is None:
            messages = []
            for t in voice_scope_description:
                style_id, speaker_name, style_name = get_current_style_details(
                    guild_id, user_id, t
                )
                character_id = CHARACTORS_INFO.get(speaker_name, "unknown")  # キャラクターIDを取得
                url = f"https://voicevox.hiroshiba.jp/dormitory/{character_id}/"
                messages.append(
                    f"**{voice_scope_description[t]}**: {speaker_name}({url}) {style_name}"
                )
            await interaction.response.send_message("\n".join(messages))
            return
        elif style_id is None and voice_scope is not None:
            # Display current style settings
            current_style_id, speaker_name, style_name = get_current_style_details(
                guild_id, user_id, voice_scope
            )
            character_id = CHARACTORS_INFO.get(speaker_name, "unknown")  # キャラクターIDを取得
            url = f"https://voicevox.hiroshiba.jp/dormitory/{character_id}/"
            await interaction.response.send_message(
                f"現在の{voice_scope_description[voice_scope]}は「{speaker_name}({url}) {style_name}」です。"
            )
        elif style_id is not None and voice_scope is None:
            messages = []
            for t in voice_scope_description:
                style_id, speaker_name, style_name = get_current_style_details(
                    guild_id, user_id, t
                )
                character_id = CHARACTORS_INFO.get(speaker_name, "unknown")  # キャラクターIDを取得
                url = f"https://voicevox.hiroshiba.jp/dormitory/{character_id}/"
                messages.append(
                    f"**{voice_scope_description[t]}**: {speaker_name}({url}) {style_name}"
                )
            await interaction.response.send_message("\n".join(messages))
            return
        elif style_id is not None and voice_scope is not None:
            valid, speaker_name, style_name = validate_style_id(style_id)
            if not valid:
                await interaction.response.send_message(
                    f"スタイルID {style_id} は無効です。正しいIDを入力してください。", ephemeral=True
                )
                return
            update_style_setting(guild_id, user_id, style_id, voice_scope)
            character_id = CHARACTORS_INFO.get(speaker_name, "unknown")  # キャラクターIDを取得
            url = f"https://voicevox.hiroshiba.jp/dormitory/{character_id}/"
            await interaction.response.send_message(
                f"{voice_scope_description[voice_scope]}が「VOICEVOX:{speaker_name}({url}): {style_name}」に更新されました。"
            )
            return

    except Exception as e:
        await interaction.response.send_message(f"エラーが発生しました: {e}")
    return None  # Return None if there's no response


def update_style_setting(guild_id, user_id, style_id, voice_scope):
    if voice_scope == "user_default":
        speaker_settings[guild_id]["user_default"] = style_id
    elif voice_scope == "announcement":
        speaker_settings[guild_id]["announcement"] = style_id
    elif voice_scope == "user":
        speaker_settings[user_id] = style_id
    save_style_settings()


def get_current_style_details(guild_id, user_id, voice_scope):
    if voice_scope == "user_default":
        style_id = speaker_settings[guild_id].get("user_default", USER_DEFAULT_STYLE_ID)
    elif voice_scope == "announcement":
        style_id = speaker_settings[guild_id].get("announcement", announcement_DEFAULT_STYLE_ID)
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
        description="あなたのテキスト読み上げキャラクターを設定します。",
    )
    async def voice_config(interaction: discord.Interaction, style_id: int):
        await handle_voice_config_command(interaction, style_id, voice_scope="user")

    @bot.tree.command(
        name="server_voice_config",
        guild=TEST_GUILD_ID,
        description="サーバーのテキスト読み上げキャラクターを表示また設定します。",
    )
    @app_commands.choices(
        voice_scope=[
            app_commands.Choice(name="アナウンス音声", value="announcement"),
            app_commands.Choice(name="ユーザーデフォルトTTS音声", value="user_default"),
        ]
    )
    async def server_voice_config(
        interaction: discord.Interaction, voice_scope: str = None, style_id: int = None
    ):
        await handle_voice_config_command(interaction, style_id, voice_scope)

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
                welcome_voice = "読み上げを開始します。"

                guild_id = str(interaction.guild_id)
                user_id = str(interaction.user.id)  # コマンド使用者のユーザーID
                user_display_name = (
                    interaction.user.display_name
                )  # Corrected variable name
                text_channel_id = str(interaction.channel_id)  # このコマンドを使用したテキストチャンネルID

                # サーバー設定が存在しない場合は初期化
                if guild_id not in speaker_settings:
                    speaker_settings[guild_id] = {"text_channel": text_channel_id}
                else:
                    # 既にサーバー設定が存在する場合はテキストチャンネルIDを更新
                    speaker_settings[guild_id]["text_channel"] = text_channel_id

                save_style_settings()  # 変更を保存

                # 通知スタイルIDを取得
                announcement_style_id = speaker_settings.get(guild_id, {}).get(
                    "announcement", announcement_DEFAULT_STYLE_ID
                )
                # ユーザーのスタイルIDを取得
                user_style_id = speaker_settings.get(user_id, USER_DEFAULT_STYLE_ID)

                # クレジットをメッセージに追加
                announcement_speaker_name, announcement_style_name = get_style_details(
                    announcement_style_id
                )
                announcement_character_id = CHARACTORS_INFO.get(announcement_speaker_name, "unknown")  # キャラクターIDを取得
                announcement_url = f"https://voicevox.hiroshiba.jp/dormitory/{announcement_character_id}/"
                user_speaker_name, user_style_name = get_style_details(user_style_id)
                user_character_id = CHARACTORS_INFO.get(user_speaker_name, "unknown")  # キャラクターIDを取得
                user_url = f"https://voicevox.hiroshiba.jp/dormitory/{user_character_id}/"
                welcome_message = (
                    f"アナウンス音声「[VOICEVOX:{announcement_speaker_name}]({announcement_url})-{announcement_style_name}」\n"
                    f"{user_display_name}のテキスト読み上げ音声「[VOICEVOX:{user_speaker_name}]({user_url})-{user_style_name}」"
                )

                # メッセージとスタイルIDをキューに追加
                await text_to_speech(
                    voice_client, welcome_voice, announcement_style_id, guild_id
                )
                await interaction.followup.send(welcome_message)
            else:
                await interaction.followup.send(
                    "ボイスチャンネルに接続できませんでした。ユーザーがボイスチャンネルにいることを確認してください。"
                )
        except Exception as e:
            # エラーメッセージをユーザーに通知
            await interaction.followup.send(f"接続中にエラーが発生しました: {e}")

    @bot.tree.command(
        name="list", guild=TEST_GUILD_ID, description="話者とそのスタイルIDを表示します。"
    )
    async def list(interaction: discord.Interaction):
        """話者とそのスタイルIDを表示します。"""
        if not speakers:
            await interaction.response.send_message("話者のデータを取得できませんでした。")
            return

        # メッセージを整形して作成
        message = "**利用可能な話者とスタイル:**\n"
        for speaker in speakers:
            name = speaker["name"]
            character_id = CHARACTORS_INFO.get(name, "unknown")  # キャラクターIDを取得
            url = f"https://voicevox.hiroshiba.jp/dormitory/{character_id}/"
            styles = ", ".join(
                [f"{style['name']} (ID: {style['id']})" for style in speaker["styles"]]
            )
            message += f"\n[{name}]({url}): {styles}"

        # 長いメッセージを適切に分割して送信
        await send_long_message(interaction, message)

    async def send_long_message(
        interaction: discord.Interaction, message, split_char="\n"
    ):
        """2000文字を超える長いメッセージを適切に分割して送信します。
        最初のメッセージは応答として送信され、残りはフォローアップとして送信されます。
        """
        # 最初のメッセージフラグを設定します。
        first_message = True

        while len(message) > 0:
            # メッセージが2000文字以下の場合はそのまま送信
            if len(message) <= 2000:
                # 最初のメッセージの場合は応答として送信
                if first_message:
                    await interaction.response.send_message(message)
                else:
                    await interaction.followup.send(message)
                break

            # メッセージを2000文字で仮に切り分け
            part = message[:2000]
            # 最後の改行位置または分割文字の位置を探す
            split_pos = part.rfind(split_char)
            if split_pos == -1:
                # 分割文字が見つからない場合は、2000文字で強制的に分割
                split_pos = 1999

            # 最初の部分を送信
            part_to_send = message[: split_pos + 1]
            if first_message:
                await interaction.response.send_message(part_to_send)
                first_message = False
            else:
                await interaction.followup.send(part_to_send)

            # 残りのメッセージを更新
            message = message[split_pos + 1 :]

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
    #     embed.description = "各話者と利用可能なスタイルのIDです。"
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
    #         app_commands.Choice(name="VC入退室時", value="announcement"),
    #         app_commands.Choice(name="ユーザーデフォルト", value="user_default"),
    #     ]
    # )
    # async def style_id(interaction, voice_scope: str, style_id: int = None):
    #     if voice_scope and not style_id:
    #         # If only voice_scope is provided, display the current settings for that type.
    #         update_message = await handle_voice_config_command(interaction, None, voice_scope)
    #     else:
    #         # handle_voice_config_command from the response
    #         update_message = await handle_voice_config_command(
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
    #         "announcement": "VC入退室時の通知",
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
