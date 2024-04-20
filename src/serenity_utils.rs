use serenity::prelude::Context;
use songbird::{Songbird, SongbirdKey};
use std::sync::Arc;
use tokio::sync::MutexGuard;
use songbird::Call;
use serenity::model::id::GuildId;


/// コンテキストデータからSongbirdクライアントを非同期に取得します。
///
/// ## Arguments
/// * `ctx` - ボットの状態に関する様々なデータのコンテキスト。
///
/// ## Returns
/// Songbirdクライアント。
pub async fn get_songbird_from_ctx(ctx: &Context) -> Arc<Songbird> {
    let data = ctx.data.read().await;
    data.get::<SongbirdKey>()
        .cloned()
        .expect("Failed to retrieve Songbird client")
}

/// songbird の音声ハンドラを取得し、指定された関数を実行します。
///
/// ## Arguments
/// * `ctx` - ボットの状態に関する様々なデータのコンテキスト。
/// * `guild_id` - ギルドID。
/// * `f` - 音声ハンドラを操作する関数。
///
/// ## Returns
/// `Result<R, String>` - 指定された関数の実行結果、またはエラー。
///
/// ## Type Parameters
/// * `F` - 音声ハンドラを操作する関数の型。
/// * `R` - 関数の戻り値の型。
pub async fn with_songbird_handler<F, R>(ctx: &Context, guild_id: GuildId, f: F) -> Result<R, String>
where
    F: FnOnce(MutexGuard<'_, Call>) -> R + Send,
    R: Send,
{
    let songbird = get_songbird_from_ctx(&ctx).await;
    let handler_lock = songbird
        .get(guild_id)
        .ok_or_else(|| "No Songbird handler found".to_string())?;
    let handler = handler_lock.lock().await;

    Ok(f(handler))
}