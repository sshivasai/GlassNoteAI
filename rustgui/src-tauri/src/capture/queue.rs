use parking_lot::RwLock;
use std::collections::VecDeque;

#[derive(Default)]
pub struct CaptureQueue {
    queue: RwLock<VecDeque<String>>,
}

impl CaptureQueue {
    pub fn new() -> Self {
        Self {
            queue: RwLock::new(VecDeque::new()),
        }
    }

    pub fn add(&self, screenshot: String) {
        self.queue.write().push_back(screenshot);
    }

    pub fn pop_all(&self) -> Vec<String> {
        let mut queue = self.queue.write();
        let items: Vec<String> = queue.drain(..).collect();
        items
    }

    pub fn clear(&self) {
        self.queue.write().clear();
    }

    pub fn len(&self) -> usize {
        self.queue.read().len()
    }

    pub fn is_empty(&self) -> bool {
        self.queue.read().is_empty()
    }
}
