use core::time;
use std::{fs, path::Path, thread};

use serde::{Deserialize, Serialize};
use anyhow::{Result, Context};

use crate::config::InstallerConfig;

#[derive(Serialize, Deserialize, Debug)]
struct ServerInfo {
    ip: String,
    port: usize,
    page: String,
}

// TODO: run this on another thread to prevent UI blocking? usually only blocks for a couple of seconds.
fn read_file_with_polling<P: AsRef<Path> + std::fmt::Debug>(server_info_path: &P) -> Option<String>
{
    let delay = time::Duration::from_millis(500);

    for _ in 0..20 {
        match fs::read_to_string(&server_info_path) {
            Ok(contents) => return Some(contents),
            Err(_) => println!("Poll of {:?} failed, trying again...", server_info_path),
        }

        thread::sleep(delay)
    }

    println!("Poll failed too many times - giving up.");
    None
}

fn get_url_inner(config: &InstallerConfig) -> Result<String>
{
    let server_info_contents = read_file_with_polling(&config.server_info_path).context("Failed to read server-info.json from disk")?;

    let server_info : ServerInfo = serde_json::from_str(server_info_contents.as_str())?;

    // NOTE: We ignore the ip address in the .json as we should never be connecting to a host other than localhost
    Ok(format!("http://127.0.0.1:{}/{}", server_info.port, server_info.page))
}

fn get_url(config: &InstallerConfig) -> String
{
    let default_url = "http://127.0.0.1:8000/loading_screen.html".to_string();


    match get_url_inner(config) {
        Ok(url) => url,
        Err(e) => {
            println!("Warning: Couldn't get server info - defaulting to {}\n{}", default_url, e); 
            default_url 
        },
    }
}

pub fn launch(config: &InstallerConfig) -> wry::Result<()> {
    use wry::{
        application::{
            event::{Event, StartCause, WindowEvent},
            event_loop::{ControlFlow, EventLoop},
            window::WindowBuilder,
        },
        webview::WebViewBuilder,
    };

    let event_loop = EventLoop::new();
    let window = WindowBuilder::new()
        .with_title("07th-mod Installer")
        .build(&event_loop)?;


    let webview =
        WebViewBuilder::new(window)?.with_url(get_url(config).as_str())?;

    #[cfg(debug_assertions)]
    let webview = webview.with_devtools(true);

    let webview = webview.build()?;

    #[cfg(debug_assertions)]
    webview.open_devtools();

    // TODO: spawn event loop on new thread? Currently this freezes the launcher-ui
    // Could also just close the launcher UI at this point as it's not really needed anymore.
    event_loop.run(move |event, _, control_flow| {
        *control_flow = ControlFlow::Wait;

        match event {
            Event::NewEvents(StartCause::Init) => println!("Wry has started!"),
            Event::WindowEvent {
                event: WindowEvent::CloseRequested,
                ..
            } => *control_flow = ControlFlow::Exit,
            _ => (),
        }
    });
}