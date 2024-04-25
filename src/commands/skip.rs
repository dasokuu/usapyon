use serenity::all::{Context, GuildId};

use crate::serenity_utils::with_songbird_handler;
use crate::usapyon_event_handler::get_synthesis_queue_manager;

pub async fn skip_command(ctx: &Context, guild_id: GuildId) {
    // songbird の音声ハンドラでスキップを試みます。
    let result = with_songbird_handler(&ctx, guild_id, |handler| {
        handler
            .queue()
            .current()
            .map(|_| handler.queue().skip().is_ok())
    })
    .await;

    match result {
        Ok(Some(true)) => {
            println!("Track skipped successfully for guild {}", guild_id);
        }
        // トラックが存在しない、またはスキップに失敗した場合、音声合成リクエストをキャンセル。
        Ok(Some(false)) | Ok(None) => {
            let synthesis_queue_manager = get_synthesis_queue_manager(&ctx).await;
            synthesis_queue_manager
                .cancel_current_request(guild_id)
                .await;
            println!(
                "No track was playing, or skip failed. Synthesis request cancelled for guild {}",
                guild_id
            );
        }
        Err(e) => {
            println!("Failed to handle track for guild {}: {:?}", guild_id, e);
        }
    }
}
