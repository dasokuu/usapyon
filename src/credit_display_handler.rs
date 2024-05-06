use songbird::{
    events::{Event, EventContext, EventHandler as SongbirdEventHandler},
    tracks::PlayMode,
};
use std::{collections::HashMap, future::Future, pin::Pin, sync::Arc};
use tokio::sync::Mutex;
use uuid::Uuid;

/// クレジット情報を表示するためのイベントハンドラ。
pub struct CreditDisplayHandler {
    /// トラックIDとクレジット情報のマップ。
    credits: Arc<Mutex<HashMap<Uuid, String>>>,
}

impl SongbirdEventHandler for CreditDisplayHandler {
    /// イベント発生時に実行される処理。
    ///
    /// ## Arguments
    /// * `ctx` - イベントコンテキスト。
    ///
    /// ## Returns
    /// * `Pin<Box<dyn Future<Output = Option<Event>> + Send + 'async_trait>>` - 処理結果。
    fn act<'life0, 'life1, 'life2, 'async_trait>(
        &'life0 self,
        ctx: &'life1 EventContext<'life2>,
    ) -> Pin<Box<dyn Future<Output = Option<Event>> + Send + 'async_trait>>
    where
        Self: 'async_trait,
        'life0: 'async_trait,
        'life1: 'async_trait,
        'life2: 'async_trait,
    {
        Box::pin(async move {
            if let EventContext::Track(track_events) = ctx {
                for (track_state, track_handle) in (*track_events).iter() {
                    match track_state.playing {
                        PlayMode::Play => {
                            let track_id = track_handle.uuid();
                            let credits = self.credits.lock().await;
                            if let Some(credit) = credits.get(&track_id) {
                                println!("Credit: {}", credit);
                            } else {
                                println!("Credit not found for track ID: {}", track_id);
                            }
                        }
                        _ => {}
                    }
                }
            }
            None
        })
    }
}

impl CreditDisplayHandler {
    /// 新しい `CreditDisplayHandler` を作成します。
    ///
    /// ## Returns
    /// * `CreditDisplayHandler` - 新しい `CreditDisplayHandler` インスタンス。
    pub fn new() -> Self {
        Self {
            credits: Arc::new(Mutex::new(HashMap::new())),
        }
    }
}
