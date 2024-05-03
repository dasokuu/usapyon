use serenity::model::id::ChannelId;
use serenity::{model::prelude::*, prelude::*};
use std::collections::HashSet;
use std::{collections::HashMap, sync::Arc};

/// ギルドごとのアクティブなボイスチャンネルとテキストチャンネルのトラッキングを行う構造体。
pub struct VoiceChannelTracker {
    /// 各ギルドでアクティブなボイスチャンネルとテキストチャンネルのマップ。
    /// 
    /// キーはギルドID、値はボイスチャンネルIDとテキストチャンネルIDのタプルです。
    pub active_channels: Mutex<HashMap<GuildId, (ChannelId, ChannelId)>>, // (VoiceChannelId, TextChannelId)

    /// 各ギルドで使用されたスピーカーのセット。
    pub used_speakers: Mutex<HashMap<GuildId, HashSet<String>>>,
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

    /// 指定したスピーカーを、使用済みとして登録します。
    /// 
    /// ## Arguments
    /// * `guild_id` - ギルドID。
    /// * `speaker_name` - スピーカー名。
    /// 
    /// ## Returns
    /// * `bool` - スピーカーが既に使用されている場合は `true`、そうでない場合は `false`。
    pub async fn mark_speaker_as_used(&self, guild_id: GuildId, speaker_name: String) -> bool {
        let mut used = self.used_speakers.lock().await;
        let entry = used.entry(guild_id).or_default();
        entry.insert(speaker_name)
    }

    /// 指定したギルドに対して使用済みのスピーカーをクリアします。
    /// 
    /// ## Arguments
    /// * `guild_id` - ギルドID。
    pub async fn clear_used_speakers(&self, guild_id: GuildId) {
        let mut used = self.used_speakers.lock().await;
        used.remove(&guild_id);
    }
}

/// `VoiceChannelTracker` のインスタンスを格納するための `TypeMapKey`。
pub struct VoiceChannelTrackerKey;

impl TypeMapKey for VoiceChannelTrackerKey {
    type Value = Arc<VoiceChannelTracker>;
}
