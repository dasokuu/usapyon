use reqwest;
use serde_json::Value;
use std::error::Error;

// Asynchronous function `audio_query`
async fn audio_query(text: &str, style_id: i32) -> Result<Value, Box<dyn Error>> {
    // Define the URL and headers as per your application's needs
    let url = format!(
        "{}?text={}&speaker={}",
        "http://127.0.0.1:50021/audio_query", text, style_id
    );

    // Create a client instance
    let client = reqwest::Client::new();

    // Construct the JSON body
    let body = serde_json::json!({
        "text": text,
        "speaker": style_id
    });

    // Make the HTTP POST request
    let response = client.post(&url).json(&body).send().await?;
    // Check for errors
    if response.status().is_success() {
        // Parse the JSON response
        let json_response = response.json::<Value>().await?;
        Ok(json_response)
    } else {
        // Handle error scenarios
        Err(Box::new(std::io::Error::new(
            std::io::ErrorKind::Other,
            "Failed to query audio",
        )))
    }
}
#[tokio::main]
async fn main() {
    let response = audio_query("こんにちは", 1).await;
    match response {
        Ok(json) => println!("Response: {:?}", json),
        Err(e) => eprintln!("Error: {:?}", e),
    }
}
