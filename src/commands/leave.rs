use serenity::all::{Context, Message};

use crate::{
    serenity_utils::{get_songbird_from_ctx, with_songbird_handler},
    usapyon_event_handler::get_synthesis_queue_manager,
    voice_channel_tracker::VoiceChannelTrackerKey,
};

/// ボイスチャンネルからの退出処理を行います。
///
/// ## Arguments
/// * `ctx` - ボットの状態に関する様々なデータのコンテキスト。
/// * `msg` - メッセージ。
///
/// ## Returns
/// 成功した場合は`Ok(())`、エラーが発生した場合は`Err(Box<dyn Error + Send + Sync>)`を返します。
pub async fn leave_command(ctx: &Context, msg: &Message) -> Result<(), String> {
    let guild_id = msg.guild_id.ok_or("Message must be sent in a server")?;
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
    let synthesis_queue_manager = get_synthesis_queue_manager(&ctx).await;
    synthesis_queue_manager
        .cancel_current_request_and_clear_queue(guild_id)
        .await;
    println!(
        "Synthesis queue cleared successfully for guild {}",
        guild_id
    );
    let songbird = get_songbird_from_ctx(&ctx).await?;
    if let Err(why) = songbird.leave(guild_id).await {
        println!("Error leaving voice channel: {:?}", why);
        return Err("Failed to leave voice channel.".into());
    }

    ctx.data
        .read()
        .await
        .get::<VoiceChannelTrackerKey>()
        .ok_or("VoiceChannelTracker not found")?
        .remove_active_channel(guild_id)
        .await;

    Ok(())
}
