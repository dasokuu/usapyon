// まずはボットに接続するところから。
// joinを実行したチャンネルのテキストだけをボットが読み上げるようにしたい。

extern crate dotenv;
extern crate serenity;

use bytes::Bytes;
use dotenv::dotenv;
use futures::future::{AbortHandle, AbortRegistration, Abortable};
use reqwest::Url;
use serenity::{
    async_trait,
    model::{gateway::Ready, prelude::*},
    prelude::*,
};
use songbird::{SerenityInit, Songbird, SongbirdKey};
use std::{
    collections::{HashMap, VecDeque},
    env,
    error::Error,
    sync::Arc,
};

struct SynthesisQueueKey;

impl TypeMapKey for SynthesisQueueKey {
    type Value = Arc<SynthesisQueue>;
}
// ギルドごとにリクエストのキューを管理するための構造体
struct SynthesisQueue {
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

    // リクエストをキューに追加する
    pub async fn enqueue(&self, guild_id: GuildId, request: SynthesisRequest) {
        let mut queues = self.queues.lock().await;
        queues.entry(guild_id).or_default().push_back(request);
    }

    // 次のリクエストを取得する
    pub async fn dequeue(&self, guild_id: GuildId) -> Option<SynthesisRequest> {
        let mut queues = self.queues.lock().await;
        if let Some(queue) = queues.get_mut(&guild_id) {
            queue.pop_front()
        } else {
            None
        }
    }
    // 現在進行中のリクエストをキャンセルする
    pub async fn cancel_current_request(&self, guild_id: GuildId) {
        let mut active_requests = self.active_requests.lock().await;
        if let Some(abort_handle) = active_requests.remove(&guild_id) {
            abort_handle.abort();
        }
    }
}
struct Handler;
// 合成リクエストを表す構造体
#[derive(Clone)]
struct SynthesisRequest {
    text: String,
    speaker_id: String,
}
/// `Handler`は`EventHandler`の実装です。
/// Discordからのイベントを処理するメソッドを提供します。
#[async_trait]
impl EventHandler for Handler {
    /// このメソッドは、ボットがDiscordの接続に成功したときに呼び出されます。
    ///
    /// ## Arguments
    /// * `_` - ボットの状態に関する様々なデータのコンテキスト。
    /// * `ready` - readyイベントのコンテキスト。
    async fn ready(&self, _: Context, ready: Ready) {
        println!("{} is connected!", ready.user.name);
    }

    /// このメソッドは、ボットがメッセージを受信したときに呼び出されます。
    ///
    /// ## Arguments
    /// * `ctx` - ボットの状態に関する様々なデータのコンテキスト。
    /// * `msg` - 受信したメッセージ。
    async fn message(&self, ctx: Context, msg: Message) {
        // メッセージが任意のボットから送信されたものであれば無視します。
        if msg.author.bot {
            return;
        }
        // DMは無視します。
        if msg.is_private() {
            println!("{} said in DMs: {}", msg.author.name, msg.content);
            return;
        }

        // ギルドIDを取得。
        let guild_id = msg.guild_id.expect("Guild ID not found");

        // ギルドの数を表示
        // println!("guilds: {:?}", ctx.cache.guild_count());
        // ギルドIDを表示
        println!("{} said in {}: {}", msg.author.name, guild_id, msg.content);

        // "!"から始まるメッセージとそうでないメッセージで処理を分けます。
        if msg.content.starts_with("!") {
            // !joinと!leaveコマンドを処理。
            match msg.content.as_str() {
                // ボットをユーザーがいるボイスチャンネルに参加させます。
                "!join" => {
                    join_user_voice_channel(&ctx, &msg).await.unwrap();
                }
                // ボットをボイスチャンネルから退出させます。
                "!leave" => {
                    leave_voice_channel(&ctx, &msg).await.unwrap();
                }
                "!skip" => {
                    let data_read = ctx.data.read().await;
                    let synthesis_queue = data_read
                        .get::<SynthesisQueueKey>()
                        .expect("SynthesisQueue not found in TypeMap")
                        .clone();

                    synthesis_queue.cancel_current_request(guild_id).await;
                    println!("Current request cancelled for guild {}", guild_id);
                }
                _ => {}
            }
        } else {
            // Context から SynthesisQueue を取得
            let data_read = ctx.data.read().await;
            let synthesis_queue = data_read
                .get::<SynthesisQueueKey>()
                .expect("SynthesisQueue not found in TypeMap")
                .clone();
            let request = SynthesisRequest {
                text: msg.content.to_string(),
                speaker_id: "1".to_string(),
            };
            synthesis_queue.enqueue(guild_id, request).await;
            let ctx_clone = ctx.clone(); // Clone ctx for async block

            // キューからリクエストを処理するタスクを起動
            tokio::spawn(async move {
                process_queue(&ctx_clone, guild_id, synthesis_queue).await;
            });
        }
    }

