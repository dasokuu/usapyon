// joinを実行したチャンネルのテキストだけをボットが読み上げるようにしたい。

extern crate dotenv;
extern crate serenity;

use bytes::Bytes;
use dotenv::dotenv;
use futures::future::{AbortHandle, Abortable};
use regex::Regex;
use reqwest::Url;
use serenity::model::channel::Channel;
use serenity::model::id::{ChannelId, RoleId, UserId};
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

// 音声合成リクエストを表す構造体
#[derive(Clone)]
struct SynthesisRequest {
    text: String,
    speaker_id: String,
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
    pub async fn enqueue_synthesis_request(&self, guild_id: GuildId, request: SynthesisRequest) {
        let mut queues = self.queues.lock().await;
        queues.entry(guild_id).or_default().push_back(request);
    }

    // 現在進行中のリクエストをキャンセルする
    pub async fn cancel_current_request(&self, guild_id: GuildId) {
        let mut active_requests = self.active_requests.lock().await;
        if let Some(abort_handle) = active_requests.remove(&guild_id) {
            abort_handle.abort();
        }
    }
}

struct SynthesisQueueKey;
impl TypeMapKey for SynthesisQueueKey {
    type Value = Arc<SynthesisQueue>;
}

struct VoiceChannelTracker {
    active_channels: Mutex<HashMap<GuildId, (ChannelId, ChannelId)>>, // (VoiceChannelId, TextChannelId)
}

impl VoiceChannelTracker {
    pub fn new() -> Self {
        VoiceChannelTracker {
            active_channels: Mutex::new(HashMap::new()),
        }
    }

    pub async fn remove_active_channel(&self, guild_id: GuildId) {
        let mut channels = self.active_channels.lock().await;
        channels.remove(&guild_id);
    }

    pub async fn set_active_channel(
        &self,
        guild_id: GuildId,
        voice_channel_id: ChannelId,
        text_channel_id: ChannelId,
    ) {
        let mut channels = self.active_channels.lock().await;
        channels.insert(guild_id, (voice_channel_id, text_channel_id));
    }

    pub async fn is_active_text_channel(
        &self,
        guild_id: GuildId,
        text_channel_id: ChannelId,
    ) -> bool {
        let channels = self.active_channels.lock().await;
        matches!(channels.get(&guild_id), Some((_, id)) if *id == text_channel_id)
    }
}

struct VoiceChannelTrackerKey;
impl TypeMapKey for VoiceChannelTrackerKey {
    type Value = Arc<VoiceChannelTracker>;
}

