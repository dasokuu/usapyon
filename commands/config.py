import asyncio
import discord
import jaconv
from settings import APPROVED_GUILD_OBJECTS, DORMITORY_URL_BASE
from discord.ui import Button, View

from utils import VoiceSynthConfig, get_character_info


def setup_config_command(bot, voice_config: VoiceSynthConfig):
    @bot.tree.command(
        name="config", guilds=APPROVED_GUILD_OBJECTS, description="読み上げ音声を設定します。"
    )
    async def config(interaction: discord.Interaction):
        voice_scope_description = get_voice_scope_description(interaction)
        view = create_config_view(interaction, voice_scope_description)
        await interaction.response.send_message(
            "設定対象を選んでください：", view=view, ephemeral=True
        )

    def get_voice_scope_description(interaction: discord.Interaction):
        return {
            "user": f"{interaction.user.display_name}さんの読み上げ音声",
            "announcement": "アナウンス音声（サーバー設定）",
            "user_default": "デフォルト読み上げ音声（サーバー設定）",
        }

    def create_config_view(interaction: discord.Interaction, voice_scope_description):
        view = View()
        for voice_scope, label in voice_scope_description.items():
            button = create_scope_button(interaction, label, voice_scope)
            view.add_item(button)
        return view

    def create_scope_button(interaction: discord.Interaction, label, voice_scope):
        button = Button(
            style=discord.ButtonStyle.primary,
            label=label,
        )
        button.callback = create_button_callback(interaction, button, voice_scope)
        return button

    def create_button_callback(interaction: discord.Interaction, button, voice_scope):
        async def on_button_click(interaction: discord.Interaction):
            await initiate_speaker_paging(interaction, voice_scope)

        return on_button_click

    class SpeakerSearchModal(discord.ui.Modal):
        def __init__(self, view):
            super().__init__(title="キャラクターを検索")
            self.view = view  # Reference to the PagingView

        speaker_input = discord.ui.TextInput(
            label="キャラクター名",
            style=discord.TextStyle.short,
            placeholder="例: ずんだ",
            min_length=1,
            max_length=50,
        )

        async def on_submit(self, interaction: discord.Interaction):
            # ユーザーの入力をひらがなに変換
            speaker_name_query = jaconv.kata2hira(
                self.speaker_input.value.strip().lower()
            )

            for i, speaker in enumerate(self.view.speakers):
                # データソースのテキストもひらがなに変換してから比較
                speaker_name = jaconv.kata2hira(speaker["name"].lower())
                if speaker_name_query in speaker_name:
                    self.view.current_page = i
                    await self.view.update_speaker_list(interaction)
                    return

            # 一致するキャラクターが見つからなかった場合の処理
            await interaction.response.send_message(
                f"「{self.speaker_input.value}」に一致するキャラクターが見つかりませんでした。", ephemeral=True
            )

    class PagingView(discord.ui.View):
        def __init__(self, speakers, voice_scope):
            super().__init__()
            self.speakers = speakers
            self.voice_scope = voice_scope
            self.current_page = 0

        @discord.ui.button(label="<<", style=discord.ButtonStyle.primary)
        async def five_back_button(
            self, interaction: discord.Interaction, button: discord.ui.Button
        ):
            # Move back 5 pages, but not below page 0
            self.current_page = max(0, self.current_page - 5)
            await self.update_speaker_list(interaction)

        @discord.ui.button(label="<", style=discord.ButtonStyle.primary)
        async def previous_button(
            self, interaction: discord.Interaction, button: discord.ui.Button
        ):
            if self.current_page > 0:
                self.current_page -= 1
            else:
                self.current_page = len(self.speakers) - 1
            await self.update_speaker_list(interaction)

        @discord.ui.button(label=">", style=discord.ButtonStyle.primary)
        async def next_button(
            self, interaction: discord.Interaction, button: discord.ui.Button
        ):
            if self.current_page < len(self.speakers) - 1:
                self.current_page += 1
            else:
                self.current_page = 0
            await self.update_speaker_list(interaction)

        @discord.ui.button(label=">>", style=discord.ButtonStyle.primary)
        async def five_forward_button(
            self, interaction: discord.Interaction, button: discord.ui.Button
        ):
            # Move forward 5 pages, but not beyond the last page
            self.current_page = min(len(self.speakers) - 1, self.current_page + 5)
            await self.update_speaker_list(interaction)

        @discord.ui.button(
            label="検索", style=discord.ButtonStyle.primary, custom_id="search_speaker"
        )
        async def go_button(
            self, interaction: discord.Interaction, button: discord.ui.Button
        ):
            # Open the modal when the 'Go' button is clicked
            modal = SpeakerSearchModal(self)
            await interaction.response.send_modal(modal)

        async def update_speaker_list(self, interaction: discord.Interaction):
            self.five_back_button.disabled = self.current_page < 5
            self.previous_button.disabled = self.current_page == 0
            self.five_forward_button.disabled = (
                self.current_page > len(self.speakers) - 6
            )
            self.next_button.disabled = self.current_page == len(self.speakers) - 1
            voice_scope_description = get_voice_scope_description(interaction)
            # 'interaction'を正しく使ってメッセージを編集
            speaker_name = self.speakers[self.current_page]["name"]
            content = f"矢印や検索ボタンを活用してお好みのキャラクターを選んだ後、そのキャラクター固有のスタイル（声のバリエーションや特色など）を選択してください：\nキャラクター {self.current_page + 1} / {len(self.speakers)}\n"
            speaker_character_id, speaker_display_name = get_character_info(
                speaker_name
            )
            speaker_url = f"{DORMITORY_URL_BASE}/{speaker_character_id}/"

            # 歓迎メッセージを作成
            content += f"[{speaker_display_name}]({speaker_url})"
            # 古いスタイルのボタンを削除して新しいものを追加
            self.clear_items()

            # ナビゲーションボタンを追加
            self.add_item(self.five_back_button)
            self.add_item(self.previous_button)
            self.add_item(self.next_button)
            self.add_item(self.five_forward_button)
            self.add_item(self.go_button)  # Make sure this is added back

            # 現在のキャラクターの各スタイルに対応するボタンを追加
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

        # 最初のキャラクターを表示
        speaker_name = (
            voice_config.speakers[0]["name"]
            if voice_config.speakers
            else "利用可能なキャラクターがいません"
        )
        content = f"矢印や検索ボタンを活用してお好みのキャラクターを選んだ後、そのキャラクター固有のスタイル（声のバリエーションや特色など）を選択してください：\nキャラクター 1 / {len(voice_config.speakers)}\n"
        speaker_character_id, speaker_display_name = get_character_info(speaker_name)
        speaker_url = f"{DORMITORY_URL_BASE}/{speaker_character_id}/"

        content += f"[{speaker_display_name}]({speaker_url})"
        # 最初のキャラクターの各スタイルに対応するボタンを追加
        for style in voice_config.speakers[0][
            "styles"
        ]:  # 'styles'は各キャラクターのスタイル辞書のリストと仮定
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
            view.five_back_button.disabled = True
            view.previous_button.disabled = True
            view.add_item(style_button)
        await interaction.response.edit_message(content=content, view=view)
