import re
import discord
import emoji
import jaconv
import alkana
import MeCab


class SpeechTextFormatter:
    USER_MENTION_PATTERN = re.compile(r"<@!?(\d+)>")
    ROLE_MENTION_PATTERN = re.compile(r"<@&(\d+)>")
    CHANNEL_PATTERN = re.compile(r"<#(\d+)>")
    CUSTOM_EMOJI_PATTERN = re.compile(r"<:\w+:(\d+)>")
    LAUGH_PATTERN = re.compile(r"\bw+\b|ｗ+")
    ENGLISH_WORD_PATTERN = re.compile(r"\b[a-zA-Z_]+\b")
    URL_PATTERN = re.compile(r"http[s]?://\S+")

    def __init__(self):
        # MeCabの初期化
        self.mecab = MeCab.Tagger("-Owakati")

    def mecab_tokenize(self, text):
        # MeCabを使用してテキストを単語に分割する
        result = self.mecab.parse(text)
        return result.split()

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

    def replace_english_to_kana(self, words):
        processed_words = []
        for word in words:
            if re.match(self.ENGLISH_WORD_PATTERN, word):
                # 英単語をカタカナに変換
                kana = alkana.get_kana(word)
                processed_word = kana if kana else word
            else:
                processed_word = word
            processed_words.append(processed_word)
        return processed_words

    def laugh_replace(self, words):
        # 単語リストを受け取り、笑い表現を置換
        replaced_words = []
        for word in words:
            if re.match(self.LAUGH_PATTERN, word):
                replaced_words.append("わら")
            else:
                replaced_words.append(word)
        return replaced_words

    def replace_pattern(self, pattern, text, replace_func):
        return pattern.sub(replace_func, text)

    async def replace_content(self, text, message: discord.Message):
        # 英語の単語を特定し、スペースで区切る
        english_words = re.findall(self.ENGLISH_WORD_PATTERN, text)
        for english_word in english_words:
            kana = alkana.get_kana(english_word)
            if kana:
                text = text.replace(english_word, kana)

        # テキストをMeCabで単語に分割
        words = self.mecab_tokenize(text)

        # 笑い表現の置換
        words = self.laugh_replace(words)

        # 処理された単語を結合して完全なテキストに戻す
        text = ''.join(words)

        if message:
            replace_operations = [
                (self.USER_MENTION_PATTERN,
                 lambda m: self.replace_user_mention(m, message)),
                (self.ROLE_MENTION_PATTERN,
                 lambda m: self.replace_role_mention(m, message)),
                (self.CHANNEL_PATTERN,
                 lambda m: self.replace_channel_mention(m, message)),
            ]
            for pattern, func in replace_operations:
                text = self.replace_pattern(pattern, text, func)

        text = self.CUSTOM_EMOJI_PATTERN.sub(
            self.replace_custom_emoji_name_to_kana, text)
        text = self.URL_PATTERN.sub("URL省略", text)
        text = emoji.demojize(text, language="ja")

        return text
