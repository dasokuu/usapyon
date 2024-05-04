use serenity::model::id::GuildId;
use serenity::prelude::{Context, TypeMapKey};
use songbird::Call;
use songbird::{Songbird, SongbirdKey};
use std::sync::Arc;
use tokio::sync::MutexGuard;

/// コンテキストデータからSongbirdクライアントを非同期に取得します。
///
/// ## Arguments
/// * `ctx` - ボットの状態に関する様々なデータのコンテキスト。
///
/// ## Returns
/// Songbirdクライアント。
pub async fn get_songbird_from_ctx(ctx: &Context) -> Result<Arc<Songbird>, String> {
    let data = ctx.data.read().await;
    data.get::<SongbirdKey>()
        .cloned()
        .ok_or_else(|| "Failed to retrieve Songbird client".to_string())
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
pub async fn with_songbird_handler<F, R>(
    ctx: &Context,
    guild_id: GuildId,
    func: F,
) -> Result<R, String>
where
    F: FnOnce(MutexGuard<'_, Call>) -> R + Send,
    R: Send,
{
    let songbird = get_songbird_from_ctx(ctx).await?;
    let handler_lock = songbird
        .get(guild_id)
        .ok_or_else(|| "No Songbird handler found for the guild".to_string())?;
    let handler = handler_lock.lock().await;
    Ok(func(handler))
}

/// データコンテキストから、指定されたキーに関連付けられたデータを取得します。
///
/// ## Arguments
/// * `ctx` - ボットの状態に関する様々なデータのコンテキスト。
///
/// ## Returns
/// * `Arc<T>` - 指定されたキーに関連付けられたデータ。
pub async fn get_data_from_ctx<T: TypeMapKey>(ctx: &Context) -> T::Value
where
    T::Value: Clone,
{
    // どの型で呼び出されたか表示。
    println!("Called with type: {:?}", std::any::type_name::<T>());
    
    let data_read = ctx.data.read().await;
    data_read
        .get::<T>()
        .expect("Failed to retrieve data from context")
        .clone()
}
