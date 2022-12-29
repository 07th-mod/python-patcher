use glium::glutin;
use glium::glutin::event::{Event, WindowEvent};
use glium::glutin::event_loop::{ControlFlow, EventLoop};
use glium::glutin::window::WindowBuilder;
use glium::{Display, Surface};
use imgui::{Context, FontConfig, FontGlyphRanges, FontSource, Ui};
use imgui_glium_renderer::Renderer;
use imgui_winit_support::{HiDpiMode, WinitPlatform};
use std::path::{Path, PathBuf};
use std::time::Instant;

use crate::resources;

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
		))
		.with_window_icon(resources::get_glium_icon().ok());
	let display =
		Display::new(builder, context, &event_loop).expect("Failed to initialize display");

	let mut imgui = Context::create();
	imgui.set_ini_filename(None);

	// Clipboard disabled for now as we don't use it
	// if let Some(backend) = clipboard::init() {
	// 	imgui.set_clipboard_backend(backend);
	// } else {
	// 	eprintln!("Failed to initialize clipboard");
	// }

	let mut platform = WinitPlatform::init(&mut imgui);
	{
		let gl_window = display.gl_window();
		let window = gl_window.window();
		platform.attach_window(imgui.io_mut(), window, HiDpiMode::Default);
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
	pub fn main_loop<T: 'static + ApplicationGUI, A: 'static + AppBuilder<T>>(
		self,
		mut builder: A,
	) {
		let System {
			event_loop,
			display,
			mut imgui,
			mut platform,
			mut renderer,
			..
		} = self;
		let mut last_frame = Instant::now();
		let mut application = Some(builder.build());
		let mut terminate_next_frame = false;

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
				let gl_window = display.gl_window();
				let window = gl_window.window();
				let mut ui = imgui.frame();

				if let Some(app) = &mut application {
					let next_frame_commands = app.run_ui(&mut ui);

					if terminate_next_frame {
						// Forcibly drop the application to make it clean up anything it still owns
						application = None;

						// call builder's on_exit() to clean up any resources on the builder
						if let Some(failed_cleanup_path) = builder.cleanup() {
							application = Some(builder.build_cleanup_error(failed_cleanup_path));
						} else {
							*control_flow = ControlFlow::Exit;
						}
					}

					if !next_frame_commands.run {
						terminate_next_frame = true;
					}

					if next_frame_commands.force_show_window {
						window.set_minimized(false);
						window.set_visible(true);
					}

					if next_frame_commands.retry_using_tempdir {
						match builder.build_retry() {
							Ok(app) => application = Some(app),
							Err(e) => {
								println!("Error retrying with tempdir: {}", e);
							}
						}
					}
				}

				let mut target = display.draw();
				target.clear_color_srgb(1.0, 1.0, 1.0, 1.0);

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
						window_id: _id,
						event: window_event,
					} => {
						if let Some(app) = &mut application {
							app.handle_event(window_event);
						}
					}
					_ => {}
				}

				let gl_window = display.gl_window();
				platform.handle_event(imgui.io_mut(), gl_window.window(), &event);
			}
		});
	}
}

// Note: there is some application specific logic in the below traits, and also
// in the above main_loop() function. Ideally it shouldn't be in there, but it's easier to do it
// this way for now.
pub struct NextFrameCommands {
	pub run: bool,
	pub force_show_window: bool,
	pub retry_using_tempdir: bool,
}

pub trait ApplicationGUI {
	fn run_ui(&mut self, ui: &mut Ui) -> NextFrameCommands;
	fn handle_event(&mut self, event: &WindowEvent);
}

pub trait AppBuilder<T> {
	fn window_size(&self) -> [f64; 2];
	fn window_name(&self) -> String;
	fn build(&self) -> T;
	fn build_cleanup_error(&self, failed_cleanup_path: PathBuf) -> T;
	fn build_retry(&mut self) -> Result<T, Box<dyn std::error::Error>>;
	fn cleanup(&mut self) -> Option<PathBuf>;
}
