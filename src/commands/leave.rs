use serenity::all::{Context, Message};

use crate::{serenity_utils::get_songbird_from_ctx, voice_channel_tracker::VoiceChannelTrackerKey};

/// ボイスチャンネルからの退出処理を行います。
///
/// ## Arguments
/// * `ctx` - ボットの状態に関する様々なデータのコンテキスト。
/// * `msg` - メッセージ。
///
/// ## Returns
/// 成功した場合は`Ok(())`、エラーが発生した場合は`Err(Box<dyn Error + Send + Sync>)`を返します。
pub async fn leave_voice_channel(ctx: &Context, msg: &Message) -> Result<(), String> {
    let songbird = get_songbird_from_ctx(&ctx).await?;
    let guild_id = msg.guild_id.ok_or("Message must be sent in a server")?;

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
