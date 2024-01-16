import logging
import random
import aiohttp
import asyncio
import json
import discord
import io
from SpeechTextFormatter import SpeechTextFormatter
from settings_loader import BotSettings, VOICEVOXSettings, engine_performance


# aiohttp.ClientSession の改善
class VoiceSynthService:
    def __init__(self):
        self.guild_playback_queues = {}
        self.headers = {"Content-Type": "application/json"}
        self.session = aiohttp.ClientSession()
        self.active_engines = []

    async def check_and_update_active_engines(self, interval_seconds):
        while True:
            await asyncio.sleep(interval_seconds)
            # アクティブエンジンの状態をチェックして更新
            for engine_url in VOICEVOXSettings.ENGINE_URLS:
                try:
                    is_up = await self.is_engine_up(engine_url)
                    if is_up and engine_url not in self.active_engines:
                        await self.activate_engine(self.active_engines, engine_url)
                    elif not is_up and engine_url in self.active_engines:
                        await self.deactivate_engine(self.active_engines, engine_url)
                except Exception as e:
                    logging.error(f"Error checking engine status: {e}")

    async def is_engine_up(self, engine_url):
        try:
            async with self.session.get(
                engine_url + VOICEVOXSettings.SPEAKERS_URL
            ) as response:
                return response.status == 200
        except Exception as e:
            logging.debug(f"Engine {engine_url} is not reachable: {e}")
            return False

    async def activate_engine(self, engines: list, engine):
        if engine not in engines:
            engines.append(engine)

    async def deactivate_engine(self, engines: list, engine):
        if engine in engines:
            engines.remove(engine)

    async def get_highest_performance_active_engine(self, engines):
        if not engines:
            return None

        # 仮にエンジンURL自体を性能指標として使用
        # 実際には、ここで性能データに基づいてエンジンを選択する
        sorted_active_engines = sorted(
            engines, key=lambda url: engine_performance[url], reverse=True
        )
        return sorted_active_engines[0] if sorted_active_engines else None

    async def synthesis(self, speaker, query_data):
        engine_url = await self.get_highest_performance_active_engine(self.active_engines)
        if not engine_url:
            return None
        headers = {"Content-Type": "application/json", "Accept": "audio/wav"}
        params = {"speaker": speaker}
        try:
            async with self.session.post(
                engine_url + VOICEVOXSettings.SYNTHESIS_URL,
                headers=headers,
                params=params,
                data=json.dumps(query_data),
            ) as response:
                if response.status == 200:
                    logging.info(f"using {engine_url}")
                    return await response.read()
                else:
                    logging.error(
                        f"Synthesis request failed with status: {response.status}"
                    )
                    return None
        except Exception as e:
            logging.error(
                f"Error during synthesis request to {engine_url}: {e}")
            self.deactivate_engine(self.active_engines, engine_url)
            return await self.retry_synthesis_on_different_engine(speaker, query_data)

    async def retry_synthesis_on_different_engine(self, speaker, query_data):
        retry_engines = self.active_engines.copy()
        while retry_engines:
            retry_engine = await self.get_highest_performance_active_engine(retry_engines)
            headers = {"Content-Type": "application/json",
                       "Accept": "audio/wav"}
            params = {"speaker": speaker}
            try:
                async with self.session.post(
                    retry_engine + VOICEVOXSettings.SYNTHESIS_URL,
                    headers=headers,
                    params=params,
                    data=json.dumps(query_data),
                ) as response:
                    if response.status == 200:
                        logging.info(f"using {retry_engine}")
                        return await response.read()
                    else:
                        logging.error(
                            f"Retry synthesis request failed with status: {response.status}"
                        )
            except Exception as e:
                logging.error(
                    f"Error during retry synthesis request to {retry_engine}: {e}"
                )
            finally:
                self.deactivate_engine(retry_engines, retry_engine)
        logging.error("All engines failed to process the request.")
        return None

    async def close(self):
        await self.session.close()

    async def get_random_active_engine(self):
        if not self.active_engines:
            return None
        return random.choice(self.active_engines)

    async def get_preferred_or_random_active_engine(self, preferred_engine):
        if not self.active_engines:
            return None

        # 指定した優先エンジンがリストに含まれているか確認
        if preferred_engine in self.active_engines:
            return preferred_engine

        # リストからランダムにエンジンを選択
        return random.choice(self.active_engines)

    async def ensure_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
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
            if (
                voice_client
                and voice_client.is_connected()
                and not voice_client.is_playing()
            ):
                await self.safely_speak_line(voice_client, line, style_id)
            guild_queue.task_done()

    # 例外処理時にユーザーへのフィードバックを追加
    async def safely_speak_line(self, voice_client, line, style_id):
        try:
            await self.speak_line(voice_client, line, style_id)
        except aiohttp.ClientError as e:
            logging.error(
                f"Client error during speaking line: {e}", exc_info=True)
            await self.send_error_message(voice_client, "音声合成サービスへの接続に問題が発生しました。")
        except Exception as e:
            logging.error(
                f"Unexpected error speaking line: {e}", exc_info=True)
            await self.send_error_message(voice_client, "予期せぬエラーが発生しました。")
            if voice_client.is_connected():
                await voice_client.disconnect()

    async def send_error_message(self, voice_client, message):
        # エラーメッセージを送信するための専用メソッド
        if voice_client.channel:
            await voice_client.channel.send(message)

    async def audio_query(self, text, style_id):
        try:
            async with self.session.post(
                VOICEVOXSettings.LOCAL_ENGINE_URL +
                    VOICEVOXSettings.AUDIO_QUERY_URL,
                headers=self.headers,
                params={"text": text, "speaker": style_id},
            ) as response:
                response.raise_for_status()
                return await response.json()
        except asyncio.TimeoutError:
            logging.error("Timeout occurred during audio query")
            return {"error": "Timeout during audio query"}
        except aiohttp.ClientConnectionError:
            logging.error("Connection error during audio query")
            return {"error": "Connection error during audio query"}
        except Exception as e:
            logging.error(f"Unexpected error during audio query: {e}")
            return {"error": "Unexpected error"}

    # async def synthesis(self, speaker, query_data):
    #     session = await self.ensure_session()
    #     if not session:
    #         logging.error("Failed to establish session for synthesis")
    #         return None
    #     synth_payload = {"speaker": speaker}
    #     headers = {"Content-Type": "application/json", "Accept": "audio/wav"}
    #     try:
    #         async with session.post(
    #             VOICEVOXSettings.SYNTHESIS_URL,
    #             headers=headers,
    #             params=synth_payload,
    #             data=json.dumps(query_data),
    #         ) as response:
    #             if response.status == 200:
    #                 return await response.read()
    #             else:
    #                 logging.error(
    #                     f"Synthesis request failed with status: {response.status}"
    #                 )
    #     except aiohttp.ClientResponseError as e:
    #         logging.error(f"Response error during synthesis: {e}", exc_info=True)
    #     except Exception as e:
    #         logging.error(f"Unexpected error during synthesis: {e}", exc_info=True)

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
            if voice_client.is_connected():
                await voice_client.disconnect()
            raise  # 再発生させて上位レベルでキャッチ

    async def _play_audio(self, voice_client: discord.VoiceClient, voice_data):
        try:
            audio_source = discord.FFmpegPCMAudio(
                io.BytesIO(voice_data), pipe=True)
            voice_client.play(audio_source)
            # Wait for the current audio to finish playing before returning
            while voice_client.is_playing():
                await asyncio.sleep(0.1)
        except Exception as e:
            # 詳細なエラー情報をログに記録
            logging.error(f"Error playing audio: {e}", exc_info=True)

    async def clear_playback_queue(self, guild_id):
        guild_queue = self.get_guild_playback_queue(guild_id)
        while not guild_queue.empty():
            guild_queue.get_nowait()
            guild_queue.task_done()

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
                if len(line) > BotSettings.MAX_MESSAGE_LENGTH:
                    # 長すぎるテキストの場合、メッセージを送信する
                    if message.channel:
                        await message.channel.send("テキストが長すぎるため、音声合成はスキップされました。")
                    continue  # この行の処理をスキップ

                processed_line = await text_processor.replace_content(line, message)
                guild_queue = self.get_guild_playback_queue(guild_id)
                await guild_queue.put((voice_client, processed_line, style_id))
        except Exception as e:
            logging.error(f"Error in text_to_speech: {e}")
