import aiohttp
import asyncio
import json
import discord
import io
from settings import SYNTHESIS_URL, AUDIO_QUERY_URL


# Initialize global variables
guild_playback_queues = {}
headers = {"Content-Type": "application/json"}


def get_guild_playback_queue(guild_id):
    """指定されたギルドIDのplayback_queueを取得または作成します。"""
    if guild_id not in guild_playback_queues:
        guild_playback_queues[guild_id] = asyncio.Queue()
    return guild_playback_queues[guild_id]


async def process_playback_queue(guild_id):
    guild_queue = get_guild_playback_queue(guild_id)
    while True:
        voice_client, line, style_id = await guild_queue.get()
        try:
            if (
                voice_client
                and voice_client.is_connected()
                and not voice_client.is_playing()
            ):
                await speak_line(voice_client, line, style_id, guild_id)
        except Exception as e:
            print(e)  # Log the error or handle it as needed.
        finally:
            guild_queue.task_done()


async def audio_query(text, style_id):
    # 音声合成用のクエリを作成します。
    query_payload = {"text": text, "speaker": style_id}
    async with aiohttp.ClientSession() as session:
        async with session.post(
            AUDIO_QUERY_URL, headers=headers, params=query_payload
        ) as response:
            if response.status == 200:
                return await response.json()
            elif response.status == 422:
                error_detail = await response.text()
                print(f"処理できないエンティティ: {error_detail}")
                return None


async def synthesis(speaker, query_data):
    # 音声合成を行います。
    synth_payload = {"speaker": speaker}
    headers = {"Content-Type": "application/json", "Accept": "audio/wav"}
    async with aiohttp.ClientSession() as session:
        async with session.post(
            SYNTHESIS_URL,
            headers=headers,
            params=synth_payload,
            data=json.dumps(query_data),
        ) as response:
            if response.status == 200:
                return await response.read()
            return None


async def text_to_speech(voice_client, text, style_id, guild_id):
    """テキストを音声に変換して再生します。"""
    if not voice_client or not voice_client.is_connected():
        return  # 接続されていない場合は処理を中断

    try:
        lines = text.split("\n")
        for line in filter(None, lines):  # 空行を除外
            guild_queue = get_guild_playback_queue(guild_id)
            await guild_queue.put((voice_client, line, style_id))
    except Exception as e:
        print(f"Error in text_to_speech: {e}")


async def speak_line(voice_client, line, style_id, guild_id):
    query_data = await audio_query(line, style_id)
    if query_data:
        voice_data = await synthesis(style_id, query_data)
        if voice_data:
            audio_source = discord.FFmpegPCMAudio(io.BytesIO(voice_data), pipe=True)
            voice_client.play(audio_source)

            # Wait for the current audio to finish playing before returning
            while voice_client.is_playing():
                await asyncio.sleep(0.1)


async def clear_playback_queue(guild_id):
    guild_queue = get_guild_playback_queue(guild_id)
    while not guild_queue.empty():
        try:
            guild_queue.get_nowait()
        except asyncio.QueueEmpty:
            continue
        guild_queue.task_done()
