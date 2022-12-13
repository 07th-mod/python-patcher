pub fn launch() -> wry::Result<()> {
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
        .with_title("Hello World")
        .build(&event_loop)?;

    // TODO: Tell python script which port to use, OR retreive port to use from python script
    // For now we assume python script chose port 8000, but it could choose other ports if 8000 is in use
    let webview =
        WebViewBuilder::new(window)?.with_url("http://127.0.0.1:8000/loading_screen.html")?;

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