// まずはボットに接続するところから。

extern crate dotenv;
extern crate serenity;

use dotenv::dotenv;
use std::env;
use serenity::{
    async_trait,
    model::{ gateway::Ready, prelude::*},
    prelude::*,
};
use songbird::{
    SerenityInit,
    SongbirdKey
};
use std::error::Error;

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
            println!("{} said in DMs: {}", msg.author.name, msg.content);
        }
    }
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
    let data = ctx.data.read().await;
    let songbird = data.get::<SongbirdKey>().cloned().expect("Failed to retrieve Songbird client");

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
    let data = ctx.data.read().await;
    let songbird = data.get::<SongbirdKey>().cloned().expect(
        "Failed to retrieve Songbird client");

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
    println!("Hello, world!");

    dotenv().ok();

    let token = env::var("DISCORD_TOKEN").expect("DISCORD_TOKEN must be set");
    println!("DISCORD_TOKEN: {}", token);

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
    let mut client = Client::builder(&token, intents)
        .event_handler(Handler)
        .register_songbird()
        .await
        .expect("Error creating client");

    if let Err(why) = client.start().await {
        println!("Client error: {:?}", why);
    }
}
