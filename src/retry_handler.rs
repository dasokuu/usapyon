use std::error::Error;
use std::{future::Future, marker::Send};
use tokio::time::{sleep, Duration};

/// リトライ処理を行うための構造体。
pub struct RetryHandler {
    max_attempts: usize,
    base_delay_sec: u64,
}

impl RetryHandler {
    /// 新しい `RetryHandler` を作成します。
    /// 
    /// ## Arguments
    /// * `max_attempts` - リトライの最大試行回数。
    /// * `base_delay` - リトライの最初の遅延時間（秒）。
    pub fn new(max_attempts: usize, base_delay: u64) -> Self {
        Self {
            max_attempts,
            base_delay_sec: base_delay,
        }
    }

    /// 指数バックオフを使用してリトライ処理を行います。
    /// 
    /// ## Arguments
    /// * `task` - リトライ処理を行う関数。
    /// 
    /// ## Returns
    /// * `Result<T, Box<dyn Error + Send + Sync>>` - リトライ処理の結果。
    pub async fn execute_with_exponential_backoff_retry<F, Fut, T>(
        &self,
        mut task: F,
    ) -> Result<T, Box<dyn Error + Send + Sync>>
    where
        F: FnMut() -> Fut,
        Fut: Future<Output = Result<T, Box<dyn Error + Send + Sync>>>,
    {
        let mut attempts = 0;
        while attempts < self.max_attempts {
            match task().await {
                Ok(result) => return Ok(result),
                Err(e) => {
                    let delay = Duration::from_secs(self.base_delay_sec * 2_u64.pow(attempts as u32));
                    println!(
                        "Attempt {} failed, retrying in {:?} seconds... Error: {}",
                        attempts + 1,
                        delay.as_secs(),
                        e
                    );
                    sleep(delay).await;
                    attempts += 1;
                }
            }
        }
        Err("Max retry attempts exceeded".into())
    }
}
