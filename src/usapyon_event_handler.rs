use crate::{
    commands::{clear, help, join, leave, liststyles, setstyle, skip},
    env,
};
use std::{error::Error, fs::File, path::PathBuf};

use regex::Regex;
use serde_json::{from_reader, Value};
use serenity::model::channel::Channel;
use serenity::model::id::{ChannelId, RoleId, UserId};
use serenity::{
    async_trait,
    model::{gateway::Ready, prelude::*},
    prelude::*,
};
use std::collections::HashMap;

use crate::{
    serenity_utils::{get_data_from_ctx, get_songbird_from_ctx},
    usapyon_config::UsapyonConfigKey,
    SynthesisContext, SynthesisQueueManagerKey, VoiceChannelTrackerKey,
};

pub struct UsapyonEventHandler;

/// Discordからのイベントを処理するメソッドを提供します。
#[async_trait]
impl EventHandler for UsapyonEventHandler {
    /// ボットがDiscordの接続に成功したときに実行されます。
    ///
    /// ## Arguments
    /// * `_` - ボットの状態に関する様々なデータのコンテキスト。
    /// * `ready` - readyイベントのコンテキスト。
    async fn ready(&self, _: Context, ready: Ready) {
        println!("{} is connected!", ready.user.name);
    }

    /// ボットがメッセージを受信したときに実行されます。
    ///
    /// ## Arguments
    /// * `ctx` - ボットの状態に関する様々なデータのコンテキスト。
    /// * `msg` - 受信したメッセージ。
    async fn message(&self, ctx: Context, msg: Message) {
        // メッセージがボットから送られたもの、またはプライベートメッセージであれば処理を中断します。
        if msg.author.bot || msg.is_private() {
            return;
        }

        // メッセージが送信されたギルドのIDを取得します。
        let guild_id = msg.guild_id.expect("Guild ID not found");

        // メッセージが送信されたテキストチャンネルがアクティブな状態か確認します。
        if is_active_text_channel(&ctx, guild_id, msg.channel_id).await {
            // コマンドプレフィックス"!"で始まるメッセージの場合、アクティブコマンドを処理します。
            if msg.content.starts_with("u!") {
                Self::process_active_command(&ctx, &msg, guild_id).await;
            } else {
                // コマンドでないメッセージの場合、読み上げリクエストとして処理します。
                if let Err(e) = Self::process_user_speech_request(&ctx, &msg, guild_id).await {
                    println!("Error processing speech request: {}", e);
                }
                if !msg.attachments.is_empty() {
                    if let Err(e) = Self::process_attachments(&ctx, &msg, guild_id).await {
                        println!("Error processing attachments: {}", e);
                    }
                }
            }
        } else {
            Self::process_inactive_command(&ctx, &msg).await;
        }
    }

