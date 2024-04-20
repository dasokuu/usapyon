use std::sync::Arc;
use songbird::{Songbird, SongbirdKey};
use serenity::prelude::Context;

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