    /// ボイスチャットの状態が変更されたときに呼び出されます。
    ///
    /// ## Arguments
    /// * `ctx` - ボットの状態に関する様々なデータのコンテキスト。
    /// * `_old_state` - 変更前のボイスチャットの状態。
    /// * `new_state` - 変更後のボイスチャットの状態。
    async fn voice_state_update(
        &self,
        ctx: Context,
        _old_state: Option<VoiceState>,
        new_state: VoiceState,
    ) {
        let guild_id = new_state.guild_id.expect("Guild ID not found");
        let non_bot_users_count = count_non_bot_users_in_bot_voice_channel(&ctx, guild_id);

        println!("non_bot_users_count: {:?}", non_bot_users_count);

        // ボット以外のユーザーがボイスチャンネルに存在しなくなった場合、ボットを退出させます。
        if non_bot_users_count == 0 {
            let songbird = get_songbird_from_ctx(&ctx).await;

            if let Err(why) = songbird.leave(guild_id).await {
                println!("Error leaving voice channel: {:?}", why);
            }
        }
    }
}
async fn process_queue(ctx: &Context, guild_id: GuildId, synthesis_queue: Arc<SynthesisQueue>) {
    loop {
        let request = {
            let mut queues = synthesis_queue.queues.lock().await;
            if let Some(queue) = queues.get_mut(&guild_id) {
                if queue.is_empty() || synthesis_queue.active_requests.lock().await.contains_key(&guild_id) {
                    // 既に処理中、またはキューが空の場合は終了
                    return;
                } else {
                    // リクエストを取り出し、同時にキューから削除
                    queue.pop_front()
                }
            } else {
                // キューが存在しない場合は終了
                return;
            }
        };

        if let Some(request) = request {
            let client = reqwest::Client::new();
            let audio_query_json = request_audio_query(&client, &request.text, &request.speaker_id).await.unwrap();
            let (abort_handle, abort_registration) = AbortHandle::new_pair();
            let future = Abortable::new(
                request_synthesis(&client, audio_query_json),
                abort_registration,
            );
            synthesis_queue.active_requests.lock().await.insert(guild_id, abort_handle);

            match future.await {
                Ok(Ok(synthesis_body_bytes)) => {
                    let songbird = get_songbird_from_ctx(&ctx).await;
                    let handler_lock = songbird.get(guild_id).expect("No Songbird handler found");
                    let mut handler = handler_lock.lock().await;
                    let source = songbird::input::Input::from(Box::from(synthesis_body_bytes.to_vec()));
                    handler.enqueue_input(source).await;

                    // 処理が成功したら、アクティブなリクエストを削除
                    synthesis_queue.active_requests.lock().await.remove(&guild_id);
                }
                Ok(Err(_)) | Err(_) => {
                    println!("Synthesis was aborted or failed for guild {}", guild_id);
                    synthesis_queue.active_requests.lock().await.remove(&guild_id);
                }
            }
        }
    }
}


/// ボットが参加しているボイスチャンネルにいるボット以外のユーザーの数を取得します。
///
/// ## Arguments
/// * `ctx` - ボットの状態に関する様々なデータのコンテキスト。
/// * `guild_id` - ギルドID。
///
/// ## Returns
/// `usize` - ボットが参加しているボイスチャンネルにいるボット以外のユーザーの数。
fn count_non_bot_users_in_bot_voice_channel(ctx: &Context, guild_id: GuildId) -> usize {
    let guild = ctx.cache.guild(guild_id).expect("Guild not found");
    let bot_voice_channel_id = guild
        .voice_states
        .get(&ctx.cache.current_user().id)
        .and_then(|voice_state| voice_state.channel_id)
        .expect("Bot voice channel ID not found");

    // ボットが参加しているボイスチャンネルにいるユーザーIDを取得。
    let users_in_bot_voice_channel = guild
        .voice_states
        .iter()
        .filter_map(|(user_id, voice_state)| {
            if voice_state.channel_id == Some(bot_voice_channel_id) {
                Some(user_id)
            } else {
                None
            }
        })
        .collect::<Vec<_>>();

    println!(
        "users_in_bot_voice_channel: {:?}",
        users_in_bot_voice_channel
    );

    // ボットが参加しているボイスチャンネルにいるユーザーの数（ボットを除く）を取得。
    // デバッグ用にユーザーがキャッシュに含まれているか、ボットかどうかを表示。
    let non_bot_users_count = users_in_bot_voice_channel
        .iter()
        .filter(|user_id| match user_id.to_user_cached(&ctx) {
            Some(user) => {
                if user.bot {
                    println!("{} is a bot user", user_id);
                    false
                } else {
                    println!("{} is not a bot user", user_id);
                    true
                }
            }
            None => {
                println!("{} is not cached", user_id);
                false
            }
        })
        .count();

    non_bot_users_count
}

