extern crate reqwest;
extern crate serde;
extern crate serde_json;

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::error::Error;

// スタイル情報を格納する構造体
#[derive(Serialize, Deserialize, Debug, Clone)]
struct Style {
    name: String,
    id: i32,
    #[serde(rename = "type")]
    style_type: String,
}

// スピーカー情報を格納する構造体
#[derive(Serialize, Deserialize, Debug, Clone)]
struct Speaker {
    name: String,
    speaker_uuid: String,
    styles: Vec<Style>,
    version: String,
    supported_features: HashMap<String, String>,
}

// UsapyonConfigクラスの定義
pub(crate) struct UsapyonConfig {
    speakers: Vec<Speaker>,
}

impl UsapyonConfig {
    // 新しいインスタンスを生成するための関数
    pub async fn new(url: &str) -> Result<Self, Box<dyn Error>> {
        let resp = reqwest::get(url).await?.text().await?;
        let speakers: Vec<Speaker> = serde_json::from_str(&resp)?;
        Ok(UsapyonConfig { speakers })
    }

    // スピーカー情報を出力するためのメソッド
    pub fn display_speakers(&self) {
        for speaker in &self.speakers {
            println!("Speaker: {}, UUID: {}", speaker.name, speaker.speaker_uuid);
            for style in &speaker.styles {
                println!("  Style: {}, ID: {}", style.name, style.id);
            }
        }
    }
}

