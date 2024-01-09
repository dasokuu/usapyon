import re
import discord
import emoji
import jaconv
import alkana


class MessageToSpeechProcessor:
    USER_MENTION_PATTERN = re.compile(r"<@!?(\d+)>")
    ROLE_MENTION_PATTERN = re.compile(r"<@&(\d+)>")
    CHANNEL_PATTERN = re.compile(r"<#(\d+)>")
    CUSTOM_EMOJI_PATTERN = re.compile(r"<:\w+:(\d+)>")
    LAUGH_PATTERN = re.compile(r"ｗ+$")
    ENGLISH_WORD_PATTERN = re.compile(r"\b[a-zA-Z_]+\b")
    URL_PATTERN = re.compile(r"http[s]?://\S+")

    def __init__(self):
        pass

    def replace_user_mention(self, match, message: discord.Message):
        user_id = int(match.group(1))
        user = message.guild.get_member(user_id)
        return user.display_name if user else match.group(0)

    def replace_role_mention(self, match, message: discord.Message):
        role_id = int(match.group(1))
        role = discord.utils.get(message.guild.roles, id=role_id)
        return role.name if role else match.group(0)

    def replace_channel_mention(self, match, message: discord.Message):
        channel_id = int(match.group(1))
        channel = message.guild.get_channel(channel_id)
        return channel.name if channel else match.group(0)

    def replace_custom_emoji_name_to_kana(self, match):
        # 絵文字の名前をキャプチャする
        emoji_name = match.group(0)
        # 絵文字名からID部分を取り除く
        emoji_name_cleaned = emoji_name.split(":")[1]
        # 絵文字名をひらがなに変換して返す
        return jaconv.alphabet2kana(emoji_name_cleaned) + " "

    def replace_english_to_kana(self, text):
        def replace_to_kana(match):
            word = match.group(0)
            sub_words = word.split("_")
            kana_words = []
            for sub_word in sub_words:
                kana = alkana.get_kana(sub_word)
                kana_words.append(kana if kana is not None else sub_word)
            return "".join(kana_words)

        return self.ENGLISH_WORD_PATTERN.sub(replace_to_kana, text)

    def laugh_replace(self, match):
        return "わら" * len(match.group(0))

    def replace_pattern(self, pattern, text, replace_func):
        return pattern.sub(replace_func, text)

    async def replace_content(self, text, message: discord.Message):
        text = self.replace_english_to_kana(
            text)  # First replace English words
        if message:
            replace_operations = [
                (
                    self.USER_MENTION_PATTERN,
                    lambda m: self.replace_user_mention(m, message),
                ),
                (
                    self.ROLE_MENTION_PATTERN,
                    lambda m: self.replace_role_mention(m, message),
                ),
                (
                    self.CHANNEL_PATTERN,
                    lambda m: self.replace_channel_mention(m, message),
                ),
            ]
            for pattern, func in replace_operations:
                text = self.replace_pattern(pattern, text, func)
        text = self.CUSTOM_EMOJI_PATTERN.sub(
            self.replace_custom_emoji_name_to_kana, text
        )
        text = self.URL_PATTERN.sub("URL省略", text)
        text = self.LAUGH_PATTERN.sub(self.laugh_replace, text)
        text = emoji.demojize(
            text, language="ja"
        )  # Assuming you meant emojize instead of demojize
        return text
