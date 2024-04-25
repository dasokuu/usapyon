use serenity::all::{Context, GuildId};

use crate::serenity_utils::with_songbird_handler;
use crate::usapyon_event_handler::get_synthesis_queue_manager;

pub async fn clear_command(ctx: &Context, guild_id: GuildId) {
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
}
