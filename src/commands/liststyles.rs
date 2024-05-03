use serenity::all::{Context, Message};

use crate::usapyon_config::get_usapyon_config;

pub async fn list_styles_command(ctx: &Context, msg: &Message) {
    let config_lock = get_usapyon_config(ctx).await;
    let config = config_lock.lock().await;

    let mut response = String::from("Available Styles:\n");
    for speaker in &config.speakers {
        response.push_str(&format!("Speaker: {}\n", speaker.name)); // スピーカー名を追加
        for style in &speaker.styles {
            let style_info = format!(
                "  ID: {}, Name: {}, Type: {}\n",
                style.id, style.name, style.style_type
            );
            if response.len() + style_info.len() > 1900 {
                // Discordの最大メッセージ長に近づいたら送信
                if let Err(e) = msg.channel_id.say(&ctx.http, &response).await {
                    println!("Error sending message: {:?}", e);
                }
                response.clear(); // レスポンスをリセット
                response.push_str("Available Styles (continued):\n"); // 新しいメッセージのヘッダー
            }
            response.push_str(&style_info);
        }
        response.push('\n'); // スピーカー間に空行を挿入
    }

    if !response.is_empty() {
        if let Err(e) = msg.channel_id.say(&ctx.http, &response).await {
            println!("Error sending message: {:?}", e);
        }
    }
}
