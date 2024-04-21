extern crate reqwest;
extern crate serde;
extern crate serde_json;

use serde::{Deserialize, Serialize};
use serenity::model::id::UserId;
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
}

// UsapyonConfigクラスの定義
pub struct UsapyonConfig {
    pub speakers: Vec<Speaker>,
    pub user_style_settings: HashMap<UserId, i32>, // ユーザーIDとスタイルIDのマッピング
}
impl UsapyonConfig {
    pub async fn new(url: &str) -> Result<Self, Box<dyn Error>> {
        let resp = reqwest::get(url).await?.text().await?;
        let speakers: Vec<Speaker> = serde_json::from_str(&resp)?;
        Ok(UsapyonConfig {
            speakers,
            user_style_settings: HashMap::new(),
        })
    }

    pub fn set_user_style(&mut self, user_id: UserId, style_id: i32) {
        self.user_style_settings.insert(user_id, style_id);
    }

    pub fn get_user_style(&self, user_id: &UserId) -> Option<i32> {
        self.user_style_settings.get(user_id).copied()
    }
}

pub struct UsapyonConfigKey;

impl TypeMapKey for UsapyonConfigKey {
    type Value = Arc<Mutex<UsapyonConfig>>;
}
