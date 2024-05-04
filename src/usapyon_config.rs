extern crate reqwest;
extern crate serde;
extern crate serde_json;

use rusqlite::{params, Connection, Result};
use serde::{Deserialize, Serialize};
use serenity::model::id::{GuildId, UserId};
use songbird::typemap::TypeMapKey;
use std::collections::HashMap;
use std::error::Error;
use std::sync::Arc;
use tokio::sync::Mutex;

/// スタイル情報を格納する構造体。
/// VoiceVoxサーバーのspeakersエンドポイントから取得したデータのstyleを格納します。
/// 各フィールドは、jsonのキーに対応しています。
#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct Style {
    /// スタイル名。
    pub name: String,

    /// スタイルID。
    pub id: i32,

    /// スタイルの種類。（talkだけ？）
    #[serde(rename = "type")]
    pub style_type: String,
}

/// スピーカー情報を格納する構造体。
/// VoiceVoxサーバーのspeakersエンドポイントから取得したデータを格納します。
/// 各フィールドは、jsonのキーに対応しています。
#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct Speaker {
    /// スピーカー名。
    pub name: String,

    /// スピーカーのUUID。
    pub speaker_uuid: String,

    /// スピーカーのスタイル情報。
    pub styles: Vec<Style>,

    /// スピーカーのバージョン？？？
    pub version: String,

    pub supported_features: HashMap<String, String>,
}

impl Speaker {
    /// クレジット名を返します。特定のスピーカーは、名前とクレジット名が異なる場合があります。
    ///
    /// ## Returns
    /// * `String` - クレジット名。
    pub fn get_credit_name(&self) -> String {
        match self.name.as_str() {
            "もち子さん" => "もち子(cv 明日葉よもぎ)".to_string(),
            _ => self.name.clone(),
        }
    }
}

/// ユーザーとギルドのスタイル設定を管理する構造体。
pub struct UsapyonConfig {
    /// スピーカー情報のリスト。
    pub speakers: Vec<Speaker>,

    /// ユーザーIDとスタイルIDのマッピング。
    pub user_style_settings: HashMap<UserId, i32>,

    /// ギルドIDとスタイルIDのマッピング。
    pub guild_style_settings: HashMap<GuildId, i32>,

    /// SQLiteデータベースの接続。
    conn: Arc<Mutex<rusqlite::Connection>>,
}

impl UsapyonConfig {
    /// VoiceVoxサーバーのspeakersからスタイル情報を取得し、`UsapyonConfig`を初期化します。
    ///
    /// ## Arguments
    /// * `url` - VoiceVoxサーバーのspeakersエンドポイントのURL。
    ///
    /// ## Returns
    /// * `Result<UsapyonConfig, Box<dyn Error>>` - `UsapyonConfig`のインスタンス。
    pub async fn new(url: &str) -> Result<Self, Box<dyn Error>> {
        let resp = reqwest::get(url).await?.text().await?;
        let speakers: Vec<Speaker> = serde_json::from_str(&resp)?;

        // SQLiteデータベースと接続。
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

/// `UsapyonConfig`のインスタンスを格納するための`TypeMapKey`。
pub struct UsapyonConfigKey;

impl TypeMapKey for UsapyonConfigKey {
    type Value = Arc<Mutex<UsapyonConfig>>;
}

/// ユーザーごとのスタイル設定とギルドごとのスタイル設定を格納するデータベースを初期化します。
///
/// ## Returns
/// * `Result<Connection>` - `rusqlite::Connection`のインスタンス。
fn init_db() -> Result<Connection> {
    let conn = Connection::open("usapyon_styles.db")?;

    // ユーザーごとのスタイル設定を格納するテーブルが存在しない場合は作成。
    conn.execute(
        "CREATE TABLE IF NOT EXISTS user_styles (
            user_id INTEGER PRIMARY KEY,
            style_id INTEGER NOT NULL
        )",
        [],
    )?;

    // ギルドごとのスタイル設定を格納するテーブルが存在しない場合は作成。
    conn.execute(
        "CREATE TABLE IF NOT EXISTS guild_styles (
            guild_id INTEGER PRIMARY KEY,
            style_id INTEGER NOT NULL
        )",
        [],
    )?;
    Ok(conn)
}
