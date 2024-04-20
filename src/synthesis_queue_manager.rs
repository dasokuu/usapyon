use bytes::Bytes;
use futures::{future::AbortHandle, stream::Abortable};
use reqwest::Url;
use serenity::{model::id::GuildId, prelude::Context};
use songbird::typemap::TypeMapKey;
use std::{
    collections::HashMap,
    error::Error,
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc, Mutex,
    },
};

use crate::serenity_utils::get_songbird_from_ctx;
use crate::synthesis_queue::{SynthesisQueue, SynthesisRequest};

/// ギルドごとの音声合成の進行状況を管理する構造体。
#[derive(Clone)]
pub struct SynthesisQueueManager {
    guild_states: Arc<Mutex<HashMap<GuildId, Arc<AtomicBool>>>>,
    synthesis_queue: Arc<SynthesisQueue>,
}

impl SynthesisQueueManager {
    pub fn new() -> Self {
        SynthesisQueueManager {
            guild_states: Arc::new(Mutex::new(HashMap::new())),
            synthesis_queue: Arc::new(SynthesisQueue::new()),
        }
    }

    /// キューの処理を開始します。既に処理中の場合は何もしません。
    ///
    /// ## Arguments
    /// * `ctx` - ボットの状態に関する様々なデータのコンテキスト。
    /// * `guild_id` - サーバーID。
    /// * `synthesis_queue` - 音声合成リクエストのキュー。
    pub async fn start_processing(&self, ctx: &Context, guild_id: GuildId) {
        let is_running_state = {
            let mut states = self.guild_states.lock().expect("Mutex was poisoned");
            states
                .entry(guild_id)
                .or_insert_with(|| Arc::new(AtomicBool::new(false)))
                .clone()
        };

        if is_running_state.load(Ordering::SeqCst) {
            println!(
                "Synthesis Queue processing is already running for guild {}",
                guild_id
            );
            return;
        }

        is_running_state.store(true, Ordering::SeqCst);
        println!("Synthesis Queue processing started for guild {}", guild_id);

        tokio::spawn({
            let ctx_clone = ctx.clone();
            let synthesis_queue = self.synthesis_queue.clone();

            async move {
                loop {
                    // 既に処理中の場合。
                    if synthesis_queue.contains_active_request(guild_id).await {
                        println!("Already processing a request for guild {}", guild_id);
                        break;
                    }

                    let request = match synthesis_queue.dequeue_request(guild_id).await {
                        Some(request) => request,
                        None => {
                            println!("No requests in queue for guild {}", guild_id);
                            break;
                        }
                    };

                    let client = reqwest::Client::new();
                    let audio_query_json =
                        request_audio_query(&client, &request.text(), &request.speaker_id())
                            .await
                            .unwrap();
                    let (abort_handle, abort_registration) = AbortHandle::new_pair();
                    let future = Abortable::new(
                        request_synthesis(&client, audio_query_json, true),
                        abort_registration,
                    );

                    synthesis_queue
                        .add_active_request(guild_id, abort_handle)
                        .await;

                    match future.await {
                        Ok(Ok(synthesis_body_bytes)) => {
                            let songbird = get_songbird_from_ctx(&ctx_clone).await;
                            let handler_lock =
                                songbird.get(guild_id).expect("No Songbird handler found");
                            let mut handler = handler_lock.lock().await;
                            let source = songbird::input::Input::from(Box::from(
                                synthesis_body_bytes.to_vec(),
                            ));
                            handler.enqueue_input(source).await;

                            // 処理が成功したら、アクティブなリクエストを削除
                            synthesis_queue.remove_active_request(guild_id).await;
                        }
                        Ok(Err(_)) | Err(_) => {
                            println!("Synthesis was aborted or failed for guild {}", guild_id);
                            synthesis_queue.remove_active_request(guild_id).await;
                        }
                    }
                }

                is_running_state.store(false, Ordering::SeqCst);
                println!("Synthesis Queue processing finished for guild {}", guild_id);
            }
        });
    }

