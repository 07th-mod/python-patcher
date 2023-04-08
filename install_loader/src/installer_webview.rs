use std::{fs, thread, sync::mpsc::{Sender, self}, path::{Path, PathBuf}};

use serde::{Deserialize, Serialize};
use anyhow::Result;
use wry::{application::{window::Window, dpi::{PhysicalSize, PhysicalPosition}, platform::windows::EventLoopExtWindows, event_loop::EventLoopProxy, error::NotSupportedError}, webview::WebContext};

use crate::{config::InstallerConfig, resources};

#[derive(Serialize, Deserialize, Debug)]
struct ServerInfo {
    ip: String,
    port: usize,
    page: String,
}

pub fn get_url(config: &InstallerConfig) -> Result<String>
{
    let server_info_contents = fs::read_to_string(&config.server_info_path)?;

    let server_info : ServerInfo = serde_json::from_str(server_info_contents.as_str())?;

    // NOTE: We ignore the ip address in the .json as we should never be connecting to a host other than localhost
    Ok(format!("http://127.0.0.1:{}/{}", server_info.port, server_info.page))
}

#[derive(Debug)]
pub enum UserEvent {
    NavigateToURL(String),
    SetVisible(bool),
}

pub fn launch<P: AsRef<Path>>(url: String, data_directory: P) -> Result<EventLoopProxy<UserEvent>> {
    let (tx, rx) = mpsc::channel();
    let data_directory = PathBuf::from(data_directory.as_ref());

    // NOTE: once the webview window is launched, it cannot be closed without closing
    // the whole program (not just this thread, but the entire program). So the returned
    // JoinHandle isn't very useful.
    thread::spawn(move || {
        launch_inner(&url.to_string(), Some(data_directory), tx)
    });

    Ok(rx.recv()?)
}


fn launch_inner(url: &str, data_directory: Option<PathBuf>, tx: Sender<EventLoopProxy<UserEvent>>) -> Result<()> {
    use wry::{
        application::{
            event::{Event, StartCause, WindowEvent},
            event_loop::{ControlFlow, EventLoop},
            window::WindowBuilder,
        },
        webview::WebViewBuilder,
    };

    let event_loop = EventLoop::<UserEvent>::new_any_thread();

    tx.send(event_loop.create_proxy())?;

    let window = WindowBuilder::new()
        .with_title("07th-Mod Installer")
        .build(&event_loop)?;

    let (window_position, window_size) = window_position_size(&window);
    window.set_inner_size(window_size);
    window.set_outer_position(window_position);

    // window.set_fullscreen(Some(window::Fullscreen::Borderless(None)));

    // Set the window icon
    // NOTE: Setting the taskbar icon with set_taskbar_icon() seems to have no effect
    // Instead, it is set by embedding an icon into the .exe with the winres library
    window.set_window_icon(resources::get_wry_icon().ok());

    let mut web_context = WebContext::new(data_directory);

    let webview = WebViewBuilder::new(window)?
        .with_web_context(&mut web_context)
        .with_new_window_req_handler(|url| { webbrowser::open(&url).is_err() })
        .with_url(url)?;

    #[cfg(debug_assertions)]
    let webview = webview.with_devtools(true);

    let webview = webview.build()?;

    #[cfg(debug_assertions)]
    webview.open_devtools();

    // This function call can never return - once the user closes the window, the entire program closes!
    event_loop.run(move |event, _, control_flow| {
        *control_flow = ControlFlow::Wait;

        match event {
            Event::UserEvent(UserEvent::NavigateToURL(url)) => webview.load_url(url.as_str()),
            Event::UserEvent(UserEvent::SetVisible(visible)) => webview.window().set_visible(visible),
            Event::NewEvents(StartCause::Init) => println!("Wry has started!"),
            Event::WindowEvent {
                event: WindowEvent::CloseRequested,
                ..
            } => *control_flow = ControlFlow::Exit,
            _ => (),
        }
    });
}

// Note: this function will briefly maximize the window, so that it can correctly calculate the window position.
// We need to do this to take into account the size and position of the taskbar
fn window_position_size(window: &Window) -> (PhysicalPosition<i32>, PhysicalSize<u32>)
{
    let original_maximized_state = window.is_maximized();

    // We use the maximized size of the window in the calculation, rather than the monitor resolution, to take into account
    // the taskbar when setting the windowed size. The taskbar size and position may be on any size of the window,
    // and also be bigger or smaller depending on scaling settings and which windows version they are using.
    window.set_maximized(true);

    let result = window_position_size_inner(window);

    // Reset the maximized state to what it was before calling this function
    window.set_maximized(original_maximized_state);

    // Default to 720p window if can't get outer position of maximized window
    result.unwrap_or((PhysicalPosition::new(0,0), PhysicalSize::new(1280, 720)))
}

// Window should be maximized before calling this function
fn window_position_size_inner(window: &Window) -> Result<(PhysicalPosition<i32>, PhysicalSize<u32>), NotSupportedError>
{
    let maximized_position = window.outer_position()?;
    let maximized_size = window.inner_size();

    // Add padding on all sides of the window
    // UI looks weird if the window is too wide, so also limit width to a reasonable value
    let new_width = std::cmp::min(1600, maximized_size.width * 95 / 100);
    let new_height = maximized_size.height * 95 / 100;

    // Center the window in the middle of the maximized window area (this takes into account the taskbar)
    let new_pos_x = maximized_position.x + ((maximized_size.width - new_width) as i32 / 2);
    let new_pos_y = maximized_position.y + ((maximized_size.height - new_height) as i32 / 2);

    Ok((PhysicalPosition::new(new_pos_x, new_pos_y), PhysicalSize::new(new_width, new_height)))
}