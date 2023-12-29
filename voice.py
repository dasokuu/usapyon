import aiohttp
import asyncio
import json
import discord
import io

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
        item = await guild_queue.get()
        try:
            if isinstance(item, tuple) and len(item) == 2:
                voice_client, audio_source = item
                if voice_client and not voice_client.is_playing():
                    voice_client.play(audio_source)
                    while voice_client.is_playing():
                        await asyncio.sleep(0.1)
            else:
                raise ValueError(f"Unexpected item format in queue: {item}")
        except ValueError as e:
            print(e)  # Log the error or handle it as needed.
        finally:
            guild_queue.task_done()


async def audio_query(text, style_id):
    # 音声合成用のクエリを作成します。
    query_payload = {"text": text, "speaker": style_id}
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "http://127.0.0.1:50021/audio_query", headers=headers, params=query_payload
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
            "http://127.0.0.1:50021/synthesis",
            headers=headers,
            params=synth_payload,
            data=json.dumps(query_data),
        ) as response:
            if response.status == 200:
                return await response.read()
            return None


async def text_to_speech(voice_client, text, style_id, guild_id):
    lines = text.split("\n")
    tasks = []

    for line in lines:
        if not line.strip():
            continue
        # Create a task for each line and add it to the task list
        task = asyncio.create_task(speak_line(voice_client, line, style_id, guild_id))
        tasks.append(task)

    # Wait for all tasks to complete
    await asyncio.gather(*tasks)


async def speak_line(voice_client, line, style_id, guild_id):
    # The rest of your logic for processing each line
    query_data = await audio_query(line, style_id)
    if query_data:
        voice_data = await synthesis(style_id, query_data)
        if voice_data:
            audio_source = discord.FFmpegPCMAudio(io.BytesIO(voice_data), pipe=True)
            guild_queue = get_guild_playback_queue(guild_id)
            try:
                # Add audio source to the guild-specific queue
                await guild_queue.put((voice_client, audio_source))
            except Exception as e:
                print(f"An error occurred while playing audio: {e}")


async def clear_playback_queue(guild_id):
    guild_queue = get_guild_playback_queue(guild_id)
    while not guild_queue.empty():
        try:
            guild_queue.get_nowait()
        except asyncio.QueueEmpty:
            continue
        guild_queue.task_done()
