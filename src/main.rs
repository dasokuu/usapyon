// まずはボットに接続するところから。

// use reqwest;
// use serde_json::Value;
// use std::env;
// use std::error::Error;

// use serenity::async_trait;
// use serenity::framework::standard::macros::{command, group};
// use serenity::framework::standard::{CommandResult, Configuration, StandardFramework};
// use serenity::model::channel::Message;
// use serenity::prelude::*;

extern crate dotenv;
extern crate serenity;

use dotenv::dotenv;
use std::env;
use serenity::{
    async_trait,
    model::{ gateway::Ready, prelude::*, id::{GuildId, ChannelId}},
    prelude::*,
};
use songbird::SerenityInit;

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
    /// # Arguments
    /// * `ctx` - ボットの状態に関する様々なデータのコンテキスト。
    /// * `msg` - 受信したメッセージ。
    async fn message(&self, ctx: Context, msg: Message) {
        if let Some(guild_id) = msg.guild_id {
            // ギルドIDを表示
            println!("{} said in {}: {}", msg.author.name, guild_id, msg.content);

            if msg.content == "!join" {
                if let Some(guild_id) = msg.guild_id {
                    let channel_id_str = env::var("TEST_VOICE_CHANNEL_ID").expect("TEST_VOICE_CHANNEL_ID must be set");
                    let channel_id = ChannelId::new(channel_id_str.parse::<u64>().unwrap());

                    let manager = songbird::get(&ctx).await
                        .expect("Songbird Voice client placed in at initialization.").clone();

                    let join_result = manager.join(guild_id, channel_id).await;

                    match join_result {
                        Ok(_) => {
                            println!("Joined voice channel!");
                        },
                        Err(error) => {
                            println!("Error joining voice channel: {:?}", error);
                        }
                    }
                }
            }
        } else {
            println!("{} said in DMs: {}", msg.author.name, msg.content);
        }
    }
}

// #[group]
// #[commands(join)]
// struct General;

// struct Handler;

// #[async_trait]
// impl EventHandler for Handler {}

// // Asynchronous function `audio_query`
// async fn audio_query(text: &str, style_id: i32) -> Result<Value, Box<dyn Error>> {
//     // Define the URL and headers as per your application's needs
//     let url = format!(
//         "{}?text={}&speaker={}",
//         "http://127.0.0.1:50021/audio_query", text, style_id
//     );

//     // Create a client instance
//     let client = reqwest::Client::new();

//     // Construct the JSON body
//     let body = serde_json::json!({
//         "text": text,
//         "speaker": style_id
//     });

//     // Make the HTTP POST request
//     let response = client.post(&url).json(&body).send().await?;
//     // Check for errors
//     if response.status().is_success() {
//         // Parse the JSON response
//         let json_response = response.json::<Value>().await?;
//         Ok(json_response)
//     } else {
//         // Handle error scenarios
//         Err(Box::new(std::io::Error::new(
//             std::io::ErrorKind::Other,
//             "Failed to query audio",
//         )))
//     }
// }
#[tokio::main]
async fn main() {
    println!("Hello, world!");

    dotenv().ok();

    let token = env::var("DISCORD_TOKEN").expect("DISCORD_TOKEN must be set");
    println!("DISCORD_TOKEN: {}", token);

    // let test_guild_id_str = env::var("TEST_GUILD_ID").expect("TEST_GUILD_ID must be set");
    // let test_voice_channel_id_str = env::var("TEST_VOICE_CHANNEL_ID").expect("TEST_VOICE_CHANNEL_ID must be set");
    // println!("TEST_GUILD_ID: {}", test_guild_id_str);
    // println!("TEST_VOICE_CHANNEL_ID: {}", test_voice_channel_id_str);
    
    // let test_guild_id = GuildId::new(test_guild_id_str.parse::<u64>().unwrap());
    // let test_voice_channel_id = ChannelId::new(test_voice_channel_id_str.parse::<u64>().unwrap());

    // let manager = songbird::get(ctx).await
    //     .expect("Songbird Voice client placed in at initialization.").clone();

    // let (_, handler) = manager.join(test_guild_id, test_voice_channel_id).await;

    // match handler {
    //     Ok(connection_info) => {
    //         println!("Joined voice channel!");
    //     },
    //     Err(error) => {
    //         println!("Error joining voice channel: {:?}", error);
    //     }
    // }

    // 必要なインテントを有効にします。
    let intents = GatewayIntents::GUILD_MEMBERS
                                | GatewayIntents::GUILD_MESSAGES
                                | GatewayIntents::MESSAGE_CONTENT
                                | GatewayIntents::DIRECT_MESSAGES;
    let mut client = Client::builder(&token, intents)
        .event_handler(Handler)
        .register_songbird()
        .await
        .expect("Error creating client");

    if let Err(why) = client.start().await {
        println!("Client error: {:?}", why);
    }

    // let framework = StandardFramework::new().group(&GENERAL_GROUP);
    // framework.configure(Configuration::new().prefix("~")); // set the bot's prefix to "~"

    // // Login with a bot token from the environment
    // let token = env::var("DISCORD_TOKEN").expect("token");
    // let intents = GatewayIntents::non_privileged() | GatewayIntents::MESSAGE_CONTENT;
    // let mut client = Client::builder(token, intents)
    //     .event_handler(Handler)
    //     .framework(framework)
    //     .await
    //     .expect("Error creating client");

    // // start listening for events by starting a single shard
    // if let Err(why) = client.start().await {
    //     println!("An error occurred while running the client: {:?}", why);
    // }
    // let response = audio_query("こんにちは", 1).await;
    // match response {
    //     Ok(json) => println!("Response: {:?}", json),
    //     Err(e) => eprintln!("Error: {:?}", e),
    // }
}
// #[command]
// async fn join(ctx: &Context, msg: &Message) -> CommandResult {
//     let guild_id = match msg.guild_id {
//         Some(guild_id) => guild_id,
//         None => {
//             msg.reply(ctx, "This command can only be used in a server.").await?;
//             return Ok(());
//         }
//     };

//     // Clone the necessary data before the async block
//     let author_id = msg.author.id;
//     let cache = ctx.cache.clone();

//     // Move into async block
//     let channel_id = {
//         let guild = cache.guild(guild_id);
//         match guild {
//             Some(guild) => guild.voice_states.get(&author_id).and_then(|voice_state| voice_state.channel_id),
//             None => {
//                 msg.reply(ctx, "Error finding guild.").await?;
//                 return Ok(());
//             }
//         }
//     };

//     // Then use channel_id in the async block
//     let connect_to = match channel_id {
//         Some(channel) => channel,
//         None => {
//             msg.reply(ctx, "You are not connected to a voice channel.")
//                 .await?;
//             return Ok(());
//         }
//     };

//     // VCに接続
//     let manager = songbird::get(ctx)
//         .await
//         .expect("Songbird Voice client placed in at initialisation.")
//         .clone();
//     let _handler = manager.join(guild_id, connect_to).await;

//     msg.reply(ctx, "ボイスチャンネルに接続しました！").await?;

//     Ok(())
// }
