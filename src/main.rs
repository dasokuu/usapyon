// 話者IDを選択できるようにしたい。

mod serenity_utils;
mod synthesis_queue;
mod synthesis_queue_manager;
mod usapyon_event_handler;
mod voice_channel_tracker;

extern crate dotenv;
extern crate serenity;

use dotenv::dotenv;
use serenity::{model::prelude::*, prelude::*};
use songbird::SerenityInit;
use std::{env, sync::Arc};
use synthesis_queue::SynthesisRequest;
use synthesis_queue_manager::{SynthesisQueueManager, SynthesisQueueManagerKey};
use usapyon_event_handler::UsapyonEventHandler;
use voice_channel_tracker::{VoiceChannelTracker, VoiceChannelTrackerKey};

#[tokio::main(flavor = "current_thread")]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    dotenv().ok();
    let token = env::var("DISCORD_TOKEN")?;

    let intents = GatewayIntents::GUILD_MEMBERS
        | GatewayIntents::GUILD_MESSAGES
        | GatewayIntents::MESSAGE_CONTENT
        | GatewayIntents::DIRECT_MESSAGES
        | GatewayIntents::GUILD_VOICE_STATES
        | GatewayIntents::GUILDS
        | GatewayIntents::GUILD_PRESENCES;

    let mut client = Client::builder(&token, intents)
        .event_handler(UsapyonEventHandler)
        .register_songbird()
        .await?;

    let voice_tracker = Arc::new(VoiceChannelTracker::new());
    let queue_manager = Arc::new(SynthesisQueueManager::new());

    {
        let mut data = client.data.write().await;
        data.insert::<VoiceChannelTrackerKey>(voice_tracker.clone());
        data.insert::<SynthesisQueueManagerKey>(queue_manager.clone());
    }

    client.start().await.map_err(|e| e.into())
}
