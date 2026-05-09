use std::sync::Mutex;
use reqwest::Client;

pub struct AppStateInner {
    pub access_token: Option<String>,
    pub engine_url: String,
    pub engine_secret: String,
    pub http_client: Client,
    pub current_email: Option<String>,
}

pub struct AppState(pub Mutex<AppStateInner>);

impl AppState {
    pub fn new() -> Self {
        let client = Client::builder()
            .https_only(false)
            .cookie_store(true)
            .timeout(std::time::Duration::from_secs(60))
            .build()
            .expect("error construyendo http client");

        AppState(Mutex::new(AppStateInner {
            access_token: None,
            engine_url: "https://ovd-platform.codigonet.cloud".to_string(),
            engine_secret: String::new(),
            http_client: client,
            current_email: None,
        }))
    }
}
