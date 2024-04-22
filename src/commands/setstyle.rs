use serenity::all::{Context, GuildId, Message, UserId};

use crate::usapyon_config::UsapyonConfigKey;

pub async fn set_style_command(ctx: &Context, msg: &Message, args: Vec<&str>, guild_id: GuildId) {
    if args.len() < 2 {
        let reply = "Usage: !setstyle [user|guild] [style_id]";
        msg.reply(ctx, reply).await.unwrap();
        return;
    }

    match args[1] {
        "user" => set_user_style(ctx, msg, args[2], msg.author.id).await,
        "guild" => set_guild_style(ctx, msg, args[2], guild_id).await,
        _ => {
            let _ = msg
                .reply(ctx, "Invalid option. Use 'user' or 'guild'.")
                .await;
        }
    }
}

async fn set_user_style(ctx: &Context, msg: &Message, style_id_str: &str, user_id: UserId) {
    match style_id_str.parse::<i32>() {
        Ok(style_id) => {
            let mut data = ctx.data.write().await;
            if let Some(config) = data.get_mut::<UsapyonConfigKey>() {
                let mut config = config.lock().await;
                config.set_user_style(user_id, style_id);
                let reply = format!(
                    "Style ID {} set successfully for user {}.",
                    style_id, user_id
                );
                msg.reply(ctx, &reply).await.unwrap();
            }
        }
        Err(_) => {
            msg.reply(ctx, "Invalid style ID. Please enter a numeric value.")
                .await
                .unwrap();
        }
    }
}

async fn set_guild_style(ctx: &Context, msg: &Message, style_id_str: &str, guild_id: GuildId) {
    match style_id_str.parse::<i32>() {
        Ok(style_id) => {
            let mut data = ctx.data.write().await;
            if let Some(config) = data.get_mut::<UsapyonConfigKey>() {
                let mut config = config.lock().await;
                config.set_guild_style(guild_id, style_id);
                let reply = format!(
                    "Style ID {} set successfully for guild {}.",
                    style_id, guild_id
                );
                msg.reply(ctx, &reply).await.unwrap();
            }
        }
        Err(_) => {
            msg.reply(ctx, "Invalid style ID. Please enter a numeric value.")
                .await
                .unwrap();
        }
    }
}
