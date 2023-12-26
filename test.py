import discord
from discord.ext import commands
import requests
import json
import time
import re
import io

def audio_query(text, speaker, max_retry):
    # 音声合成用のクエリを作成する
    query_payload = {"text": text, "speaker": speaker}
    for query_i in range(max_retry):
        r = requests.post("http://localhost:50021/audio_query", 
                        params=query_payload, timeout=(10.0, 300.0))
        if r.status_code == 200:
            query_data = r.json()
            break
        time.sleep(1)
    else:
        raise ConnectionError("リトライ回数が上限に到達しました。 audio_query : ", "/", text[:30], r.text)
    return query_data
def synthesis(speaker, query_data,max_retry):
    synth_payload = {"speaker": speaker}
    for synth_i in range(max_retry):
        r = requests.post("http://localhost:50021/synthesis", params=synth_payload, 
                          data=json.dumps(query_data), timeout=(10.0, 300.0))
        if r.status_code == 200:
            #音声ファイルを返す
            return r.content
        time.sleep(1)
    else:
        raise ConnectionError("音声エラー：リトライ回数が上限に到達しました。 synthesis : ", r)


def text_to_speech(texts, speaker=8, max_retry=20):
    if texts==False:
        texts="ちょっと、通信状態悪いかも？"
    texts=re.split("(?<=！|。|？)",texts)
    play_obj=None
    for text in texts:
        # audio_query
        query_data = audio_query(text,speaker,max_retry)
        # synthesis
        voice_data=synthesis(speaker,query_data,max_retry)
        #音声の再生
        if play_obj != None and play_obj.is_playing():
            play_obj.wait_done()
        wave_obj=simpleaudio.WaveObject(voice_data,1,2,24000)
        play_obj=wave_obj.play()

# Discordクライアントの準備
intents = discord.Intents.default()
intents.messages = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')

@bot.command(name='join', help='このコマンドはボットをボイスチャンネルに接続します。')
async def join(ctx):
    if ctx.author.voice:
        channel = ctx.message.author.voice.channel
        await channel.connect()

@bot.command(name='leave', help='このコマンドはボットをボイスチャンネルから切断します。')
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()

@bot.command(name='speak', help='指定したテキストを読み上げます。')
async def speak(ctx, *, message):
    try:
        # 音声合成
        voice_data = text_to_speech(message, speaker=8)
        
        # Discordで再生するために音声データをByteIOとして変換
        audio_source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(io.BytesIO(voice_data), pipe=True))
        
        # ボイスチャンネルで再生
        if ctx.voice_client.is_playing():
            ctx.voice_client.stop()
        ctx.voice_client.play(audio_source)

    except Exception as e:
        await ctx.send(f'エラーが発生しました: {e}')

if __name__ == "__main__":
    bot.run(os.environ['DISCORD_BOT_TOKEN'])
