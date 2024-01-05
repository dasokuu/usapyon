import aiohttp
import asyncio
import json
import discord
import io
from settings import SYNTHESIS_URL, AUDIO_QUERY_URL
import logging

# Loggerの設定
logging.basicConfig(level=logging.INFO)


class VoiceSynthServer:
    def __init__(self):
        self.guild_playback_queues = {}
        self.headers = {"Content-Type": "application/json"}
        self.session = aiohttp.ClientSession()  # セッションを一つだけ作成

    def get_guild_playback_queue(self, guild_id):
        if guild_id not in self.guild_playback_queues:
            self.guild_playback_queues[guild_id] = asyncio.Queue()
        return self.guild_playback_queues[guild_id]

    async def process_playback_queue(self, guild_id):
        guild_queue = self.get_guild_playback_queue(guild_id)
        while True:
            voice_client, line, style_id = await guild_queue.get()
            try:
                # タイムアウトを設定してspeak_lineメソッドを呼び出す
                await asyncio.wait_for(
                    self.speak_line(voice_client, line, style_id, guild_id), timeout=10
                )
            except asyncio.TimeoutError:
                logging.error("speak_line() timed out")
            except Exception as e:
                logging.error(f"Error in process_playback_queue: {e}")
            finally:
                guild_queue.task_done()

    async def audio_query(self, text, style_id):
        query_payload = {"text": text, "speaker": style_id}
        async with self.session.post(
            AUDIO_QUERY_URL, headers=self.headers, json=query_payload
        ) as response:
            if response.status == 200:
                return await response.json()
            else:
                error_detail = await response.text()
                logging.warning(
                    f"audio_query failed: {response.status}, {error_detail}"
                )
                return None

    async def synthesis(self, speaker, query_data):
        synth_payload = {"speaker": speaker}
        headers = {"Content-Type": "application/json", "Accept": "audio/wav"}
        async with self.session.post(
            SYNTHESIS_URL, headers=headers, json=query_data
        ) as response:
            if response.status == 200:
                return await response.read()
            else:
                logging.warning(f"synthesis failed: {response.status}")
                return None

    async def close(self):
        await self.session.close()  # セッションを閉じる

    async def text_to_speech(self, voice_client, text, style_id, guild_id):
        """テキストを音声に変換して再生します。"""
        if not voice_client or not voice_client.is_connected():
            return  # 接続されていない場合は処理を中断

        try:
            lines = text.split("\n")
            for line in filter(None, lines):  # 空行を除外
                guild_queue = self.get_guild_playback_queue(guild_id)
                await guild_queue.put((voice_client, line, style_id))
        except Exception as e:
            print(f"Error in text_to_speech: {e}")

    async def speak_line(self, voice_client, line, style_id, guild_id):
        query_data = await self.audio_query(line, style_id)
        if query_data:
            voice_data = await self.synthesis(style_id, query_data)
            if voice_data:
                audio_source = discord.FFmpegPCMAudio(io.BytesIO(voice_data), pipe=True)
                voice_client.play(audio_source)

                # Wait for the current audio to finish playing before returning
                while voice_client.is_playing():
                    await asyncio.sleep(0.1)

    async def clear_playback_queue(self, guild_id):
        guild_queue = self.get_guild_playback_queue(guild_id)
        while not guild_queue.empty():
            try:
                guild_queue.get_nowait()
            except asyncio.QueueEmpty:
                continue
            guild_queue.task_done()
