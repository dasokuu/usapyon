use serenity::model::id::ChannelId;
use serenity::{model::prelude::*, prelude::*};
use std::collections::HashSet;
use std::{collections::HashMap, sync::Arc};

/// ギルドごとのアクティブなボイスチャンネルとテキストチャンネルのトラッキングを行う構造体。
pub struct VoiceChannelTracker {
    pub active_channels: Mutex<HashMap<GuildId, (ChannelId, ChannelId)>>, // (VoiceChannelId, TextChannelId)
    pub used_speakers: Mutex<HashMap<GuildId, HashSet<String>>>, // 追加: 各ギルドで使用されたスピーカーの記録
}

impl VoiceChannelTracker {
    pub fn new() -> Self {
        VoiceChannelTracker {
            active_channels: Mutex::new(HashMap::new()),
            used_speakers: Mutex::new(HashMap::new()),
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

    pub async fn get_active_voice_channel(&self, guild_id: GuildId) -> Option<ChannelId> {
        let channels = self.active_channels.lock().await;
        channels
            .get(&guild_id)
            .map(|(voice_channel_id, _)| *voice_channel_id)
    }

    pub async fn get_active_text_channel(&self, guild_id: GuildId) -> Option<ChannelId> {
        let channels = self.active_channels.lock().await;
        channels
            .get(&guild_id)
            .map(|(_, text_channel_id)| *text_channel_id)
    }

    // スピーカーが使用されたかをチェックし、必要に応じて記録
    pub async fn mark_speaker_as_used(&self, guild_id: GuildId, speaker_name: String) -> bool {
        let mut used = self.used_speakers.lock().await;
        let entry = used.entry(guild_id).or_default();
        entry.insert(speaker_name)
    }
}

pub struct VoiceChannelTrackerKey;
impl TypeMapKey for VoiceChannelTrackerKey {
    type Value = Arc<VoiceChannelTracker>;
}