    /// 音声合成リクエストをキューに追加します。
    ///
    /// ## Arguments
    /// * `guild_id` - リクエストを追加するギルドID。
    /// * `request` - 追加するリクエスト。
    pub async fn enqueue_synthesis_request(&self, guild_id: GuildId, request: SynthesisRequest) {
        self.synthesis_queue
            .enqueue_synthesis_request(guild_id, request)
            .await;
    }

    /// 現在進行中のリクエストをキャンセルします。
    ///
    /// ## Arguments
    /// * `guild_id` - キャンセルするリクエストのギルドID。
    pub async fn cancel_current_request(&self, guild_id: GuildId) {
        self.synthesis_queue.cancel_current_request(guild_id).await;
    }

    /// 現在進行中のリクエストをキャンセルし、キューを空にします。
    ///
    /// ## Arguments
    /// * `guild_id` - キャンセルするリクエストのギルドID。
    pub async fn cancel_current_request_and_clear_queue(&self, guild_id: GuildId) {
        self.synthesis_queue
            .cancel_current_request_and_clear_queue(guild_id)
            .await;
    }
}

pub struct SynthesisQueueManagerKey;
impl TypeMapKey for SynthesisQueueManagerKey {
    type Value = Arc<SynthesisQueueManager>;
}

/// テキストとスタイルIDからオーディオクエリを生成し、サーバにリクエストを送信します。
///
/// ## Arguments
/// * `client` - reqwestクライアント。
/// * `text` - 再生するテキスト。
/// * `speaker` - スタイルID。
///
/// ## Returns
/// * `Result<serde_json::Value, Box<dyn Error + Send + Sync>>` - サーバーからのJSON形式のレスポンス、またはエラー。
async fn request_audio_query(
    client: &reqwest::Client,
    text: &str,
    speaker: &str,
) -> Result<serde_json::Value, Box<dyn Error + Send + Sync>> {
    let audio_query_headers = reqwest::header::HeaderMap::new();
    let base = "http://localhost:50021/audio_query";
    let params: HashMap<&str, &str> = [("text", text), ("speaker", speaker)]
        .iter()
        .cloned()
        .collect();

    let audio_query_url = Url::parse_with_params(base, &params).unwrap();

    let audio_query_res = client
        .post(audio_query_url)
        .headers(audio_query_headers)
        .send()
        .await?;

    let response_body = audio_query_res.text().await?;
    let response_json: serde_json::Value = serde_json::from_str(&response_body)?;

    Ok(response_json)
}

/// オーディオクエリから音声合成をリクエストします。
///
/// ## Arguments
/// * `client` - reqwestクライアント。
/// * `audio_query_json` - オーディオクエリのJSON。
/// * `is_cancellable` - キャンセル可能かどうか。
///
/// ## Returns
/// * `Bytes` - 合成した音声のバイトデータ。
async fn request_synthesis(
    client: &reqwest::Client,
    audio_query_json: serde_json::Value,
    is_cancellable: bool,
) -> Result<Bytes, Box<dyn Error + Send + Sync>> {
    let url = match is_cancellable {
        true => "http://localhost:50021/cancellable_synthesis",
        false => "http://localhost:50021/synthesis",
    };
    // 新しいリクエストのURLを作成。
    let synthesis_url = Url::parse_with_params(
        url,
        &[("speaker", "1"), ("enable_interrogative_upspeak", "true")],
    )
    .unwrap();

    // 新しいリクエストのヘッダーを設定。
    let mut synthesis_headers = reqwest::header::HeaderMap::new();
    synthesis_headers.insert("Content-Type", "application/json".parse().unwrap());

    // 新しいリクエストのボディを送信。
    let synthesis_res = client
        .post(synthesis_url)
        .headers(synthesis_headers)
        .json(&audio_query_json)
        .send()
        .await
        .unwrap();

    // レスポンスの状態を確認。
    println!("status: {:?}", synthesis_res.status());

    let synthesis_body_bytes = synthesis_res.bytes().await.unwrap();

    Ok(synthesis_body_bytes)
}