/// コンテキストデータからSongbirdクライアントを非同期に取得します。
///
/// ## Arguments
/// * `ctx` - ボットの状態に関する様々なデータのコンテキスト。
///
/// ## Returns
/// Songbirdクライアント。
async fn get_songbird_from_ctx(ctx: &Context) -> Arc<Songbird> {
    let data = ctx.data.read().await;
    data.get::<SongbirdKey>()
        .cloned()
        .expect("Failed to retrieve Songbird client")
}

/// ユーザーがいるボイスチャンネルにボットを非同期に参加させます。
///
/// ## Arguments
/// * `ctx` - ボットの状態に関する様々なデータのコンテキスト。
/// * `msg` - メッセージ。
///
/// ## Returns
/// 成功した場合は`Ok(())`、エラーが発生した場合は`Err(Box<dyn Error + Send + Sync>)`を返します。
async fn join_user_voice_channel(
    ctx: &Context,
    msg: &Message,
) -> Result<(), Box<dyn Error + Send + Sync>> {
    // コンテキストデータからSongbirdクライアントを取得。
    let songbird = get_songbird_from_ctx(&ctx).await;

    let guild_id = match msg.guild_id {
        Some(guild_id) => guild_id,
        None => return Err("Message must be sent in a server".into()),
    };

    println!("guild_id: {:?}", guild_id);

    let channel_id = match ctx
        .cache
        .guild(guild_id)
        .and_then(|guild| guild.voice_states.get(&msg.author.id).cloned())
        .and_then(|voice_state| voice_state.channel_id)
    {
        Some(channel_id) => channel_id,
        None => return Err("User is not in a voice channel".into()),
    };
    println!("Channel ID: {:?}", channel_id);

    // ユーザーがいるチャンネルにボットを参加させます。
    let result = songbird.join(guild_id, channel_id).await;

    if let Ok(call) = result {
        // ボットをスピーカーミュートにする
        if let Err(why) = call.lock().await.deafen(true).await {
            println!("Failed to deafen: {:?}", why);
        }
    } else if let Err(why) = result {
        println!("Error joining voice channel: {:?}", why);
    }

    Ok(())
}

/// ボイスチャンネルからボットを非同期に退出させます。
///
/// ## Arguments
/// * `ctx` - ボットの状態に関する様々なデータのコンテキスト。
/// * `msg` - メッセージ。
///
/// ## Returns
/// 成功した場合は`Ok(())`、エラーが発生した場合は`Err(Box<dyn Error + Send + Sync>)`を返します。
async fn leave_voice_channel(
    ctx: &Context,
    msg: &Message,
) -> Result<(), Box<dyn Error + Send + Sync>> {
    let songbird = get_songbird_from_ctx(&ctx).await;

    let guild_id = match msg.guild_id {
        Some(guild_id) => guild_id,
        None => return Err("Message must be sent in a server".into()),
    };

    if let Err(why) = songbird.leave(guild_id).await {
        println!("Error leaving voice channel: {:?}", why);
    }

    Ok(())
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
///
/// ## Returns
/// * `Bytes` - 合成した音声のバイトデータ。
async fn request_synthesis(
    client: &reqwest::Client,
    audio_query_json: serde_json::Value,
) -> Result<Bytes, Box<dyn Error + Send + Sync>> {
    // 新しいリクエストのURLを作成。
    let synthesis_url = Url::parse_with_params(
        "http://localhost:50021/cancellable_synthesis",
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

#[tokio::main]
async fn main() {
    dotenv().ok();

    let token = env::var("DISCORD_TOKEN").expect("DISCORD_TOKEN must be set");
    // println!("DISCORD_TOKEN: {}", token);

    // 必要なインテントを有効にします。
    // GUILDS: サーバーのリストを取得するため。
    let intents = GatewayIntents::GUILD_MEMBERS
                                | GatewayIntents::GUILD_MESSAGES
                                | GatewayIntents::MESSAGE_CONTENT // メッセージの内容を取得するため。
                                | GatewayIntents::DIRECT_MESSAGES
                                | GatewayIntents::GUILD_VOICE_STATES
                                | GatewayIntents::GUILDS
                                | GatewayIntents::GUILD_PRESENCES; // ボット起動後にボイスチャンネルに参加したユーザーを取得するため。

    // すべてのインテントを有効にします。
    // let intents = GatewayIntents::all();

    let mut serenity_client = Client::builder(&token, intents)
        .event_handler(Handler)
        .register_songbird()
        .await
        .expect("Error creating client");
    let synthesis_queue = Arc::new(SynthesisQueue::new());
    {
        let mut data = serenity_client.data.write().await;
        data.insert::<SynthesisQueueKey>(synthesis_queue.clone());
    }
    if let Err(why) = serenity_client.start().await {
        println!("Client error: {:?}", why);
    }
}
