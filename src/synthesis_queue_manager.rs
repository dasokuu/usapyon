use serenity::{model::id::GuildId, prelude::Context};
use songbird::typemap::TypeMapKey;
use std::{
    collections::HashMap,
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc, Mutex,
    },
};

use crate::synthesis_queue::SynthesisQueue;

/// ギルドごとの音声合成の進行状況を管理する構造体。
#[derive(Clone)]
pub struct SynthesisQueueManager {
    guild_states: Arc<Mutex<HashMap<GuildId, Arc<AtomicBool>>>>,
}

impl SynthesisQueueManager {
    pub fn new() -> Self {
        SynthesisQueueManager {
            guild_states: Arc::new(Mutex::new(HashMap::new())),
        }
    }

    pub async fn start_processing(
        &self,
        ctx: &Context,
        guild_id: GuildId,
        synthesis_queue: Arc<SynthesisQueue>,
    ) {
        let is_running_state = {
            let mut states = self.guild_states.lock().expect("Mutex was poisoned");
            states.entry(guild_id)
            .or_insert_with(|| Arc::new(AtomicBool::new(false)))
            .clone()
        };

        if is_running_state.load(Ordering::SeqCst) {
            println!(
                "Synthesis Queue processing is already running for guild {}",
                guild_id
            );
            return;
        }

        is_running_state.store(true, Ordering::SeqCst);
        println!("Synthesis Queue processing started for guild {}", guild_id);

        tokio::spawn({
            async move {
                // 10秒待機
                tokio::time::sleep(tokio::time::Duration::from_secs(10)).await;

                is_running_state.store(false, Ordering::SeqCst);
                println!("Synthesis Queue processing finished for guild {}", guild_id);
            }
        });
    }
}

pub struct SynthesisQueueManagerKey;
impl TypeMapKey for SynthesisQueueManagerKey {
    type Value = Arc<SynthesisQueueManager>;
}