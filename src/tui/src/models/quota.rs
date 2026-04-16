use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QuotaInfo {
    pub cycles_used: u32,
    pub cycles_limit: u32,
    pub tokens_used: u64,
    pub tokens_limit: u64,
    pub period_start: String,
    pub period_end: String,
}

impl QuotaInfo {
    pub fn cycles_percent(&self) -> f64 {
        if self.cycles_limit == 0 {
            return 0.0;
        }
        (self.cycles_used as f64 / self.cycles_limit as f64 * 100.0).min(100.0)
    }

    pub fn tokens_percent(&self) -> f64 {
        if self.tokens_limit == 0 {
            return 0.0;
        }
        (self.tokens_used as f64 / self.tokens_limit as f64 * 100.0).min(100.0)
    }
}
