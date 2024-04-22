use crate::commands::{clear, join, leave, setstyle, skip};
use std::error::Error;
use std::sync::Arc;

use regex::Regex;
use serenity::model::channel::Channel;
use serenity::model::id::{ChannelId, RoleId, UserId};
use serenity::{
    async_trait,
    model::{gateway::Ready, prelude::*},
    prelude::*,
};

use crate::serenity_utils::get_songbird_from_ctx;
use crate::synthesis_queue_manager::SynthesisQueueManager;
use crate::usapyon_config::UsapyonConfigKey;
use crate::{SynthesisQueueManagerKey, SynthesisRequest, VoiceChannelTrackerKey};

pub struct UsapyonEventHandler;

/// `Handler`は`EventHandler`の実装です。
/// Discordからのイベントを処理するメソッドを提供します。
#[async_trait]
impl EventHandler for UsapyonEventHandler {
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
        if msg.author.bot || msg.is_private() {
            return;
        }

        let guild_id = msg.guild_id.expect("Guild ID not found");

        // joinコマンドは非アクティブな場合でも実行できる必要があるため、ここで処理。
        if msg.content == "!join" {
            if let Err(e) = join::join_voice_channel(&ctx, &msg).await {
                println!("Error processing !join command: {}", e);
            }
        }

        if !is_active_text_channel(&ctx, guild_id, msg.channel_id).await {
            return; // アクティブなチャンネルでなければ何もしません。
        }

        if msg.content.starts_with("!") {
            UsapyonEventHandler::process_command(&ctx, &msg, guild_id).await;
            return;
        } else {
            if let Err(e) = UsapyonEventHandler::process_speech_request(&ctx, &msg, guild_id).await
            {
                println!("Error processing speech request: {}", e);
            }
        }
    }

    /// ボイスチャットの状態が変更されたときに呼び出されます。
    ///
    /// ## Arguments
    /// * `ctx` - ボットの状態に関する様々なデータのコンテキスト。
    /// * `_old_state` - 変更前のボイスチャットの状態。
    /// * `new_state` - 変更後のボイスチャットの状態。
    async fn voice_state_update(
        &self,
        ctx: Context,
        _old_state: Option<VoiceState>,
        new_state: VoiceState,
    ) {
        let guild_id = match new_state.guild_id {
            Some(guild_id) => guild_id,
            None => {
                eprintln!("Voice state update without guild ID.");
                return;
            }
        };

        match count_non_bot_users_in_bot_voice_channel(&ctx, guild_id) {
            Some(non_bot_users_count) => {
                println!("non_bot_users_count: {:?}", non_bot_users_count);

                // ボット以外のユーザーがボイスチャンネルに存在しなくなった場合、ボットを退出させます。
                if non_bot_users_count == 0 {
                    match get_songbird_from_ctx(&ctx).await {
                        Ok(songbird) => {
                            if let Err(why) = songbird.leave(guild_id).await {
                                println!("Error leaving voice channel: {:?}", why);
                            }

                            ctx.data
                                .read()
                                .await
                                .get::<VoiceChannelTrackerKey>()
                                .expect("VoiceChannelTracker not found")
                                .remove_active_channel(guild_id)
                                .await;
                        }
                        Err(e) => {
                            println!("Failed to get Songbird client: {}", e);
                        }
                    }
                }
            }
            None => {
                println!("Failed to determine the count of non-bot users in the voice channel.");
            }
        }
        match count_non_bot_users_in_bot_voice_channel(&ctx, guild_id) {
            Some(non_bot_users_count) => {
                println!("non_bot_users_count: {:?}", non_bot_users_count);

                // ボット以外のユーザーがボイスチャンネルに存在しなくなった場合、ボットを退出させます。
                if non_bot_users_count == 0 {
                    match get_songbird_from_ctx(&ctx).await {
                        Ok(songbird) => {
                            if let Err(why) = songbird.leave(guild_id).await {
                                println!("Error leaving voice channel: {:?}", why);
                            }

                            ctx.data
                                .read()
                                .await
                                .get::<VoiceChannelTrackerKey>()
                                .expect("VoiceChannelTracker not found")
                                .remove_active_channel(guild_id)
                                .await;
                        }
                        Err(e) => {
                            println!("Failed to get Songbird client: {}", e);
                        }
                    }
                }
            }
            None => {
                println!("Failed to determine the count of non-bot users in the voice channel.");
            }
        }
    }
}

