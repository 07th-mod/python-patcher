use glium::glutin;
use glium::glutin::event::{Event, WindowEvent};
use glium::glutin::event_loop::{ControlFlow, EventLoop};
use glium::glutin::window::WindowBuilder;
use glium::{Display, Surface};
use imgui::{Context, FontConfig, FontGlyphRanges, FontSource, Ui};
use imgui_glium_renderer::Renderer;
use imgui_winit_support::{HiDpiMode, WinitPlatform};
use std::path::Path;
use std::time::Instant;

mod clipboard;

pub struct System {
	pub event_loop: EventLoop<()>,
	pub display: glium::Display,
	pub imgui: Context,
	pub platform: WinitPlatform,
	pub renderer: Renderer,
	pub font_size: f32,
}

pub fn init(title: &str, window_size: [f64; 2]) -> System {
	let title = match Path::new(&title).file_name() {
		Some(file_name) => file_name.to_str().unwrap(),
		None => title,
	};
	let event_loop = EventLoop::new();
	let context = glutin::ContextBuilder::new().with_vsync(true);
	let builder = WindowBuilder::new()
		.with_title(title.to_owned())
		.with_inner_size(glutin::dpi::LogicalSize::new(
			window_size[0],
			window_size[1],
		));
	let display =
		Display::new(builder, context, &event_loop).expect("Failed to initialize display");

	let mut imgui = Context::create();
	imgui.set_ini_filename(None);

	if let Some(backend) = clipboard::init() {
		imgui.set_clipboard_backend(Box::new(backend));
	} else {
		eprintln!("Failed to initialize clipboard");
	}

	let mut platform = WinitPlatform::init(&mut imgui);
	{
		let gl_window = display.gl_window();
		let window = gl_window.window();
		platform.attach_window(imgui.io_mut(), window, HiDpiMode::Rounded);
	}

	let hidpi_factor = platform.hidpi_factor();
	let font_size = (20.0 * hidpi_factor) as f32;
	imgui.fonts().add_font(&[
		FontSource::TtfData {
			data: include_bytes!("Roboto-Regular.ttf"),
			size_pixels: font_size,
			config: Some(FontConfig {
				rasterizer_multiply: 1.75,
				glyph_ranges: FontGlyphRanges::japanese(),
				..FontConfig::default()
			}),
		},
		FontSource::DefaultFontData {
			config: Some(FontConfig {
				size_pixels: font_size,
				..FontConfig::default()
			}),
		},
	]);

	imgui.io_mut().font_global_scale = (1.0 / hidpi_factor) as f32;

	let renderer = Renderer::init(&mut imgui, &display).expect("Failed to initialize renderer");

	System {
		event_loop,
		display,
		imgui,
		platform,
		renderer,
		font_size,
	}
}

impl System {
	pub fn main_loop<A: ApplicationGUI + 'static>(self, mut application: A) {
		let System {
			event_loop,
			display,
			mut imgui,
			mut platform,
			mut renderer,
			..
		} = self;
		let mut last_frame = Instant::now();

		event_loop.run(move |event, _, control_flow| match event {
			Event::NewEvents(_) => {
				let now = Instant::now();
				imgui.io_mut().update_delta_time(now - last_frame);
				last_frame = now;
			}
			Event::MainEventsCleared => {
				let gl_window = display.gl_window();
				platform
					.prepare_frame(imgui.io_mut(), gl_window.window())
					.expect("Failed to prepare frame");
				gl_window.window().request_redraw();
			}
			Event::RedrawRequested(_) => {
				let mut ui = imgui.frame();

				let mut nextFrameUpdates = application.run_ui(&mut ui);

				if !nextFrameUpdates.run {
					*control_flow = ControlFlow::Exit;
				}

				let gl_window = display.gl_window();

				let mut target = display.draw();
				target.clear_color_srgb(1.0, 1.0, 1.0, 1.0);
				let window = gl_window.window();

				if nextFrameUpdates.force_show_window {
					window.set_minimized(false);
					window.set_visible(true);
				}

				platform.prepare_render(&ui, window);
				let draw_data = ui.render();
				renderer
					.render(&mut target, draw_data)
					.expect("Rendering failed");
				target.finish().expect("Failed to swap buffers");
			}
			event => {
				match &event {
					Event::WindowEvent {
						window_id: id,
						event: window_event,
					} => {
						application.handle_event(window_event);
					}
					_ => {}
				}

				let gl_window = display.gl_window();
				platform.handle_event(imgui.io_mut(), gl_window.window(), &event);
			}
		});
	}
}

pub struct ExitInfo {
	pub retry_using_tempdir: bool,
}

pub struct NextFrameUpdates {
	pub run: bool,
	pub force_show_window: bool,
}

pub trait ApplicationGUI {
	fn run_ui(&mut self, ui: &mut Ui) -> NextFrameUpdates;
	fn handle_event(&mut self, event: &WindowEvent);
	fn exit_info(&self) -> ExitInfo;
}
