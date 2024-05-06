use songbird::{
    events::{Event, EventContext, EventHandler as SongbirdEventHandler},
    tracks::PlayMode,
};
use std::{future::Future, pin::Pin};

pub struct CreditDisplayHandler;

impl SongbirdEventHandler for CreditDisplayHandler {
    fn act<'life0, 'life1, 'life2, 'async_trait>(
        &'life0 self,
        ctx: &'life1 EventContext<'life2>,
    ) -> Pin<Box<dyn Future<Output = Option<Event>> + Send + 'async_trait>>
    where
        Self: 'async_trait,
        'life0: 'async_trait,
        'life1: 'async_trait,
        'life2: 'async_trait,
    {
        Box::pin(async move {
            if let EventContext::Track(track_events) = ctx {
                for (track_state, _track_handle) in (*track_events).iter() {
                    match track_state.playing {
                        PlayMode::Play => {
                            println!("Track started!");
                        }
                        _ => {}
                    }
                }
            }
            None
        })
    }
}
