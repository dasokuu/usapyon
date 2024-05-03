use serenity::all::{Context, Message};

use crate::{
    serenity_utils::{get_songbird_from_ctx, with_songbird_handler, get_data_from_ctx},
    voice_channel_tracker::VoiceChannelTrackerKey,
    SynthesisQueueManagerKey,
};

/// ボイスチャンネルへの参加と同時にアクティブなチャンネルの設定を行います。
/// ## Arguments
/// * `ctx` - コンテキスト、ボットの状態や設定情報へのアクセスを提供します。
/// * `msg` - 参加コマンドを送信したメッセージ情報。
///
/// ## Returns
/// * `Result<(), String>` - ボイスチャンネルへの参加操作が成功した場合は Ok(()) を、失敗した場合は Err を返します。
pub async fn join_command(ctx: &Context, msg: &Message) -> Result<(), String> {
    let guild_id = msg.guild_id.ok_or("Message must be sent in a server")?;
    let data = ctx.data.read().await;
    let tracker = data
        .get::<VoiceChannelTrackerKey>()
        .expect("VoiceChannelTracker should be available");
    // 使用済みスピーカーの情報をクリア
    tracker.clear_used_speakers(guild_id).await;
    let result = with_songbird_handler(&ctx, guild_id, |handler| {
        // 再生を停止してキューをクリア。
        handler.queue().stop();
        format!("Queue cleared successfully for guild {}", guild_id)
    })
    .await;

    match result {
        Ok(msg) => println!("{}", msg),
        Err(e) => println!("Failed to clear queue for guild {}: {:?}", guild_id, e),
    }

    // 音声合成キューをクリア。
    let synthesis_queue_manager = get_data_from_ctx::<SynthesisQueueManagerKey>(&ctx).await;
    synthesis_queue_manager
        .cancel_current_request_and_clear_queue(guild_id)
        .await;
    println!(
        "Synthesis queue cleared successfully for guild {}",
        guild_id
    );

    let text_channel_id = msg.channel_id;
    let voice_channel_id = ctx
        .cache
        .guild(guild_id)
        .and_then(|guild| guild.voice_states.get(&msg.author.id).cloned())
        .and_then(|voice_state| voice_state.channel_id)
        .ok_or("User is not in a voice channel.")?;

    let songbird_result = get_songbird_from_ctx(&ctx).await;
    match songbird_result {
        Ok(songbird) => {
            match songbird.join(guild_id, voice_channel_id).await {
                Ok(call) => {
                    // ここでエラーを String に変換
                    call.lock()
                        .await
                        .deafen(true)
                        .await
                        .map_err(|e| format!("Failed to deafen: {:?}", e))?;
                    ctx.data
                        .read()
                        .await
                        .get::<VoiceChannelTrackerKey>()
                        .ok_or("VoiceChannelTracker not found")?
                        .set_active_channel(guild_id, voice_channel_id, text_channel_id)
                        .await;
                    Ok(())
                }
                Err(why) => {
                    println!("Failed to join voice channel: {:?}", why);
                    Err("Failed to join voice channel.".into())
                }
            }
        }
        Err(e) => {
            println!("Error retrieving Songbird client: {}", e);
            Err("Failed to retrieve Songbird client.".into())
        }
    }
}
