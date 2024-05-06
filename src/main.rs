// 話者IDを選択できるようにしたい。

mod commands;
mod retry_handler;
mod serenity_utils;
mod synthesis_queue;
mod synthesis_queue_manager;
mod usapyon_config;
mod usapyon_event_handler;
mod voice_channel_tracker;
mod credit_display_handler;

extern crate dotenv;
extern crate serenity;

use dotenv::dotenv;
use serenity::{model::prelude::*, prelude::*};
use songbird::SerenityInit;
use std::{env, sync::Arc};
use synthesis_queue::SynthesisContext;
use synthesis_queue_manager::{SynthesisQueueManager, SynthesisQueueManagerKey};
use usapyon_config::{UsapyonConfig, UsapyonConfigKey};
use usapyon_event_handler::{load_emoji_data, EmojiData, UsapyonEventHandler};
use voice_channel_tracker::{VoiceChannelTracker, VoiceChannelTrackerKey};

#[tokio::main(flavor = "current_thread")]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // 環境変数のロード
    dotenv().ok();

    let token = env::var("DISCORD_TOKEN").expect("Expected DISCORD_TOKEN in the environment");

    let intents = GatewayIntents::GUILD_MEMBERS
        | GatewayIntents::GUILD_MESSAGES
        | GatewayIntents::MESSAGE_CONTENT  // メッセージの内容を取得するため。
        | GatewayIntents::DIRECT_MESSAGES
        | GatewayIntents::GUILD_VOICE_STATES
        | GatewayIntents::GUILDS  // サーバーのリストを取得するため。
        | GatewayIntents::GUILD_PRESENCES; // ボット起動後にボイスチャンネルに参加したユーザーを取得するため。

    // すべてのインテントを有効にする（開発中のみ）
    // let intents = GatewayIntents::all();

    let mut client = Client::builder(&token, intents)
        .event_handler(UsapyonEventHandler)
        .register_songbird()
        .await?;

    let config = UsapyonConfig::new("http://localhost:50021/speakers").await?;
    let config = Arc::new(Mutex::new(config));
    let voice_tracker = Arc::new(VoiceChannelTracker::new());
    let queue_manager = Arc::new(SynthesisQueueManager::new());

    {
        // クライアントデータへの登録
        let mut data = client.data.write().await;
        data.insert::<VoiceChannelTrackerKey>(voice_tracker);
        data.insert::<SynthesisQueueManagerKey>(queue_manager);
        data.insert::<UsapyonConfigKey>(config);
        let emoji_data = load_emoji_data();
        data.insert::<EmojiData>(emoji_data);
    }

    client.start().await.map_err(Into::into)
}
