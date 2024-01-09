

async def text_to_speech(
    self,
    voice_client: discord.VoiceClient,
    text,
    style_id,
    guild_id,
    message_handler: MessageToSpeechProcessor,
    synth_server: VoiceSynthService,
    message: discord.Message = None,
):
    if not voice_client or not voice_client.is_connected():
        logging.error("Voice client is not connected.")
        return

    try:
        lines = text.split("\n")
        for line in filter(None, lines):
            # MessageToSpeechProcessorを用いてテキストを処理
            processed_line = await message_handler.replace_content(line, message)
            guild_queue = synth_server.get_guild_playback_queue(guild_id)
            await guild_queue.put((voice_client, processed_line, style_id))
    except Exception as e:
        logging.error(f"Error in text_to_speech: {e}")
        # Handle specific exceptions and add remediation here.