struct Handler;
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
        if msg.author.bot || msg.is_private() {
            return;
        }

        let guild_id = msg.guild_id.expect("Guild ID not found");

        if msg.content == "!join" {
            if let Err(e) = join_voice_channel(&ctx, &msg).await {
                println!("Error processing !join command: {}", e);
            }
        }

        let is_active_channel = {
            let data_read = ctx.data.read().await;
            data_read
                .get::<VoiceChannelTrackerKey>()
                .expect("VoiceChannelTracker not found")
                .is_active_text_channel(guild_id, msg.channel_id)
                .await
        };

        if !is_active_channel {
            return; // アクティブなチャンネルでなければ何もしない
        }
        if msg.content.starts_with("!") {
            match msg.content.as_str() {
                "!leave" => {
                    if let Err(e) = leave_voice_channel(&ctx, &msg).await {
                        println!("Error processing !leave command: {}", e);
                    }
                }
                "!skip" => {
                    // Retrieve the Songbird instance and attempt to skip the current track
                    let songbird = get_songbird_from_ctx(&ctx).await;
                    let handler_lock = songbird.get(guild_id).expect("No Songbird handler found");
                    let handler = handler_lock.lock().await;

                    // Check if there is a current track and attempt to skip it
                    if handler.queue().current().is_some() {
                        // Attempt to skip the current track and handle the result
                        match handler.queue().skip() {
                            Ok(_) => println!("Track skipped successfully for guild {}", guild_id),
                            Err(e) => {
                                println!("Failed to skip track for guild {}: {:?}", guild_id, e)
                            }
                        }
                    } else {
                        let data_read = ctx.data.read().await;
                        let synthesis_queue = data_read
                            .get::<SynthesisQueueKey>()
                            .expect("SynthesisQueue not found in TypeMap")
                            .clone();

                        // Cancel the current synthesis request
                        synthesis_queue.cancel_current_request(guild_id).await;
                        println!(
                        "No track was playing. Current synthesis request cancelled for guild {}",
                        guild_id
                    );
                    }
                }
                _ => {}
            }
            return;
        }

        println!("msg.content: {}", msg.content);

        let sanitized_content: String = sanitize_message(&ctx, &msg.content, guild_id).await;
        println!("Sanitized message: {}", sanitized_content);

        // メッセージを読み上げる処理
        // Context から SynthesisQueue を取得
        let data_read = ctx.data.read().await;
        let synthesis_queue = data_read
            .get::<SynthesisQueueKey>()
            .expect("SynthesisQueue not found in TypeMap")
            .clone();
        let text_to_read = if sanitized_content.chars().count() > 200 {
            sanitized_content.chars().take(200).collect::<String>() + "...以下略"
        } else {
            sanitized_content.clone()
        };
        let request = SynthesisRequest {
            text: text_to_read.to_string(),
            speaker_id: "1".to_string(),
        };
        synthesis_queue
            .enqueue_synthesis_request(guild_id, request)
            .await;
        let ctx_clone = ctx.clone(); // Clone ctx for async block

        // キューからリクエストを処理するタスクを起動
        tokio::spawn(async move {
            process_queue(&ctx_clone, guild_id, synthesis_queue).await;
        });
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
        let guild_id = match new_state.guild_id {
            Some(guild_id) => guild_id,
            None => {
                eprintln!("Voice state update without guild ID.");
                return;
            }
        };

        match count_non_bot_users_in_bot_voice_channel(&ctx, guild_id) {
            Some(non_bot_users_count) => {
                println!("non_bot_users_count: {:?}", non_bot_users_count);

                // ボット以外のユーザーがボイスチャンネルに存在しなくなった場合、ボットを退出させます。
                if non_bot_users_count == 0 {
                    let songbird = get_songbird_from_ctx(&ctx).await;

                    if let Err(why) = songbird.leave(guild_id).await {
                        println!("Error leaving voice channel: {:?}", why);
                    }

                    ctx.data
                        .read()
                        .await
                        .get::<VoiceChannelTrackerKey>()
                        .expect("VoiceChannelTracker not found")
                        .remove_active_channel(guild_id)
                        .await;
                }
            }
            None => {
                println!("Failed to determine the count of non-bot users in the voice channel.");
            }
        }
    }
}

