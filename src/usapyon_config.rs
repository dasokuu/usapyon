extern crate reqwest;
extern crate serde;
extern crate serde_json;

use serde::{Deserialize, Serialize};
use serenity::model::id::{GuildId, UserId};
use songbird::typemap::TypeMapKey;
use std::collections::HashMap;
use std::error::Error;
use std::sync::Arc;
use tokio::sync::Mutex;

// スタイル情報を格納する構造体
#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct Style {
    pub name: String,
    pub id: i32,
    #[serde(rename = "type")]
    pub style_type: String,
}

// スピーカー情報を格納する構造体
#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct Speaker {
    pub name: String,
    pub speaker_uuid: String,
    pub styles: Vec<Style>,
    pub version: String,
    pub supported_features: HashMap<String, String>,
    pub credit_name: Option<String>, // オプションとしてクレジット名を追加
}

impl Speaker {
    // クレジット名を返すメソッド、特定の条件で異なる名前を返す
    pub fn get_credit_name(&self) -> String {
        match self.name.as_str() {
            "もち子さん" => "もち子(cv 明日葉よもぎ)".to_string(),
            _ => self.name.clone(),
        }
    }
}
// UsapyonConfigクラスの定義
pub struct UsapyonConfig {
    pub speakers: Vec<Speaker>,
    pub user_style_settings: HashMap<UserId, i32>, // ユーザーIDとスタイルIDのマッピング
    pub guild_style_settings: HashMap<GuildId, i32>, // ギルドIDとスタイルIDのマッピング
    pub style_cache: StyleCache,
    conn: Arc<Mutex<rusqlite::Connection>>,
}

impl UsapyonConfig {
    pub async fn new(url: &str) -> Result<Self, Box<dyn Error>> {
        let resp = reqwest::get(url).await?.text().await?;
        let speakers: Vec<Speaker> = serde_json::from_str(&resp)?;
        let conn = Arc::new(Mutex::new(init_db()?));
        Ok(UsapyonConfig {
            speakers,
            user_style_settings: HashMap::new(),
            guild_style_settings: HashMap::new(),
            style_cache: StyleCache::new(),
            conn,
        })
    }

    pub async fn set_user_style(&self, user_id: UserId, style_id: i32) -> Result<()> {
        let conn = self.conn.lock().await;
        conn.execute(
            "REPLACE INTO user_styles (user_id, style_id) VALUES (?1, ?2)",
            params![i64::from(user_id), style_id],
        )?;
        self.style_cache.set_user_style(user_id, style_id).await;
        Ok(())
    }

    pub async fn get_user_style(&self, user_id: UserId) -> Result<i32> {
        let conn = self.conn.lock().await;
        if let Some(style_id) = self.style_cache.get_user_style(user_id).await {
            Ok(style_id)
        } else {
            let style_id = conn.query_row(
                "SELECT style_id FROM user_styles WHERE user_id = ?1",
                params![i64::from(user_id)],
                |row| row.get(0),
            )?;
            self.style_cache.set_user_style(user_id, style_id).await;
            Ok(style_id)
        }
    }

    pub async fn set_guild_style(&self, guild_id: GuildId, style_id: i32) -> Result<()> {
        let conn = self.conn.lock().await;
        conn.execute(
            "REPLACE INTO guild_styles (guild_id, style_id) VALUES (?1, ?2)",
            params![i64::from(guild_id), style_id],
        )?;
        self.style_cache.set_guild_style(guild_id, style_id).await;
        Ok(())
    }

    pub async fn get_guild_style(&self, guild_id: GuildId) -> Result<i32> {
        let conn = self.conn.lock().await;
        if let Some(style_id) = self.style_cache.get_guild_style(guild_id).await {
            Ok(style_id)
        } else {
            let style_id = conn.query_row(
                "SELECT style_id FROM guild_styles WHERE guild_id = ?1",
                params![i64::from(guild_id)],
                |row| row.get(0),
            )?;
            self.style_cache.set_guild_style(guild_id, style_id).await;
            Ok(style_id)
        }
    }

    pub async fn get_credit_name_by_style_id(&self, style_id: i32) -> Result<String, String> {
        for speaker in &self.speakers {
            for style in &speaker.styles {
                if style.id == style_id {
                    return Ok(speaker.get_credit_name()); // スピーカーのget_credit_nameメソッドを呼び出す
                }
            }
        }
        Err("Style ID not found".to_string())
    }
}

pub struct UsapyonConfigKey;

impl TypeMapKey for UsapyonConfigKey {
    type Value = Arc<Mutex<UsapyonConfig>>;
}

use rusqlite::{params, Connection, Result};

fn init_db() -> Result<Connection> {
    let conn = Connection::open("usapyon_styles.db")?;
    conn.execute(
        "CREATE TABLE IF NOT EXISTS user_styles (
            user_id INTEGER PRIMARY KEY,
            style_id INTEGER NOT NULL
        )",
        [],
    )?;
    conn.execute(
        "CREATE TABLE IF NOT EXISTS guild_styles (
            guild_id INTEGER PRIMARY KEY,
            style_id INTEGER NOT NULL
        )",
        [],
    )?;
    Ok(conn)
}

#[derive(Clone, Debug)]
pub struct StyleCache {
    user_styles: Arc<Mutex<HashMap<UserId, i32>>>,
    guild_styles: Arc<Mutex<HashMap<GuildId, i32>>>,
}

impl StyleCache {
    fn new() -> Self {
        StyleCache {
            user_styles: Arc::new(Mutex::new(HashMap::new())),
            guild_styles: Arc::new(Mutex::new(HashMap::new())),
        }
    }

    async fn get_user_style(&self, user_id: UserId) -> Option<i32> {
        let styles = self.user_styles.lock().await;
        styles.get(&user_id).cloned()
    }

    async fn set_user_style(&self, user_id: UserId, style_id: i32) {
        let mut styles = self.user_styles.lock().await;
        styles.insert(user_id, style_id);
    }

    async fn get_guild_style(&self, guild_id: GuildId) -> Option<i32> {
        let styles = self.guild_styles.lock().await;
        styles.get(&guild_id).cloned()
    }

    async fn set_guild_style(&self, guild_id: GuildId, style_id: i32) {
        let mut styles = self.guild_styles.lock().await;
        styles.insert(guild_id, style_id);
    }
}