    /// ボイスチャットの状態が変更されたときに呼び出されます。
    ///
    /// ## Arguments
    /// * `ctx` - ボットの状態に関する様々なデータのコンテキスト。
    /// * `old_state` - 変更前のボイスチャットの状態。
    /// * `new_state` - 変更後のボイスチャットの状態。
    async fn voice_state_update(
        &self,
        ctx: Context,
        old_state: Option<VoiceState>,
        new_state: VoiceState,
    ) {
        let guild_id = match new_state.guild_id {
            Some(guild_id) => guild_id,
            None => {
                eprintln!("Voice state update without guild ID.");
                return;
            }
        };

        // ボットが参加しているボイスチャンネルIDを取得
        let tracker = get_data_from_ctx::<VoiceChannelTrackerKey>(&ctx).await;
        let bot_voice_channel_id = tracker.get_active_voice_channel(guild_id).await;

        // ユーザーがボットかどうかを確認
        let user_id = new_state.user_id;
        if ctx.cache.user(user_id).map(|u| u.bot).unwrap_or(false) {
            return; // ユーザーがボットの場合は何もしない
        }

        // ボット以外のユーザーがボイスチャンネルに存在しなくなった場合、ボットを退出させます。
        if let Some(non_bot_users_count) = count_non_bot_users_in_bot_voice_channel(&ctx, guild_id)
        {
            if non_bot_users_count == 0 {
                if let Ok(songbird) = get_songbird_from_ctx(&ctx).await {
                    if let Err(why) = songbird.leave(guild_id).await {
                        println!("Error leaving voice channel: {:?}", why);
                    }

                    let tracker = get_data_from_ctx::<VoiceChannelTrackerKey>(&ctx).await;

                    // ボイスチャンネルのアクティブ情報を削除
                    tracker.remove_active_channel(guild_id).await;

                    // 使用済みスピーカーの情報をクリア
                    tracker.clear_used_speakers(guild_id).await;

                    return; // ボットが退出するときは他の退出メッセージを送信しない
                }
            }
        }

        if let Some(bot_channel_id) = bot_voice_channel_id {
            if new_state.channel_id == Some(bot_channel_id)
                && old_state.as_ref().map(|s| s.channel_id) != Some(Some(bot_channel_id))
            {
                // ユーザーがボットのいるボイスチャンネルに参加
                if let Some(member) = get_member_from_ctx(&ctx, guild_id, user_id) {
                    let display_name = member.display_name();
                    let message = format!("{}さんが参加しました。", display_name);
                    if let Err(e) =
                        Self::process_guild_speech_request(&ctx, guild_id, &message).await
                    {
                        eprintln!("Failed to announce voice channel join: {}", e);
                    }
                }
            } else if old_state.as_ref().map(|s| s.channel_id) == Some(Some(bot_channel_id))
                && new_state.channel_id != Some(bot_channel_id)
            {
                // ユーザーがボットのいるボイスチャンネルから退出
                if let Some(member) = get_member_from_ctx(&ctx, guild_id, user_id) {
                    let display_name = member.display_name();
                    let message = format!("{}さんが退出しました。", display_name);
                    if let Err(e) =
                        Self::process_guild_speech_request(&ctx, guild_id, &message).await
                    {
                        eprintln!("Failed to announce voice channel leave: {}", e);
                    }
                }
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
    async fn process_inactive_command(ctx: &Context, msg: &Message) {
        // joinコマンドは非アクティブな場合でも実行できる必要があるため、ここで処理。
        if msg.content == "u!join" {
            if let Err(e) = join::join_command(&ctx, &msg).await {
                println!("Error processing !join command: {}", e);
            }
        }
    }

    /// "!"から始まるコマンドを処理します。
    ///
    /// ## Arguments
    /// * `ctx` - ボットの状態に関する様々なデータのコンテキスト。
    /// * `msg` - メッセージ。
    /// * `guild_id` - ギルドID。
    async fn process_active_command(ctx: &Context, msg: &Message, guild_id: GuildId) {
        match msg.content.as_str() {
            "u!leave" => {
                if let Err(e) = leave::leave_command(ctx, msg).await {
                    println!("Error when trying to leave voice channel: {}", e);
                }
            }
            "u!skip" => {
                skip::skip_command(ctx, guild_id).await; // Assume this handles its errors internally
            }
            "u!clear" => {
                clear::clear_command(ctx, guild_id).await; // Assume this handles its errors internally
            }
            "u!liststyles" => {
                liststyles::list_styles_command(ctx, msg).await; // Assume this handles its errors internally
            }
            "u!help" => {
                help::help_command(ctx, msg).await;
            }
            _ => {}
        }
        if msg.content.starts_with("u!setstyle") {
            let args: Vec<&str> = msg.content.split_whitespace().collect();
            setstyle::set_style_command(ctx, msg, args, guild_id).await; // Assume this handles its errors internally
        }
    }

    /// メッセージを読み上げるリクエストを処理します。
    ///
    /// ## Arguments
    /// * `ctx` - ボットの状態に関する様々なデータのコンテキスト。
    /// * `msg` - メッセージ。
    /// * `guild_id` - ギルドID。
    async fn process_user_speech_request(
        ctx: &Context,
        msg: &Message,
        guild_id: GuildId,
    ) -> Result<(), Box<dyn Error + Send + Sync>> {
        // メッセージ内容が空か、スペースのみであれば読み上げない
        if msg.content.trim().is_empty() {
            return Ok(());
        }
        // ユーザーの style_id を取得
        let user_id = msg.author.id;

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

        // 制限を取り払う場合。デバッグ用。
        // let speech_text = sanitized_content.clone();

        let style_id = get_user_style(&ctx, user_id, guild_id).await?;

        let request = SynthesisContext::new(speech_text.to_string(), style_id.to_string());

        // 音声合成キューマネージャーを取得し、リクエストを追加して処理を開始します。
        let synthesis_queue_manager = get_data_from_ctx::<SynthesisQueueManagerKey>(&ctx).await;
        synthesis_queue_manager
            .add_request_to_synthesis_queue(guild_id, request)
            .await;
        synthesis_queue_manager
            .start_processing(&ctx, guild_id)
            .await?;

        Ok(())
    }

    /// メッセージを読み上げるリクエストを処理します。
    ///
    /// ## Arguments
    /// * `ctx` - ボットの状態に関する様々なデータのコンテキスト。
    /// * `msg` - メッセージ。
    /// * `guild_id` - ギルドID。
    async fn process_guild_speech_request(
        ctx: &Context,
        guild_id: GuildId,
        message: &str,
    ) -> Result<(), Box<dyn Error + Send + Sync>> {
        let style_id = get_guild_style(&ctx, guild_id).await?;

        println!("msg.content: {}", message);

        let sanitized_content: String = sanitize_message(&ctx, &message, guild_id).await;
        println!("Sanitized message: {}", sanitized_content);

        // メッセージを読み上げる処理
        // Context から SynthesisQueue を取得
        let speech_text = if sanitized_content.chars().count() > 200 {
            sanitized_content.chars().take(200).collect::<String>() + "...以下略"
        } else {
            sanitized_content.clone()
        };

        let request = SynthesisContext::new(speech_text.to_string(), style_id.to_string());

        // 音声合成キューマネージャーを取得し、リクエストを追加して処理を開始します。
        let synthesis_queue_manager = get_data_from_ctx::<SynthesisQueueManagerKey>(&ctx).await;
        synthesis_queue_manager
            .add_request_to_synthesis_queue(guild_id, request)
            .await;
        synthesis_queue_manager
            .start_processing(&ctx, guild_id)
            .await?;

        Ok(())
    }

    async fn process_attachments(
        ctx: &Context,
        msg: &Message,
        guild_id: GuildId,
    ) -> Result<(), Box<dyn Error + Send + Sync>> {
        let mut attachment_counts = HashMap::new();
        for attachment in &msg.attachments {
            let kind = match attachment.filename.split('.').last().unwrap_or("") {
                "gif" => "GIF画像",
                "mp4" | "webm" => "動画",
                "mp3" | "wav" => "音声ファイル",
                "png" | "jpg" | "jpeg" => "画像",
                "txt" => "テキストファイル",
                _ => "ファイル",
            };
            *attachment_counts.entry(kind).or_insert(0) += 1;
        }

        let mut read_message = String::new();
        let mut current_type = 0;
        for (kind, count) in attachment_counts {
            current_type += 1;
            if current_type > 1 {
                read_message.push_str("と");
            }
            if count == 1 {
                read_message.push_str(kind);
            } else {
                read_message.push_str(&format!("{}個の{}", count, kind));
            }
        }

        if !read_message.is_empty() {
            read_message.push_str("が投稿されました");
            if let Err(e) = Self::process_guild_speech_request(&ctx, guild_id, &read_message).await
            {
                eprintln!("Failed to announce attachments: {}", e);
            }
        }

        Ok(())
    }
}

async fn sanitize_message(ctx: &Context, msg: &str, guild_id: GuildId) -> String {
    let data_read = ctx.data.read().await;
    let emoji_data = data_read
        .get::<EmojiData>()
        .expect("Expected emoji data in TypeMap.");

    let re_user = Regex::new(r"<@!?(\d+)>").unwrap();
    let re_channel = Regex::new(r"<#(\d+)>").unwrap();
    let re_role = Regex::new(r"<@&(\d+)>").unwrap();
    let re_emoji = Regex::new(r"<:([^:]+):\d+>").unwrap();
    let re_url = Regex::new(
        r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+",
    )
    .unwrap();

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

    // 絵文字を short_name に置き換え
    for (emoji, short_name) in emoji_data {
        sanitized = sanitized.replace(emoji, short_name);
    }

    // Replace custom emojis
    sanitized = re_emoji
        .replace_all(&sanitized, |caps: &regex::Captures| format!("{}", &caps[1]))
        .to_string();

    // URLを「リンク」という単語に置き換えます。
    sanitized = re_url.replace_all(&sanitized, "リンク").to_string();

    // 絵文字を short_name に置き換え
    for (emoji, short_name) in emoji_data {
        sanitized = sanitized.replace(emoji, short_name);
    }

    sanitized
}
pub struct EmojiData;

impl TypeMapKey for EmojiData {
    type Value = HashMap<String, String>;
}

/// JSON ファイルから絵文字データを読み込みます。
///
/// ## Returns
/// * `HashMap<String, String>` - 絵文字データ。
pub fn load_emoji_data() -> HashMap<String, String> {
    // 環境変数に"EMOJI_DATA_PATH"が設定されていない場合は、相対パス"resources"を使用します。
    let dir_path = env::var("EMOJI_DATA_DIR").unwrap_or("resources".to_string());
    let mut file_path = PathBuf::from(dir_path);
    file_path.push("emoji_ja.json");
    let file = File::open(file_path).expect("file should open read only");
    let json: HashMap<String, Value> = from_reader(file).expect("file should be proper JSON");
    json.iter()
        .filter_map(|(key, val)| {
            if let Some(short_name) = val["short_name"].as_str() {
                if !val["group"].as_str().unwrap_or("").is_empty() {
                    Some((key.clone(), short_name.to_string()))
                } else {
                    None
                }
            } else {
                None
            }
        })
        .collect()
}

/// データコンテキスト、ギルドID、ユーザーIDを指定して、メンバーを取得します。
///
/// ## Arguments
/// * `ctx` - ボットの状態に関する様々なデータのコンテキスト。
/// * `guild_id` - ギルドID。
/// * `user_id` - ユーザーID。
///
/// ## Returns
/// * `Option<Member>` - メンバー、またはNone。
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

/// 指定したテキストチャンネルがアクティブなチャンネルであるかどうかを返します。
/// アクティブなチャンネルとは、最後にjoinコマンドが実行されたテキストチャンネルです。
///
/// ## Arguments
/// * `ctx` - ボットの状態に関する様々なデータのコンテキスト。
/// * `guild_id` - ギルドID。
/// * `text_channel_id` - テキストチャンネルID。
///
/// ## Returns
/// * `bool` - 指定したテキストチャンネルがアクティブなチャンネルであるかどうか。
async fn is_active_text_channel(
    ctx: &Context,
    guild_id: GuildId,
    text_channel_id: ChannelId,
) -> bool {
    let tracker = get_data_from_ctx::<VoiceChannelTrackerKey>(&ctx).await;
    tracker
        .is_active_text_channel(guild_id, text_channel_id)
        .await
}

/// データコンテキスト、ギルドID、ユーザーIDを指定し、スタイルIDを取得します。
///
/// ## Arguments
/// * `ctx` - ボットの状態に関する様々なデータのコンテキスト。
/// * `user_id` - ユーザーID。
/// * `guild_id` - ギルドID。
///
/// ## Returns
/// * `Result<String, Box<dyn Error + Send + Sync>>` - スタイルID、またはエラー。
async fn get_user_style(
    ctx: &Context,
    user_id: UserId,
    guild_id: GuildId,
) -> Result<i32, Box<dyn Error + Send + Sync>> {
    let config_lock = get_data_from_ctx::<UsapyonConfigKey>(&ctx).await;
    let config = config_lock.lock().await;
    match config.get_user_style(user_id, guild_id).await {
        Ok(style_id) => Ok(style_id),
        Err(e) => Err(Box::new(e) as Box<dyn Error + Send + Sync>),
    }
}

/// データコンテキストとギルドIDを指定し、スタイルIDを取得します。
///
/// ## Arguments
/// * `ctx` - ボットの状態に関する様々なデータのコンテキスト。
/// * `guild_id` - ギルドID。
///
/// ## Returns
/// * `Result<String, Box<dyn Error + Send + Sync>>` - スタイルID、またはエラー。
async fn get_guild_style(
    ctx: &Context,
    guild_id: GuildId,
) -> Result<i32, Box<dyn Error + Send + Sync>> {
    let config_lock = get_data_from_ctx::<UsapyonConfigKey>(&ctx).await;
    let config = config_lock.lock().await;
    match config.get_guild_style(guild_id).await {
        Ok(style_id) => Ok(style_id),
        Err(e) => Err(Box::new(e) as Box<dyn Error + Send + Sync>),
    }
}
