use futures::future::AbortHandle;
use serenity::{model::prelude::*, prelude::*};
use std::{
    collections::{HashMap, VecDeque},
    sync::Arc,
};

/// 音声合成リクエストを表す構造体
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
    /// ## Returns
    /// * `&str`: 読み上げるテキスト。
    pub fn text(&self) -> &str {
        &self.text
    }

    /// スタイルIDを取得します。
    ///
    /// ## Returns
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

    /// 音声合成リクエストをキューに追加します。
    ///
    /// ## Arguments
    /// * `guild_id` - リクエストを追加するギルドID。
    /// * `request` - 追加するリクエスト。
    pub async fn enqueue_synthesis_request(&self, guild_id: GuildId, request: SynthesisRequest) {
        let mut queues = self.queues.lock().await;
        queues.entry(guild_id).or_default().push_back(request);
    }

    /// 現在進行中のリクエストをキャンセルします。
    ///
    /// ## Arguments
    /// * `guild_id` - キャンセルするリクエストのギルドID。
    pub async fn cancel_current_request(&self, guild_id: GuildId) {
        let mut active_requests = self.active_requests.lock().await;
        if let Some(abort_handle) = active_requests.remove(&guild_id) {
            abort_handle.abort();
        }
    }

    /// 現在進行中のリクエストをキャンセルし、キューを空にします。
    ///
    /// ## Arguments
    /// * `guild_id` - キャンセルするリクエストのギルドID。
    pub async fn cancel_current_request_and_clear_queue(&self, guild_id: GuildId) {
        self.cancel_current_request(guild_id).await;
        let mut queues = self.queues.lock().await;
        // ハッシュマップから対応するギルドIDのキューを削除。
        queues.remove(&guild_id);
    }

    /// 指定したギルドIDのキューから次のリクエストを取得し、キューから削除します。
    ///
    /// ## Arguments
    /// * `guild_id` - 検索するギルドID。
    ///
    /// ## Returns
    /// * `Option<SynthesisRequest>` - 次のリクエスト。キューが空の場合は `None`。
    pub async fn dequeue_request(&self, guild_id: GuildId) -> Option<SynthesisRequest> {
        let mut queues = self.queues.lock().await;
        if let Some(queue) = queues.get_mut(&guild_id) {
            queue.pop_front()
        } else {
            None
        }
    }

    /// ギルドIDと `AbortHandle` を指定し、アクティブなリクエストを追加します。
    ///
    /// ## Arguments
    /// * `guild_id` - 音声合成要求があったギルドID。
    /// * `abort_handle` - リクエストをキャンセルするための `AbortHandle`。
    pub async fn add_active_request(&self, guild_id: GuildId, abort_handle: AbortHandle) {
        self.active_requests
            .lock()
            .await
            .insert(guild_id, abort_handle);
    }

    /// ギルドIDを指定し、アクティブなリクエストを削除します。
    ///
    /// ## Arguments
    /// * `guild_id` - 削除するリクエストのギルドID。
    pub async fn remove_active_request(&self, guild_id: GuildId) {
        self.active_requests.lock().await.remove(&guild_id);
    }

    /// アクティブなリクエストの中に、指定したギルドIDが含まれているかどうかを返します。
    ///
    /// ## Arguments
    /// * `guild_id` - 検索するギルドID。
    ///
    /// ## Returns
    /// * `bool` - 指定したギルドIDが含まれているかどうか。
    pub async fn contains_active_request(&self, guild_id: GuildId) -> bool {
        self.active_requests.lock().await.contains_key(&guild_id)
    }
}

pub struct SynthesisQueueKey;
impl TypeMapKey for SynthesisQueueKey {
    type Value = Arc<SynthesisQueue>;
}
