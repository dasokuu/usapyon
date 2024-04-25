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
            conn,
        })
    }

    pub async fn set_user_style(&self, user_id: UserId, style_id: i32) -> Result<()> {
        let conn = self.conn.lock().await;
        conn.execute(
            "REPLACE INTO user_styles (user_id, style_id) VALUES (?1, ?2)",
            params![i64::from(user_id), style_id],
        )?;
        Ok(())
    }

    pub async fn get_user_style(&self, user_id: UserId, guild_id: GuildId) -> Result<i32> {
        let conn = self.conn.lock().await;
        let user_style_result = conn.query_row(
            "SELECT style_id FROM user_styles WHERE user_id = ?1",
            params![i64::from(user_id)],
            |row| row.get::<_, i32>(0),
        );

        match user_style_result {
            Ok(style_id) => Ok(style_id),
            Err(rusqlite::Error::QueryReturnedNoRows) => {
                // If no user-specific style is found, check for a guild-specific style in the database
                let guild_style_result = conn.query_row(
                    "SELECT style_id FROM guild_styles WHERE guild_id = ?1",
                    params![i64::from(guild_id)],
                    |row| row.get::<_, i32>(0),
                );
                match guild_style_result {
                    Ok(style_id) => Ok(style_id),
                    Err(rusqlite::Error::QueryReturnedNoRows) => {
                        // If no guild-specific style is found either, return a default style ID
                        Ok(3)
                    }
                    Err(e) => {
                        // Handle other database errors
                        eprintln!("Database error when fetching guild style: {}", e);
                        Err(*Box::new(e))
                    }
                }
            }
            Err(e) => {
                // Handle other database errors
                eprintln!("Database error when fetching user style: {}", e);
                Err(*Box::new(e))
            }
        }
    }

    pub async fn set_guild_style(&self, guild_id: GuildId, style_id: i32) -> Result<()> {
        let conn = self.conn.lock().await;
        conn.execute(
            "REPLACE INTO guild_styles (guild_id, style_id) VALUES (?1, ?2)",
            params![i64::from(guild_id), style_id],
        )?;
        Ok(())
    }

    pub async fn get_guild_style(&self, guild_id: GuildId) -> Result<i32> {
        // キャッシュにない場合はデータベースから取得
        let conn = self.conn.lock().await;
        let guild_style_result = conn.query_row(
            "SELECT style_id FROM guild_styles WHERE guild_id = ?1",
            params![i64::from(guild_id)],
            |row| row.get::<_, i32>(0),
        );

        match guild_style_result {
            Ok(style_id) => Ok(style_id),
            Err(rusqlite::Error::QueryReturnedNoRows) => {
                // ギルドにスタイルが設定されていない場合はデフォルト値を返す
                Ok(3)
            }
            Err(e) => {
                // その他のデータベースエラーを処理
                eprintln!("Database error when fetching guild style: {}", e);
                Err(*Box::new(e))
            }
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
