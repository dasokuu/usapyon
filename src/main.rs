// 話者IDを選択できるようにしたい。

mod synthesis_queue;
mod usapyon_event_handler;

extern crate dotenv;
extern crate serenity;

use dotenv::dotenv;
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
    collections::HashMap,
    env,
    error::Error,
    sync::Arc,
};
use synthesis_queue::{SynthesisQueue, SynthesisQueueKey, SynthesisRequest};
use usapyon_event_handler::{UsapyonEventHandler, VoiceChannelTracker, VoiceChannelTrackerKey};

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

    {
        let mut data = serenity_client.data.write().await;
        data.insert::<SynthesisQueueKey>(synthesis_queue.clone());
        data.insert::<VoiceChannelTrackerKey>(voice_channel_tracker.clone());
    }

    if let Err(why) = serenity_client.start().await {
        println!("Client error: {:?}", why);
    }
}