/// 音声合成キューを処理します。
///
/// ## Arguments
/// * `ctx` - ボットの状態に関する様々なデータのコンテキスト。
/// * `guild_id` - ギルドID。
/// * `synthesis_queue` - 音声合成キュー。
async fn process_queue(ctx: &Context, guild_id: GuildId, synthesis_queue: Arc<SynthesisQueue>) {
    loop {
        let request = {
            let mut queues = synthesis_queue.queues.lock().await;
            if let Some(queue) = queues.get_mut(&guild_id) {
                if queue.is_empty()
                    || synthesis_queue
                        .active_requests
                        .lock()
                        .await
                        .contains_key(&guild_id)
                {
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
            let audio_query_json = request_audio_query(&client, &request.text, &request.speaker_id)
                .await
                .unwrap();
            let (abort_handle, abort_registration) = AbortHandle::new_pair();
            let future = Abortable::new(
                request_synthesis(&client, audio_query_json),
                abort_registration,
            );
            synthesis_queue
                .active_requests
                .lock()
                .await
                .insert(guild_id, abort_handle);

            match future.await {
                Ok(Ok(synthesis_body_bytes)) => {
                    let songbird = get_songbird_from_ctx(&ctx).await;
                    let handler_lock = songbird.get(guild_id).expect("No Songbird handler found");
                    let mut handler = handler_lock.lock().await;
                    let source =
                        songbird::input::Input::from(Box::from(synthesis_body_bytes.to_vec()));
                    handler.enqueue_input(source).await;

                    // 処理が成功したら、アクティブなリクエストを削除
                    synthesis_queue
                        .active_requests
                        .lock()
                        .await
                        .remove(&guild_id);
                }
                Ok(Err(_)) | Err(_) => {
                    println!("Synthesis was aborted or failed for guild {}", guild_id);
                    synthesis_queue
                        .active_requests
                        .lock()
                        .await
                        .remove(&guild_id);
                }
            }
        }
    }
}

/// ボットが参加しているボイスチャンネルにいるボット以外のユーザーの数を取得します。
/// エラーが発生した場合はNoneを返します。
///
/// ## Arguments
/// * `ctx` - ボットの状態に関する様々なデータのコンテキスト。
/// * `guild_id` - ギルドID。
///
/// ## Returns
/// `Option<usize>` - ボット以外のユーザーの数、またはNone。
fn count_non_bot_users_in_bot_voice_channel(ctx: &Context, guild_id: GuildId) -> Option<usize> {
    let guild = ctx.cache.guild(guild_id)?;

    let bot_voice_channel_id = guild
        .voice_states
        .get(&ctx.cache.current_user().id)?
        .channel_id?;

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

    // ボットを除くユーザーの数を計算。
    let non_bot_users_count = users_in_bot_voice_channel
        .iter()
        .filter(|user_id| !ctx.cache.user(**user_id).map_or(false, |user| user.bot))
        .count();

    Some(non_bot_users_count)
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

/// ボイスチャンネルへの参加と同時にアクティブなチャンネルの設定を行います。
/// # 引数
/// * `ctx` - コンテキスト、ボットの状態や設定情報へのアクセスを提供します。
/// * `msg` - 参加コマンドを送信したメッセージ情報。
///
/// # 戻り値
/// ボイスチャンネルへの参加操作が成功した場合は Ok(()) を、失敗した場合は Err を返します。
async fn join_voice_channel(ctx: &Context, msg: &Message) -> Result<(), String> {
    let guild_id = msg.guild_id.ok_or("Message must be sent in a server")?;
    let text_channel_id = msg.channel_id;

    let voice_channel_id = ctx
        .cache
        .guild(guild_id)
        .and_then(|guild| guild.voice_states.get(&msg.author.id).cloned())
        .and_then(|voice_state| voice_state.channel_id)
        .ok_or("User is not in a voice channel.")?;

    let songbird = get_songbird_from_ctx(&ctx).await;
    match songbird.join(guild_id, voice_channel_id).await {
        Ok(call) => {
            // ここでエラーを String に変換
            call.lock()
                .await
                .deafen(true)
                .await
                .map_err(|e| format!("Failed to deafen: {:?}", e))?;
            ctx.data
                .read()
                .await
                .get::<VoiceChannelTrackerKey>()
                .ok_or("VoiceChannelTracker not found")?
                .set_active_channel(guild_id, voice_channel_id, text_channel_id)
                .await;
            Ok(())
        }
        Err(why) => {
            println!("Failed to join voice channel: {:?}", why);
            Err("Failed to join voice channel.".into())
        }
    }
}

/// ボイスチャンネルからの退出処理を行います。
///
/// ## Arguments
/// * `ctx` - ボットの状態に関する様々なデータのコンテキスト。
/// * `msg` - メッセージ。
///
/// ## Returns
/// 成功した場合は`Ok(())`、エラーが発生した場合は`Err(Box<dyn Error + Send + Sync>)`を返します。
async fn leave_voice_channel(ctx: &Context, msg: &Message) -> Result<(), String> {
    let songbird = get_songbird_from_ctx(&ctx).await;

    let guild_id = msg.guild_id.ok_or("Message must be sent in a server")?;

    if let Err(why) = songbird.leave(guild_id).await {
        println!("Error leaving voice channel: {:?}", why);
        return Err("Failed to leave voice channel.".into());
    }
    ctx.data
        .read()
        .await
        .get::<VoiceChannelTrackerKey>()
        .ok_or("VoiceChannelTracker not found")?
        .remove_active_channel(guild_id)
        .await;
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

async fn sanitize_message(ctx: &Context, msg: &str, guild_id: GuildId) -> String {
    let re_user = Regex::new(r"<@!?(\d+)>").unwrap();
    let re_channel = Regex::new(r"<#(\d+)>").unwrap();
    let re_role = Regex::new(r"<@&(\d+)>").unwrap();
    let re_emoji = Regex::new(r"<:([^:]+):\d+>").unwrap();

    let mut sanitized = msg.to_string();

    // 「<@ユーザーID>」を表示名に置き換えます。
    // 表示名がなければユーザー名に置き換えます。
    for cap in re_user.captures_iter(msg) {
        if let Ok(id) = cap[1].parse::<u64>() {
            // if let Some(guild) = ctx.cache.guild(guild_id) {
            //     if let Some(member) = guild.members.get(&UserId::new(id)) {
            //         let display_name = member.nick.as_ref().unwrap_or(&member.user.name);
            //         sanitized = sanitized.replace(&cap[0], display_name);
            //     } else if let Ok(user) = UserId::new(id).to_user(&ctx.http).await {
            //         sanitized = sanitized.replace(&cap[0], &user.name);
            //     }
            // }
            if let Some(member) = get_member_from_ctx(&ctx, guild_id, UserId::new(id)) {
                let display_name = member.nick.as_ref().unwrap_or(&member.user.name);
                sanitized = sanitized.replace(&cap[0], display_name);
            } else if let Ok(user) = UserId::new(id).to_user(&ctx.http).await {
                sanitized = sanitized.replace(&cap[0], &user.name);
            }
        }
    }

    // Replace channel mentions
    for cap in re_channel.captures_iter(msg) {
        if let Ok(id) = cap[1].parse::<u64>() {
            if let Ok(channel) = ChannelId::new(id).to_channel(&ctx.http).await {
                if let Channel::Guild(channel) = channel {
                    sanitized = sanitized.replace(&cap[0], &channel.name);
                }
            }
        }
    }

    // Replace role mentions
    for cap in re_role.captures_iter(msg) {
        if let Ok(id) = cap[1].parse::<u64>() {
            if let Some(guild) = ctx.cache.guild(guild_id) {
                if let Some(role) = guild.roles.get(&RoleId::new(id)) {
                    sanitized = sanitized.replace(&cap[0], &role.name);
                }
            }
        }
    }

    // Replace custom emojis
    sanitized = re_emoji
        .replace_all(&sanitized, |caps: &regex::Captures| format!("{}", &caps[1]))
        .to_string();

    sanitized
}

fn get_member_from_ctx(ctx: &Context, guild_id: GuildId, user_id: UserId) -> Option<Member> {
    let guild = match ctx.cache.guild(guild_id) {
        Some(guild) => guild,
        None => return None,
    };

    guild.members.get(&user_id).cloned()
}

#[tokio::main(flavor = "current_thread")]
async fn main() {
    dotenv().ok();
    let token = env::var("DISCORD_TOKEN").expect("DISCORD_TOKEN must be set");

    let intents = GatewayIntents::GUILD_MEMBERS
                                | GatewayIntents::GUILD_MESSAGES
                                | GatewayIntents::MESSAGE_CONTENT // メッセージの内容を取得するため。
                                | GatewayIntents::DIRECT_MESSAGES
                                | GatewayIntents::GUILD_VOICE_STATES
                                | GatewayIntents::GUILDS  // サーバーのリストを取得するため。
                                | GatewayIntents::GUILD_PRESENCES; // ボット起動後にボイスチャンネルに参加したユーザーを取得するため。
                                                                   // let intents = GatewayIntents::all();

    let mut serenity_client = Client::builder(&token, intents)
        .event_handler(Handler)
        .register_songbird()
        .await
        .expect("Error creating client");

    // SynthesisQueueとVoiceChannelTrackerのインスタンスを作成し、TypeMapに挿入
    let synthesis_queue = Arc::new(SynthesisQueue::new());
    let voice_channel_tracker = Arc::new(VoiceChannelTracker::new());
    {
        let mut data = serenity_client.data.write().await;
        data.insert::<SynthesisQueueKey>(synthesis_queue.clone());
        data.insert::<VoiceChannelTrackerKey>(voice_channel_tracker.clone());
    }
    if let Err(why) = serenity_client.start().await {
        println!("Client error: {:?}", why);
    }
}
