import asyncio
import discord
from settings import APPROVED_GUILD_OBJECTS, DORMITORY_URL_BASE
from discord.ui import Button, View

from utils import get_character_info


def setup_config_command(bot, voice_config):
    @bot.tree.command(
        name="config", guilds=APPROVED_GUILD_OBJECTS, description="読み上げ音声を設定します。"
    )
    async def config(interaction: discord.Interaction):
        voice_scope_description = get_voice_scope_description(interaction)
        view = create_config_view(interaction, voice_scope_description)
        await interaction.response.send_message(
            "設定対象を選んでください：", view=view, ephemeral=True
        )

    def get_voice_scope_description(interaction):
        return {
            "user": f"{interaction.user.display_name}さん専用の読み上げ音声",
            "announcement": "入退出時のアナウンス音声",
            "user_default": "未設定ユーザーの読み上げ音声",
        }

    def create_config_view(interaction, voice_scope_description):
        view = View()
        for voice_scope, label in voice_scope_description.items():
            button = create_scope_button(interaction, label, voice_scope)
            view.add_item(button)
        return view

    def create_scope_button(interaction, label, voice_scope):
        button = Button(
            style=discord.ButtonStyle.primary
            if voice_scope == "user"
            else discord.ButtonStyle.secondary,
            label=label,
        )
        button.callback = create_button_callback(interaction, button, voice_scope)
        return button

    def create_button_callback(interaction, button, voice_scope):
        async def on_button_click(interaction: discord.Interaction):
            await initiate_speaker_paging(interaction, voice_scope)

        return on_button_click

    class PagingView(discord.ui.View):
        def __init__(self, speakers, voice_scope):
            super().__init__()
            self.speakers = speakers
            self.voice_scope = voice_scope
            self.current_page = 0

        @discord.ui.button(label="<<", style=discord.ButtonStyle.blurple)
        async def first_button(
            self, interaction: discord.Interaction, button: discord.ui.Button
        ):
            self.current_page = 0
            await self.update_speaker_list(interaction)

        @discord.ui.button(label="<", style=discord.ButtonStyle.blurple)
        async def previous_button(
            self, interaction: discord.Interaction, button: discord.ui.Button
        ):
            if self.current_page > 0:
                self.current_page -= 1
            else:
                self.current_page = len(self.speakers) - 1
            await self.update_speaker_list(interaction)

        @discord.ui.button(label=">", style=discord.ButtonStyle.blurple)
        async def next_button(
            self, interaction: discord.Interaction, button: discord.ui.Button
        ):
            if self.current_page < len(self.speakers) - 1:
                self.current_page += 1
            else:
                self.current_page = 0
            await self.update_speaker_list(interaction)

        @discord.ui.button(label=">>", style=discord.ButtonStyle.blurple)
        async def last_button(
            self, interaction: discord.Interaction, button: discord.ui.Button
        ):
            self.current_page = len(self.speakers) - 1
            await self.update_speaker_list(interaction)

        async def update_speaker_list(self, interaction: discord.Interaction):
            self.first_button.disabled = self.current_page == 0
            self.last_button.disabled = self.current_page == len(self.speakers) - 1
            voice_scope_description = get_voice_scope_description(interaction)
            # 'interaction'を正しく使ってメッセージを編集
            speaker_name = self.speakers[self.current_page]["name"]
            content = f"矢印ボタンで使用するキャラクターを選択し、スタイルを選んでください：\nページ {self.current_page + 1} / {len(self.speakers)}\n"
            speaker_character_id, speaker_display_name = get_character_info(
                speaker_name
            )
            speaker_url = f"{DORMITORY_URL_BASE}/{speaker_character_id}/"

            # 歓迎メッセージを作成
            content += f"[{speaker_display_name}]({speaker_url})"
            # 古いスタイルのボタンを削除して新しいものを追加
            self.clear_items()

            # ナビゲーションボタンを追加
            self.add_item(self.first_button)
            self.add_item(self.previous_button)
            self.add_item(self.next_button)
            self.add_item(self.last_button)

            # 現在の話者の各スタイルに対応するボタンを追加
            for style in self.speakers[self.current_page]["styles"]:
                style_button = discord.ui.Button(
                    label=style["name"], style=discord.ButtonStyle.secondary
                )

                # ボタンが押されたときの処理を定義
                async def handle_style_button_click(
                    interaction: discord.Interaction,
                    button: discord.ui.Button,
                    style_id=style["id"],
                ):
                    await on_style_button_click(interaction, button, style_id)

                async def on_style_button_click(
                    interaction: discord.Interaction,
                    button: Button,
                    style_id,
                ):
                    # スタイル変更をここで処理
                    valid, speaker_name, style_name = voice_config.validate_style_id(
                        style_id
                    )
                    if not valid:
                        await interaction.response.edit_message(
                            f"スタイルID {style_id} は無効です。`/list`で有効なIDを確認し、正しいIDを入力してください。",
                            view=self,
                        )
                    voice_config.update_style_setting(
                        interaction.guild.id,
                        interaction.user.id,
                        style_id,
                        self.voice_scope,
                    )
                    speaker_character_id, speaker_display_name = get_character_info(
                        speaker_name
                    )
                    speaker_url = f"{DORMITORY_URL_BASE}/{speaker_character_id}/"
                    await interaction.response.send_message(
                        f"{voice_scope_description[self.voice_scope]}が「[{speaker_display_name}]({speaker_url}) {style_name}」に更新されました。"
                    )

                # Capture the current button and style_id using default arguments
                style_button.callback = (
                    lambda interaction, button=style_button, style_id=style[
                        "id"
                    ]: asyncio.create_task(
                        handle_style_button_click(interaction, button, style_id)
                    )
                )

                self.add_item(style_button)
            await interaction.response.edit_message(content=content, view=self)

    async def initiate_speaker_paging(interaction: discord.Interaction, voice_scope):
        voice_scope_description = get_voice_scope_description(interaction)
        # 初期ページングビューを作成
        view = PagingView(voice_config.speakers, voice_scope)

        # 最初の話者を表示
        speaker_name = (
            voice_config.speakers[0]["name"]
            if voice_config.speakers
            else "利用可能な話者がいません"
        )
        content = f"矢印ボタンで使用するキャラクターを選択し、スタイルを選んでください：\nページ 1 / {len(voice_config.speakers)}\n"
        speaker_character_id, speaker_display_name = get_character_info(speaker_name)
        speaker_url = f"{DORMITORY_URL_BASE}/{speaker_character_id}/"

        content += f"[{speaker_display_name}]({speaker_url})"
        # 最初の話者の各スタイルに対応するボタンを追加
        for style in voice_config.speakers[0]["styles"]:  # 'styles'は各話者のスタイル辞書のリストと仮定
            style_button = discord.ui.Button(
                label=style["name"], style=discord.ButtonStyle.secondary
            )

            # Define an async function for handling button clicks
            async def handle_style_button_click(
                interaction: discord.Interaction,
                button: discord.ui.Button,
                style_id=style["id"],
            ):
                await on_style_button_click(interaction, button, style_id)

            # ボタンが押されたときの処理を定義（別の関数を定義することも検討してください）
            async def on_style_button_click(
                interaction: discord.Interaction,
                button: Button,
                style_id=style["id"],
            ):
                # スタイル変更をここで処理
                valid, speaker_name, style_name = voice_config.validate_style_id(
                    style_id
                )
                if not valid:
                    await interaction.response.edit_message(
                        f"スタイルID {style_id} は無効です。`/list`で有効なIDを確認し、正しいIDを入力してください。",
                        view=view,
                    )
                voice_config.update_style_setting(
                    interaction.guild.id, interaction.user.id, style_id, voice_scope
                )
                speaker_character_id, speaker_display_name = get_character_info(
                    speaker_name
                )
                speaker_url = f"{DORMITORY_URL_BASE}/{speaker_character_id}/"
                await interaction.response.send_message(
                    f"{voice_scope_description[voice_scope]}が「[{speaker_display_name}]({speaker_url}) {style_name}」に更新されました。"
                )

            # Replace the existing 'style_button.callback' assignment with the following:
            style_button.callback = (
                lambda interaction, button=style_button, style_id=style[
                    "id"
                ]: asyncio.create_task(
                    handle_style_button_click(interaction, button, style_id)
                )
            )
            # 最初のページで<<と<ボタンを無効化
            view.first_button.disabled = True
            view.add_item(style_button)
        await interaction.response.edit_message(content=content, view=view)
