use std::sync::Arc;

use regex::Regex;
use serenity::model::channel::Channel;
use serenity::model::id::{ChannelId, RoleId, UserId};
use serenity::{
    async_trait,
    model::{gateway::Ready, prelude::*},
    prelude::*,
};

use crate::serenity_utils::{get_songbird_from_ctx, with_songbird_handler};
use crate::synthesis_queue_manager::SynthesisQueueManager;
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
            if let Err(e) = join_voice_channel(&ctx, &msg).await {
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
            UsapyonEventHandler::process_speech_request(&ctx, &msg, guild_id).await;
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
        match msg.content.as_str() {
            "!leave" => {
                if let Err(e) = leave_voice_channel(&ctx, &msg).await {
                    println!("Error processing !leave command: {}", e);
                }
            }
            "!skip" => {
                // songbird の音声ハンドラでスキップを試みます。
                let result = with_songbird_handler(&ctx, guild_id, |handler| {
                    handler
                        .queue()
                        .current()
                        .map(|_| handler.queue().skip().is_ok())
                })
                .await;

                match result {
                    Ok(Some(true)) => {
                        println!("Track skipped successfully for guild {}", guild_id);
                    }
                    // トラックが存在しない、またはスキップに失敗した場合、音声合成リクエストをキャンセル。
                    Ok(Some(false)) | Ok(None) => {
                        let synthesis_queue_manager = get_synthesis_queue_manager(&ctx).await;
                        synthesis_queue_manager
                            .cancel_current_request(guild_id)
                            .await;
                        println!("No track was playing, or skip failed. Synthesis request cancelled for guild {}", guild_id);
                    }
                    Err(e) => {
                        println!("Failed to handle track for guild {}: {:?}", guild_id, e);
                    }
                }
            }
            "!clear" => {
                let result = with_songbird_handler(&ctx, guild_id, |handler| {
                    // 再生を停止してキューをクリア。
                    handler.queue().stop();
                    format!("Queue cleared successfully for guild {}", guild_id)
                })
                .await;

                match result {
                    Ok(msg) => println!("{}", msg),
                    Err(e) => println!("Failed to clear queue for guild {}: {:?}", guild_id, e),
                }

                // 音声合成キューをクリア。
                let synthesis_queue_manager = get_synthesis_queue_manager(&ctx).await;
                synthesis_queue_manager
                    .cancel_current_request_and_clear_queue(guild_id)
                    .await;
                println!(
                    "Synthesis queue cleared successfully for guild {}",
                    guild_id
                );
            }
            _ => {}
        }
    }

    async fn process_speech_request(ctx: &Context, msg: &Message, guild_id: GuildId) {
        println!("msg.content: {}", msg.content);

        let sanitized_content: String = sanitize_message(&ctx, &msg.content, guild_id).await;
        println!("Sanitized message: {}", sanitized_content);

        // メッセージを読み上げる処理
        // Context から SynthesisQueue を取得
        let text_to_read = if sanitized_content.chars().count() > 200 {
            sanitized_content.chars().take(200).collect::<String>() + "...以下略"
        } else {
            sanitized_content.clone()
        };

        let request = SynthesisRequest::new(text_to_read.to_string(), "1".to_string());

        // 音声合成キューマネージャーを取得し、リクエストを追加して処理を開始します。
        let synthesis_queue_manager = get_synthesis_queue_manager(&ctx).await;
        synthesis_queue_manager
            .add_request_to_synthesis_queue(guild_id, request)
            .await;
        synthesis_queue_manager
            .start_processing(&ctx, guild_id)
            .await;
    }
}

/// ボイスチャンネルからの退出処理を行います。
///
/// ## Arguments
/// * `ctx` - ボットの状態に関する様々なデータのコンテキスト。
/// * `msg` - メッセージ。
///
/// ## Returns
/// 成功した場合は`Ok(())`、エラーが発生した場合は`Err(Box<dyn Error + Send + Sync>)`を返します。
async fn leave_voice_channel(ctx: &Context, msg: &Message) -> Result<(), String> {
    let songbird = get_songbird_from_ctx(&ctx).await?;
    let guild_id = msg.guild_id.ok_or("Message must be sent in a server")?;

    if let Err(why) = songbird.leave(guild_id).await {
        println!("Error leaving voice channel: {:?}", why);
        return Err("Failed to leave voice channel.".into());
    }

    ctx.data
        .read()
        .await
        .get::<VoiceChannelTrackerKey>()
        .ok_or("VoiceChannelTracker not found")?
        .remove_active_channel(guild_id)
        .await;

    Ok(())
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

/// ボイスチャンネルへの参加と同時にアクティブなチャンネルの設定を行います。
/// ## Arguments
/// * `ctx` - コンテキスト、ボットの状態や設定情報へのアクセスを提供します。
/// * `msg` - 参加コマンドを送信したメッセージ情報。
///
/// ## Returns
/// * `Result<(), String>` - ボイスチャンネルへの参加操作が成功した場合は Ok(()) を、失敗した場合は Err を返します。
async fn join_voice_channel(ctx: &Context, msg: &Message) -> Result<(), String> {
    let guild_id = msg.guild_id.ok_or("Message must be sent in a server")?;
    let text_channel_id = msg.channel_id;

    let voice_channel_id = ctx
        .cache
        .guild(guild_id)
        .and_then(|guild| guild.voice_states.get(&msg.author.id).cloned())
        .and_then(|voice_state| voice_state.channel_id)
        .ok_or("User is not in a voice channel.")?;

    let songbird_result = get_songbird_from_ctx(&ctx).await;
    match songbird_result {
        Ok(songbird) => {
            match songbird.join(guild_id, voice_channel_id).await {
                Ok(call) => {
                    // ここでエラーを String に変換
                    call.lock()
                        .await
                        .deafen(true)
                        .await
                        .map_err(|e| format!("Failed to deafen: {:?}", e))?;
                    ctx.data
                        .read()
                        .await
                        .get::<VoiceChannelTrackerKey>()
                        .ok_or("VoiceChannelTracker not found")?
                        .set_active_channel(guild_id, voice_channel_id, text_channel_id)
                        .await;
                    Ok(())
                }
                Err(why) => {
                    println!("Failed to join voice channel: {:?}", why);
                    Err("Failed to join voice channel.".into())
                }
            }
        }
        Err(e) => {
            println!("Error retrieving Songbird client: {}", e);
            Err("Failed to retrieve Songbird client.".into())
        }
    }
}

/// データコンテキストから音声合成キューのマネージャーを取得します。
///
/// ## Arguments
/// * `ctx` - ボットの状態に関する様々なデータのコンテキスト。
///
/// ## Returns
/// `Arc<SynthesisQueueManager>` - 音声合成キューのマネージャー。
async fn get_synthesis_queue_manager(ctx: &Context) -> Arc<SynthesisQueueManager> {
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
