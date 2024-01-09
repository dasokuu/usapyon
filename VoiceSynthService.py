import logging
import aiohttp
import asyncio
import json
import discord
import io
from SpeechTextFormatter import SpeechTextFormatter
from settings import VOICEVOXSettings


class VoiceSynthService:
    def __init__(self):
        # Initialize global variables
        self.guild_playback_queues = {}
        self.headers = {"Content-Type": "application/json"}
        self.session = None  # 初期化時にはセッションはNoneに

    async def get_session(self):
        if not self.session or self.session.closed:  # セッションがないか閉じている場合
            self.session = aiohttp.ClientSession()  # 新しいセッションを作成
        return self.session

    def get_guild_playback_queue(self, guild_id):
        """指定されたギルドIDのplayback_queueを取得または作成します。"""
        if guild_id not in self.guild_playback_queues:
            self.guild_playback_queues[guild_id] = asyncio.Queue()
        return self.guild_playback_queues[guild_id]

    async def process_playback_queue(self, guild_id):
        guild_queue = self.get_guild_playback_queue(guild_id)
        while True:
            voice_client, line, style_id = await guild_queue.get()
            try:
                if (
                    voice_client
                    and voice_client.is_connected()
                    and not voice_client.is_playing()
                ):
                    await self.speak_line(voice_client, line, style_id)
            except Exception as e:
                logging.error(e)  # Log the error or handle it as needed.
            finally:
                guild_queue.task_done()

    async def audio_query(self, text, style_id):
        # 音声合成用のクエリを作成します。
        query_payload = {"text": text, "speaker": style_id}
        session = await self.get_session()  # セッションを取得

        async with session.post(
            VOICEVOXSettings.AUDIO_QUERY_URL, headers=self.headers, params=query_payload
        ) as response:
            if response.status == 200:
                return await response.json()
            elif response.status == 422:
                error_detail = await response.text()
                logging.error(f"Unprocessable Entity: {error_detail}")
                return None

    async def synthesis(self, speaker, query_data):
        # 音声合成を行います。
        synth_payload = {"speaker": speaker}
        headers = {"Content-Type": "application/json", "Accept": "audio/wav"}
        async with (await self.get_session()).post(  # セッションの取得方法を修正
            VOICEVOXSettings.SYNTHESIS_URL,
            headers=headers,
            params=synth_payload,
            data=json.dumps(query_data),
        ) as response:
            if response.status == 200:
                return await response.read()
            return None

    async def speak_line(self, voice_client: discord.VoiceClient, line, style_id):
        try:
            query_data = await self.audio_query(line, style_id)
            if not query_data:
                raise RuntimeError(f"Failed to get audio query for: {line}")

            voice_data = await self.synthesis(style_id, query_data)
            if not voice_data:
                raise RuntimeError(f"Failed to synthesize audio for: {line}")

            await self._play_audio(voice_client, voice_data)
        except Exception as e:
            logging.error(f"Error in speak_line: {e}")
            # ここで特定のエラーに対する追加の処理を行うことができます。

    async def _play_audio(self, voice_client: discord.VoiceClient, voice_data):
        try:
            audio_source = discord.FFmpegPCMAudio(
                io.BytesIO(voice_data), pipe=True)
            voice_client.play(audio_source)
            # Wait for the current audio to finish playing before returning
            while voice_client.is_playing():
                await asyncio.sleep(0.1)
        except Exception as e:
            logging.error(f"Error playing audio: {e}")

    async def clear_playback_queue(self, guild_id):
        guild_queue = self.get_guild_playback_queue(guild_id)
        while not guild_queue.empty():
            try:
                guild_queue.get_nowait()
            except asyncio.QueueEmpty:
                continue
            guild_queue.task_done()

    async def close_session(self):
        if self.session and not self.session.closed:
            await self.session.close()  # セッションが開いていれば閉じる

    async def text_to_speech(
        self,
        voice_client: discord.VoiceClient,
        text,
        style_id,
        guild_id,
        text_processor: SpeechTextFormatter,
        message: discord.Message = None,
    ):
        if not voice_client or not voice_client.is_connected():
            logging.error("Voice client is not connected.")
            return

        try:
            lines = text.split("\n")
            for line in filter(None, lines):
                # SpeechTextFormatterを用いてテキストを処理
                processed_line = await text_processor.replace_content(line, message)
                guild_queue = self.get_guild_playback_queue(guild_id)
                await guild_queue.put((voice_client, processed_line, style_id))
        except Exception as e:
            logging.error(f"Error in text_to_speech: {e}")
            # Handle specific exceptions and add remediation here.
