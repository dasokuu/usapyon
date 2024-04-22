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
        Arc,
    },
};
use tokio::sync::Mutex;

use crate::synthesis_queue::{SynthesisQueue, SynthesisRequest};
use crate::{retry_handler::RetryHandler, serenity_utils::get_songbird_from_ctx};

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
    pub async fn start_processing(
        &self,
        ctx: &Context,
        guild_id: GuildId,
    ) -> Result<(), Box<dyn Error + Send + Sync>> {
        let is_running_state = {
            let mut states = self.guild_states.lock().await;
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
            return Ok(());
        }

        is_running_state.store(true, Ordering::SeqCst);
        println!("Synthesis Queue processing started for guild {}", guild_id);

        let ctx_clone = ctx.clone();
        let synthesis_queue = self.synthesis_queue.clone();

        let handle = tokio::spawn({
            async move {
                SynthesisQueueManager::process_synthesis_queue(
                    &ctx_clone,
                    guild_id,
                    synthesis_queue,
                    is_running_state,
                )
                .await
            }
        });

        handle.await??;

        // println!("start_processing finished for guild {}", guild_id);
        Ok(())
    }

    /// 音声合成リクエストをキューに追加します。
    ///
    /// ## Arguments
    /// * `guild_id` - リクエストを追加するギルドID。
    /// * `request` - 追加するリクエスト。
    pub async fn add_request_to_synthesis_queue(
        &self,
        guild_id: GuildId,
        request: SynthesisRequest,
    ) {
        self.synthesis_queue
            .add_request_to_synthesis_queue(guild_id, request)
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

    /// キューからリクエストがなくなるまで音声合成を続けます。
    ///
    /// ## Arguments
    /// * `ctx` - ボットの状態に関する様々なデータのコンテキスト。
    /// * `guild_id` - サーバーID。
    /// * `synthesis_queue` - 音声合成リクエストのキュー。
    /// * `is_running_state` - キューの処理状態。
    async fn process_synthesis_queue(
        ctx: &Context,
        guild_id: GuildId,
        synthesis_queue: Arc<SynthesisQueue>,
        is_running_state: Arc<AtomicBool>,
    ) -> Result<(), Box<dyn Error + Send + Sync>> {
        loop {
            let request = match synthesis_queue.dequeue_request(guild_id).await {
                Some(request) => request,
                None => {
                    println!("No requests in queue for guild {}", guild_id);
                    break;
                }
            };

            // オーディオクエリの要求と音声合成の要求をまとめて中断可能にします。
            let (abort_handle, abort_registration) = AbortHandle::new_pair();
            let future = Abortable::new(
                request_synthesis_with_audio_query(request, true),
                abort_registration,
            );

            synthesis_queue
                .add_active_request(guild_id, abort_handle)
                .await;

            match future.await {
                Ok(Ok(synthesis_body_bytes)) => match get_songbird_from_ctx(&ctx).await {
                    Ok(songbird) => {
                        let handler_lock =
                            songbird.get(guild_id).expect("No Songbird handler found");
                        let mut handler = handler_lock.lock().await;
                        let source =
                            songbird::input::Input::from(Box::from(synthesis_body_bytes.to_vec()));
                        handler.enqueue_input(source).await;

                        synthesis_queue.remove_active_request(guild_id).await;
                    }
                    Err(e) => {
                        println!("Failed to get Songbird client: {}", e);
                        return Err(Box::new(std::io::Error::new(std::io::ErrorKind::Other, e)));
                    }
                },
                Ok(Err(_)) | Err(_) => {
                    println!("Synthesis was aborted or failed for guild {}", guild_id);
                    synthesis_queue.remove_active_request(guild_id).await;
                }
            }
        }

        is_running_state.store(false, Ordering::SeqCst);
        println!("Synthesis Queue processing finished for guild {}", guild_id);
        Ok(())
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
    style_id: &str,
) -> Result<serde_json::Value, Box<dyn Error + Send + Sync>> {
    let audio_query_headers = reqwest::header::HeaderMap::new();
    let base = "http://localhost:50021/audio_query";
    let params: HashMap<&str, &str> = [("text", text), ("speaker", style_id)]
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
/// * `style_id` - スタイルID（ユーザーに基づいた音声スタイルを指定）。
/// * `is_cancellable` - キャンセル可能かどうか。
///
/// ## Returns
/// * `Bytes` - 合成した音声のバイトデータ。
async fn request_synthesis(
    client: &reqwest::Client,
    audio_query_json: serde_json::Value,
    style_id: &str,
    is_cancellable: bool,
) -> Result<Bytes, Box<dyn Error + Send + Sync>> {
    let url = match is_cancellable {
        true => "http://localhost:50021/cancellable_synthesis",
        false => "http://localhost:50021/synthesis",
    };

    // 新しいリクエストのURLを作成。
    let synthesis_url = Url::parse_with_params(
        url,
        &[
            ("speaker", style_id),
            ("enable_interrogative_upspeak", "true"),
        ],
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
        .await?;

    // レスポンスの状態を確認。
    println!("status: {:?}", synthesis_res.status());

    let synthesis_body_bytes = synthesis_res.bytes().await?;

    Ok(synthesis_body_bytes)
}

/// オーディオクエリを要求し、成功した場合は音声合成を要求します。
///
/// ## Arguments
/// * `request` - 音声合成リクエスト。
/// * `is_cancellable` - キャンセル可能かどうか。
///
/// ## Returns
/// * `Result<Bytes, Box<dyn Error + Send + Sync>>` - 合成した音声のバイトデータ、またはエラー。
pub async fn request_synthesis_with_audio_query(
    request: SynthesisRequest,
    is_cancellable: bool,
) -> Result<Bytes, Box<dyn Error + Send + Sync>> {
    let client = reqwest::Client::new();

    // オーディオクエリのリクエスト。
    // 失敗した場合は何度かリトライする。
    let retry_config = RetryHandler::new(5, 2);
    let result_audio_query = retry_config
        .execute_with_exponential_backoff_retry(|| {
            request_audio_query(&client, &request.text(), &request.speaker_id())
        })
        .await;

    // 一定回数リトライに失敗したら、次のリクエストに進みます。
    let audio_query_json = match result_audio_query {
        Ok(audio_query_json) => audio_query_json,
        Err(e) => {
            println!("Failed to request audio query: {}", e);
            return Err(Box::new(std::io::Error::new(std::io::ErrorKind::Other, e)));
        }
    };

    // オーディオクエリから音声合成をリクエスト。
    // 失敗した場合は何度かリトライする。
    let result_synthesis = retry_config
        .execute_with_exponential_backoff_retry(|| {
            request_synthesis(
                &client,
                audio_query_json.clone(),
                &request.speaker_id(),
                is_cancellable,
            )
        })
        .await;

    // 一定回数リトライに失敗したら、次のリクエストに進みます。
    let synthesis_body_bytes = match result_synthesis {
        Ok(synthesis_body_bytes) => synthesis_body_bytes,
        Err(e) => {
            println!("Failed to request synthesis: {}", e);
            return Err(Box::new(std::io::Error::new(std::io::ErrorKind::Other, e)));
        }
    };

    Ok(synthesis_body_bytes)
}
