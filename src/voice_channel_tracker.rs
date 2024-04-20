
extern crate dotenv;
extern crate serenity;

use serenity::model::id::ChannelId;
use serenity::{
    model::prelude::*,
    prelude::*,
};
use std::{
    collections::HashMap,
    sync::Arc,
};

/// ギルドごとのアクティブなボイスチャンネルとテキストチャンネルのトラッキングを行う構造体。
pub struct VoiceChannelTracker {
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

pub struct VoiceChannelTrackerKey;
impl TypeMapKey for VoiceChannelTrackerKey {
    type Value = Arc<VoiceChannelTracker>;
}
