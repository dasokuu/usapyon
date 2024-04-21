use std::error::Error;
use std::{future::Future, marker::Send};
use tokio::time::{sleep, Duration};

pub struct RetryHandler {
    max_attempts: usize,
    base_delay: u64,
}

impl RetryHandler {
    pub fn new(max_attempts: usize, base_delay: u64) -> Self {
        Self {
            max_attempts,
            base_delay,
        }
    }

    pub async fn execute_with_retry<F, Fut, T>(
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
                    let delay = Duration::from_secs(self.base_delay * 2_u64.pow(attempts as u32));
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
