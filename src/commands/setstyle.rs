use crate::usapyon_config::UsapyonConfigKey;
use serenity::all::{Context, GuildId, Message, UserId};

pub async fn set_style_command(ctx: &Context, msg: &Message, args: Vec<&str>, guild_id: GuildId) {
    if args.len() < 3 {
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
    let style_id = match style_id_str.parse::<i32>() {
        Ok(id) => id,
        Err(_) => {
            msg.reply(ctx, "Invalid style ID. Please enter a numeric value.")
                .await
                .unwrap();
            return;
        }
    };

    let data = ctx.data.read().await;
    let config = data
        .get::<UsapyonConfigKey>()
        .expect("Config should be available");
    let mut config = config.lock().await;

    // Clone necessary data before the mutable borrow
    let speakers = config.speakers.clone();

    let style_opt = speakers
        .iter()
        .find(|s| s.styles.iter().any(|st| st.id == style_id))
        .map(|s| {
            (
                s,
                s.styles
                    .iter()
                    .find(|st| st.id == style_id)
                    .unwrap()
                    .clone(),
            )
        });

    if let Some((speaker, style)) = style_opt {
        config.set_user_style(user_id, style_id);
        let reply = format!(
            "Style ID {} set successfully for user {}. Speaker name: {}, Style name: {}, Type: {}",
            style_id, user_id, speaker.name, style.name, style.style_type
        );
        msg.reply(ctx, &reply).await.unwrap();
    } else {
        msg.reply(ctx, "Style ID not found.").await.unwrap();
    }
}

async fn set_guild_style(ctx: &Context, msg: &Message, style_id_str: &str, guild_id: GuildId) {
    let style_id = match style_id_str.parse::<i32>() {
        Ok(id) => id,
        Err(_) => {
            msg.reply(ctx, "Invalid style ID. Please enter a numeric value.")
                .await
                .unwrap();
            return;
        }
    };

    let data = ctx.data.read().await;
    let config = data
        .get::<UsapyonConfigKey>()
        .expect("Config should be available");
    let mut config = config.lock().await;

    let speakers = config.speakers.clone();

    let style_opt = speakers
        .iter()
        .find(|s| s.styles.iter().any(|st| st.id == style_id))
        .map(|s| {
            (
                s,
                s.styles
                    .iter()
                    .find(|st| st.id == style_id)
                    .unwrap()
                    .clone(),
            )
        });

    if let Some((speaker, style)) = style_opt {
        config.set_guild_style(guild_id, style_id);
        let reply = format!(
            "Style ID {} set successfully for guild {}. Speaker name: {}, Style name: {}, Type: {}",
            style_id, guild_id, speaker.name, style.name, style.style_type
        );
        msg.reply(ctx, &reply).await.unwrap();
    } else {
        msg.reply(ctx, "Style ID not found.").await.unwrap();
    }
}
