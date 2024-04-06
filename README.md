# VoiceChatLoid
python

- `sudo apt-get install mecab mecab-ipadic mecab-ipadic-utf8 libmecab-dev`
- `pip install -r requirements.txt`

rust

- [Rustのインストールはこちら](https://www.rust-lang.org/tools/install)
- `sudo apt-get install pkg-config libssl-dev`
- `sudo apt-get install cmake`

### ボットアカウント作成

- [Discord Developer Portal](https://discord.com/developers/applications)にアクセス
- トークン取得
- "SERVER MEMBERS INTENT"を有効にする
- "MESSAGE CONTENT INTENT"を有効にする

### ボットアカウントにログインする

#### トークン登録
.envファイルを作成し、以下のようにトークンを登録してください。

```:.env
DISCORD_TOKEN=[Discordのトークン]
```

#### サーバーに追加するときのロール

OAuth2 URL Generator

SCOPES
- bot
- applications.commands

下にURLが出てくるので、ブラウザにコピペして招待。

#### serenityを使う
