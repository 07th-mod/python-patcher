use std::fs;

use serde::{Deserialize, Serialize};
use anyhow::Result;
use wry::application::{window::Window, dpi::{PhysicalSize, PhysicalPosition}};

use crate::config::InstallerConfig;

#[derive(Serialize, Deserialize, Debug)]
struct ServerInfo {
    ip: String,
    port: usize,
    page: String,
}

pub fn get_url(config: &InstallerConfig) -> Result<String>
{
    // let server_info_contents = read_file_with_polling(&config.server_info_path).context("Failed to read server-info.json from disk")?;
    let server_info_contents = fs::read_to_string(&config.server_info_path)?;

    let server_info : ServerInfo = serde_json::from_str(server_info_contents.as_str())?;

    // NOTE: We ignore the ip address in the .json as we should never be connecting to a host other than localhost
    Ok(format!("http://127.0.0.1:{}/{}", server_info.port, server_info.page))
}

pub fn window_position_size(window: &Window) -> (PhysicalPosition<u32>, PhysicalSize<u32>)
{
    if let Some(monitor) = window.current_monitor()
    {
        let monitor_size = monitor.size();
        let width = std::cmp::min(1600, monitor_size.width * 9 / 10);
        let size = PhysicalSize::new(width, monitor_size.height * 9 / 10);

        let x_pos = monitor_size.width.saturating_sub(size.width)/2;
        let y_pos = monitor_size.height.saturating_sub(size.height)/2;
        let position = PhysicalPosition::new(x_pos, y_pos);

        (position, size)
    }
    else
    {
        (PhysicalPosition::new(0,0), PhysicalSize::new(1280, 720))
    }
}

pub fn launch(url: &str) -> wry::Result<()> {
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

    let (window_position, window_size) = window_position_size(&window);
    window.set_inner_size(window_size);
    window.set_outer_position(window_position);

    let webview =
        WebViewBuilder::new(window)?.with_url(url)?;

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