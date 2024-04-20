// 話者IDを選択できるようにしたい。

mod synthesis_queue;
mod usapyon_event_handler;
mod voice_channel_tracker;
mod synthesis_queue_manager;
mod serenity_utils;

extern crate dotenv;
extern crate serenity;

use dotenv::dotenv;
use serenity::{
    model::prelude::*,
    prelude::*,
};
use songbird::SerenityInit;
use std::{
    env,
    sync::Arc,
};
use synthesis_queue::{SynthesisQueue, SynthesisQueueKey, SynthesisRequest};
use usapyon_event_handler::UsapyonEventHandler;
use voice_channel_tracker::{VoiceChannelTracker, VoiceChannelTrackerKey};
use synthesis_queue_manager::SynthesisQueueManagerKey;

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

    // すべてのインテントを有効にする（開発中のみ）
    // let intents = GatewayIntents::all();

    let mut serenity_client = Client::builder(&token, intents)
        .event_handler(UsapyonEventHandler)
        .register_songbird()
        .await
        .expect("Error creating client");

    // SynthesisQueueとVoiceChannelTrackerのインスタンスを作成し、TypeMapに挿入
    let synthesis_queue = Arc::new(SynthesisQueue::new());
    let voice_channel_tracker = Arc::new(VoiceChannelTracker::new());
    let synthesis_queue_manager = Arc::new(synthesis_queue_manager::SynthesisQueueManager::new());

    {
        let mut data = serenity_client.data.write().await;
        data.insert::<SynthesisQueueKey>(synthesis_queue.clone());
        data.insert::<VoiceChannelTrackerKey>(voice_channel_tracker.clone());
        data.insert::<SynthesisQueueManagerKey>(synthesis_queue_manager.clone());
    }

    if let Err(why) = serenity_client.start().await {
        println!("Client error: {:?}", why);
    }
}
