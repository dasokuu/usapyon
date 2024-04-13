// まずはボットに接続するところから。
// joinを実行したチャンネルのテキストだけをボットが読み上げるようにしたい。

extern crate dotenv;
extern crate serenity;

use dotenv::dotenv;
use std::{env, sync::Arc, error::Error, collections::HashMap};
use serenity::{
    async_trait,
    model::{ gateway::Ready, prelude::*},
    prelude::*,
};
use songbird::{
    Songbird,
    SerenityInit,
    SongbirdKey
};
use reqwest::Url;

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
        if let Some(guild_id) = msg.guild_id {
            // ギルドの数を表示
            println!("guilds: {:?}", ctx.cache.guild_count());
            // ギルドIDを表示
            println!("{} said in {}: {}", msg.author.name, guild_id, msg.content);

            // "!"から始まるメッセージとそうでないメッセージで処理を分けます。
            if msg.content.starts_with("!") {
                // !joinと!leaveコマンドを処理。
                match msg.content.as_str() {
                    // ボットをユーザーがいるボイスチャンネルに参加させます。
                    "!join" => {
                        join_user_voice_channel(&ctx, &msg).await.unwrap();
                    },
                    // ボットをボイスチャンネルから退出させます。
                    "!leave" => {
                        leave_voice_channel(&ctx, &msg).await.unwrap();
                    },
                    _ => {},
                }
            } else {
                // ボットがユーザーがいるボイスチャンネルに参加している場合、
                // ボットが読み上げるようにします。
                // voicevox_engineに投げるリクエストを生成します。
                let client = reqwest::Client::new();
                
                let mut headers = reqwest::header::HeaderMap::new();
                headers.insert("Accept", "application/json".parse().unwrap());

                let base = "http://localhost:50021/audio_query";
                
                let params: HashMap<&str, &str> = [
                    ("text", msg.content.as_str()),
                    ("speaker", "1")
                ].iter().cloned().collect();

                let url = Url::parse_with_params(base, &params).unwrap();

                // ポストする内容を確認。
                // println!("{:?}", params);

                let res = client.post(url)
                    .headers(headers)
                    .send()
                    .await
                    .unwrap();

                println!("{}", res.status());
            }

        } else {
            println!("{} said in DMs: {}", msg.author.name, msg.content);
        }
    }

    /// ボイスチャットの状態が変更されたときに呼び出されます。
    /// 
    /// ## Arguments
    /// * `ctx` - ボットの状態に関する様々なデータのコンテキスト。
    /// * `_old_state` - 変更前のボイスチャットの状態。
    /// * `new_state` - 変更後のボイスチャットの状態。
    async fn voice_state_update(&self, ctx: Context, _old_state: Option<VoiceState>, new_state: VoiceState) {
        // println!("voice_state_update: {:?}", new_state);

        // ボット以外のユーザーがボイスチャンネルに存在しなくなった場合、ボットを退出させます。
        if new_state.user_id != ctx.cache.current_user().id {
            if new_state.channel_id.is_none() {
                let guild_id = new_state.guild_id.expect("Guild ID not found");

                let songbird = get_songbird_from_ctx(&ctx).await;

                if let Err(why) = songbird.remove(guild_id).await {
                    println!("Error removing handler: {:?}", why);
                }
            }
        }
    }
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
    data.get::<SongbirdKey>().cloned().expect("Failed to retrieve Songbird client")
}

/// ユーザーがいるボイスチャンネルにボットを非同期に参加させます。
/// 
/// ## Arguments
/// * `ctx` - ボットの状態に関する様々なデータのコンテキスト。
/// * `msg` - メッセージ。
/// 
/// ## Returns
/// 成功した場合は`Ok(())`、エラーが発生した場合は`Err(Box<dyn Error + Send + Sync>)`を返します。
async fn join_user_voice_channel(ctx: &Context, msg: &Message) -> Result<(), Box<dyn Error + Send + Sync>> {
    // コンテキストデータからSongbirdクライアントを取得。
    let songbird = get_songbird_from_ctx(&ctx).await;

    let guild_id = match msg.guild_id {
        Some(guild_id) => guild_id,
        None => return Err("Message must be sent in a server".into()),
    };

    println!("guild_id: {:?}", guild_id);

    let channel_id = match ctx.cache.guild(guild_id)
        .and_then(|guild| guild.voice_states.get(&msg.author.id).cloned())
        .and_then(|voice_state| voice_state.channel_id) {
            Some(channel_id) => channel_id,
            None => return Err("User is not in a voice channel".into()),
    };
    println!("Channel ID: {:?}", channel_id);

    // ユーザーがいるチャンネルにボットを参加させます。
    let result = songbird.join(guild_id, channel_id).await;

    if let Err(why) = result {
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
async fn leave_voice_channel(ctx: &Context, msg: &Message) -> Result<(), Box<dyn Error + Send + Sync>> {
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
                                | GatewayIntents::GUILDS;
    // すべてのインテントを有効にします。
    // let intents = GatewayIntents::all();

    let mut serenity_client = Client::builder(&token, intents)
        .event_handler(Handler)
        .register_songbird()
        .await
        .expect("Error creating client");

    if let Err(why) = serenity_client.start().await {
        println!("Client error: {:?}", why);
    }
}