// UsapyonEventHandler独自のメソッドを実装。
impl UsapyonEventHandler {
    /// "!"から始まるコマンドを処理します。
    ///
    /// ## Arguments
    /// * `ctx` - ボットの状態に関する様々なデータのコンテキスト。
    /// * `msg` - メッセージ。
    /// * `guild_id` - ギルドID。
    async fn process_command(ctx: &Context, msg: &Message, guild_id: GuildId) {
        let content = msg.content.trim();
        if content.starts_with("!setstyle") {
            let args: Vec<&str> = content.split_whitespace().collect();
            setstyle::set_style_command(ctx, msg, args, guild_id).await; // Assume this handles its errors internally
        } else {
            match msg.content.as_str() {
                "!leave" => {
                    if let Err(e) = leave::leave_voice_channel(ctx, msg).await {
                        println!("Error when trying to leave voice channel: {}", e);
                    }
                }
                "!skip" => {
                    skip::skip_queue(ctx, guild_id).await; // Assume this handles its errors internally
                }
                "!clear" => {
                    clear::stop_and_clear_queues(ctx, guild_id).await; // Assume this handles its errors internally
                }
                _ => {}
            }
        }
    }

    /// メッセージを読み上げるリクエストを処理します。
    ///
    /// ## Arguments
    /// * `ctx` - ボットの状態に関する様々なデータのコンテキスト。
    /// * `msg` - メッセージ。
    /// * `guild_id` - ギルドID。
    async fn process_speech_request(
        ctx: &Context,
        msg: &Message,
        guild_id: GuildId,
    ) -> Result<(), Box<dyn Error + Send + Sync>> {
        // ユーザーの style_id を取得
        let user_id = msg.author.id;
        let data = ctx.data.read().await;
        let config = data
            .get::<UsapyonConfigKey>()
            .expect("Config should be available");
        let config = config.lock().await;
        let style_id = config.get_user_style(&user_id).unwrap_or(1); // デフォルトのスタイルIDを 1 とする

        println!("msg.content: {}", msg.content);

        let sanitized_content: String = sanitize_message(&ctx, &msg.content, guild_id).await;
        println!("Sanitized message: {}", sanitized_content);

        // メッセージを読み上げる処理
        // Context から SynthesisQueue を取得
        let speech_text = if sanitized_content.chars().count() > 200 {
            sanitized_content.chars().take(200).collect::<String>() + "...以下略"
        } else {
            sanitized_content.clone()
        };

        let request = SynthesisRequest::new(speech_text.to_string(), style_id.to_string());

        // 音声合成キューマネージャーを取得し、リクエストを追加して処理を開始します。
        let synthesis_queue_manager = get_synthesis_queue_manager(&ctx).await;
        synthesis_queue_manager
            .add_request_to_synthesis_queue(guild_id, request)
            .await;
        synthesis_queue_manager
            .start_processing(&ctx, guild_id)
            .await?;

        Ok(())
    }
}

