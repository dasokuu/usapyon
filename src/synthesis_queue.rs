extern crate dotenv;
extern crate serenity;

use futures::future::AbortHandle;
use serenity::{model::prelude::*, prelude::*};
use std::{
    collections::{HashMap, VecDeque},
    sync::Arc,
};
use tokio::sync::MutexGuard;

// 音声合成リクエストを表す構造体
#[derive(Clone)]
pub struct SynthesisRequest {
    text: String,
    speaker_id: String,
}

impl SynthesisRequest {
    pub fn new(text: String, speaker_id: String) -> Self {
        SynthesisRequest { text, speaker_id }
    }

    /// 読み上げるテキストを取得します。
    /// 
    /// # Returns
    /// * `&str`: 読み上げるテキスト。
    pub fn text(&self) -> &str {
        &self.text
    }

    /// スタイルIDを取得します。
    /// 
    /// # Returns
    /// * `&str`: スタイルID。
    pub fn speaker_id(&self) -> &str {
        &self.speaker_id
    }
}

/// ギルドごとにリクエストのキューを管理するための構造体。
pub struct SynthesisQueue {
    queues: Mutex<HashMap<GuildId, VecDeque<SynthesisRequest>>>,
    active_requests: Mutex<HashMap<GuildId, AbortHandle>>,
}

impl SynthesisQueue {
    pub fn new() -> Self {
        SynthesisQueue {
            queues: Mutex::new(HashMap::new()),
            active_requests: Mutex::new(HashMap::new()),
        }
    }

    /// リクエストをキューに追加します。
    pub async fn enqueue_synthesis_request(&self, guild_id: GuildId, request: SynthesisRequest) {
        let mut queues = self.queues.lock().await;
        queues.entry(guild_id).or_default().push_back(request);
    }

    /// 現在進行中のリクエストをキャンセルします。
    pub async fn cancel_current_request(&self, guild_id: GuildId) {
        let mut active_requests = self.active_requests.lock().await;
        if let Some(abort_handle) = active_requests.remove(&guild_id) {
            abort_handle.abort();
        }
    }

    /// 現在進行中のリクエストをキャンセルし、キューを空にします。
    pub async fn cancel_current_request_and_clear_queue(&self, guild_id: GuildId) {
        self.cancel_current_request(guild_id).await;
        let mut queues = self.queues.lock().await;
        // ハッシュマップから対応するギルドIDのキューを削除。
        queues.remove(&guild_id);
    }

    pub async fn get_queues_lock(&self) -> MutexGuard<'_, HashMap<GuildId, VecDeque<SynthesisRequest>>> {
        self.queues.lock().await
    }

    pub async fn get_active_requests_lock(&self) -> MutexGuard<'_, HashMap<GuildId, AbortHandle>> {
        self.active_requests.lock().await
    }
}

pub struct SynthesisQueueKey;
impl TypeMapKey for SynthesisQueueKey {
    type Value = Arc<SynthesisQueue>;
}
