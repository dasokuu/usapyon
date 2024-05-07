use serenity::{
    http::Http,
    model::id::{ChannelId, GuildId},
    prelude::TypeMapKey,
};
use songbird::{
    events::{Event, EventContext, EventHandler as SongbirdEventHandler},
    tracks::PlayMode,
};
use std::{
    collections::{HashMap, HashSet},
    future::Future,
    pin::Pin,
    sync::Arc,
};
use tokio::sync::Mutex;
use uuid::Uuid;

/// クレジット表示するために必要な情報。
pub struct CreditInfo {
    /// スタイルID。
    style_id: i32,

    /// クレジット情報を送信するチャンネルID。
    channel_id: ChannelId,

    /// HTTPクライアント。
    http: Arc<Http>,
}

impl CreditInfo {
    /// 新しい `CreditInfo` を作成します。
    ///
    /// ## Arguments
    /// * `style_id` - スタイルID。
    /// * `channel_id` - クレジット情報を送信するチャンネルID。
    /// * `http` - HTTPクライアント。
    ///
    /// ## Returns
    /// * `CreditInfo` - 新しい `CreditInfo` インスタンス。
    pub fn new(style_id: i32, channel_id: ChannelId, http: Arc<Http>) -> Self {
        Self {
            style_id,
            channel_id,
            http,
        }
    }
}

/// クレジット情報を表示するためのイベントハンドラ。
#[derive(Clone)]
pub struct CreditDisplayHandler {
    /// トラックIDとクレジット情報のマップ。
    credits: Arc<Mutex<HashMap<Uuid, CreditInfo>>>,

    /// 既にクレジットを表示したスピーカーのセット。
    used_speakers: Arc<Mutex<HashSet<String>>>,

    /// スタイルIDとクレジットテキストのマップ。
    style_id_to_credit_text: Arc<Mutex<HashMap<i32, String>>>,
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
                            if let Some(credit_info) = credits.get(&track_id) {
                                let style_id_to_credit_text =
                                    self.style_id_to_credit_text.lock().await;

                                let credit_message = format!(
                                    "VOICEVOX:{}",
                                    style_id_to_credit_text
                                        .get(&credit_info.style_id)
                                        .expect("Speaker UUID not found.")
                                );

                                credit_info
                                    .channel_id
                                    .say(&credit_info.http, credit_message)
                                    .await
                                    .unwrap();
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
    /// ## Arguments
    /// * `style_id_to_credit_text` - スタイルIDとクレジットテキストのマップ。
    ///
    /// ## Returns
    /// * `CreditDisplayHandler` - 新しい `CreditDisplayHandler` インスタンス。
    pub fn new(style_id_to_credit_text: Arc<Mutex<HashMap<i32, String>>>) -> Self {
        Self {
            credits: Arc::new(Mutex::new(HashMap::new())),
            used_speakers: Arc::new(Mutex::new(HashSet::new())),
            style_id_to_credit_text,
        }
    }

    /// トラックIDに対応するクレジット情報を登録します。
    ///
    /// ## Arguments
    /// * `track_id` - トラックID。
    /// * `credit` - クレジット情報。
    pub async fn set_credit_for_track(&mut self, track_id: Uuid, credit: CreditInfo) {
        let mut credits = self.credits.lock().await;
        credits.insert(track_id, credit);
    }
}

/// ギルドIDと`CreditDisplayHandler`のマップを格納するためのキー。
pub struct CreditDisplayHandlerKey;

impl TypeMapKey for CreditDisplayHandlerKey {
    type Value = Arc<Mutex<HashMap<GuildId, CreditDisplayHandler>>>;
}