async fn sanitize_message(ctx: &Context, msg: &str, guild_id: GuildId) -> String {
    let re_user = Regex::new(r"<@!?(\d+)>").unwrap();
    let re_channel = Regex::new(r"<#(\d+)>").unwrap();
    let re_role = Regex::new(r"<@&(\d+)>").unwrap();
    let re_emoji = Regex::new(r"<:([^:]+):\d+>").unwrap();

    let mut sanitized = msg.to_string();

    // 「<@ユーザーID>」をニックネームに置き換えます。
    // 優先順位はサーバー内ニックネーム、ユーザーのニックネーム、ユーザー名です。
    for cap in re_user.captures_iter(msg) {
        if let Ok(id) = cap[1].parse::<u64>() {
            if let Some(member) = get_member_from_ctx(&ctx, guild_id, UserId::new(id)) {
                let display_name = member.display_name();
                sanitized = sanitized.replace(&cap[0], display_name);
            }
        }
    }

    // Replace channel mentions
    for cap in re_channel.captures_iter(msg) {
        if let Ok(id) = cap[1].parse::<u64>() {
            if let Ok(channel) = ChannelId::new(id).to_channel(&ctx.http).await {
                if let Channel::Guild(channel) = channel {
                    sanitized = sanitized.replace(&cap[0], &channel.name);
                }
            }
        }
    }

    // Replace role mentions
    for cap in re_role.captures_iter(msg) {
        if let Ok(id) = cap[1].parse::<u64>() {
            if let Some(guild) = ctx.cache.guild(guild_id) {
                if let Some(role) = guild.roles.get(&RoleId::new(id)) {
                    sanitized = sanitized.replace(&cap[0], &role.name);
                }
            }
        }
    }

    // Replace custom emojis
    sanitized = re_emoji
        .replace_all(&sanitized, |caps: &regex::Captures| format!("{}", &caps[1]))
        .to_string();

    sanitized
}

fn get_member_from_ctx(ctx: &Context, guild_id: GuildId, user_id: UserId) -> Option<Member> {
    let guild = match ctx.cache.guild(guild_id) {
        Some(guild) => guild,
        None => return None,
    };

    guild.members.get(&user_id).cloned()
}

/// ボットが参加しているボイスチャンネルにいるボット以外のユーザーの数を取得します。
/// エラーが発生した場合はNoneを返します。
///
/// ## Arguments
/// * `ctx` - ボットの状態に関する様々なデータのコンテキスト。
/// * `guild_id` - ギルドID。
///
/// ## Returns
/// `Option<usize>` - ボット以外のユーザーの数、またはNone。
fn count_non_bot_users_in_bot_voice_channel(ctx: &Context, guild_id: GuildId) -> Option<usize> {
    let guild = ctx.cache.guild(guild_id)?;

    let bot_voice_channel_id = guild
        .voice_states
        .get(&ctx.cache.current_user().id)?
        .channel_id?;

    // ボットが参加しているボイスチャンネルにいるユーザーIDを取得。
    let users_in_bot_voice_channel = guild
        .voice_states
        .iter()
        .filter_map(|(user_id, voice_state)| {
            if voice_state.channel_id == Some(bot_voice_channel_id) {
                Some(user_id)
            } else {
                None
            }
        })
        .collect::<Vec<_>>();

    // ボットを除くユーザーの数を計算。
    let non_bot_users_count = users_in_bot_voice_channel
        .iter()
        .filter(|user_id| !ctx.cache.user(**user_id).map_or(false, |user| user.bot))
        .count();

    Some(non_bot_users_count)
}

/// データコンテキストから音声合成キューのマネージャーを取得します。
///
/// ## Arguments
/// * `ctx` - ボットの状態に関する様々なデータのコンテキスト。
///
/// ## Returns
/// `Arc<SynthesisQueueManager>` - 音声合成キューのマネージャー。
pub async fn get_synthesis_queue_manager(ctx: &Context) -> Arc<SynthesisQueueManager> {
    let data_read = ctx.data.read().await;
    data_read
        .get::<SynthesisQueueManagerKey>()
        .expect("SynthesisQueueManager not found")
        .clone()
}

/// 指定したテキストチャンネルがアクティブなチャンネルであるかどうかを返します。
/// アクティブなチャンネルとは、最後にjoinコマンドが実行されたテキストチャンネルです。
///
/// ## Arguments
/// * `ctx` - ボットの状態に関する様々なデータのコンテキスト。
/// * `guild_id` - ギルドID。
/// * `text_channel_id` - テキストチャンネルID。
///
/// ## Returns
/// `bool` - 指定したテキストチャンネルがアクティブなチャンネルであるかどうか。
async fn is_active_text_channel(
    ctx: &Context,
    guild_id: GuildId,
    text_channel_id: ChannelId,
) -> bool {
    let data_read = ctx.data.read().await;
    data_read
        .get::<VoiceChannelTrackerKey>()
        .expect("VoiceChannelTracker not found")
        .is_active_text_channel(guild_id, text_channel_id)
        .await
}
