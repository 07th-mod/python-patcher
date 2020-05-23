use glium::glutin::{self, Event};
use glium::{Display, Surface};
use imgui::{Context, FontConfig, FontGlyphRanges, FontSource, Ui};
use imgui_glium_renderer::Renderer;
use imgui_winit_support::{HiDpiMode, WinitPlatform};
use std::time::Instant;

mod clipboard;

pub trait ApplicationGUI {
	fn ui_loop(&mut self, ui: &mut Ui) -> bool;
	fn handle_event(&mut self, event: Event);
}

pub struct System<G: ApplicationGUI> {
	pub events_loop: glutin::EventsLoop,
	pub display: glium::Display,
	pub imgui: Context,
	pub platform: WinitPlatform,
	pub renderer: Renderer,
	pub font_size: f32,
	pub application_gui: G,
}

pub fn init<G: ApplicationGUI>(
	application_gui: G,
	title: &str,
	window_size: [f64; 2],
) -> System<G> {
	let events_loop = glutin::EventsLoop::new();
	let context = glutin::ContextBuilder::new().with_vsync(true);
	let builder = glutin::WindowBuilder::new()
		.with_title(title.to_owned())
		.with_dimensions(glutin::dpi::LogicalSize::new(
			window_size[0],
			window_size[1],
		));

	let display =
		Display::new(builder, context, &events_loop).expect("Failed to initialize display");

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
		platform.attach_window(imgui.io_mut(), &window, HiDpiMode::Rounded);
	}

	let hidpi_factor = platform.hidpi_factor();
	// Set font size to 13 if using the default font
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
		events_loop,
		display,
		imgui,
		platform,
		renderer,
		font_size,
		application_gui,
	}
}

impl<G> System<G>
where
	G: ApplicationGUI,
{
	pub fn main_loop(self) {
		let System {
			mut events_loop,
			display,
			mut imgui,
			mut platform,
			mut renderer,
			font_size: _font_size,
			mut application_gui,
		} = self;
		let gl_window = display.gl_window();
		let window = gl_window.window();
		let mut last_frame = Instant::now();
		let mut run = true;

		while run {
			events_loop.poll_events(|event| {
				platform.handle_event(imgui.io_mut(), &window, &event);
				application_gui.handle_event(event);
			});

			let io = imgui.io_mut();
			platform
				.prepare_frame(io, &window)
				.expect("Failed to start frame");
			last_frame = io.update_delta_time(last_frame);
			let mut ui = imgui.frame();

			run = application_gui.ui_loop(&mut ui);

			let mut target = display.draw();
			target.clear_color_srgb(1.0, 1.0, 1.0, 1.0);
			platform.prepare_render(&ui, &window);
			let draw_data = ui.render();
			renderer
				.render(&mut target, draw_data)
				.expect("Rendering failed");
			target.finish().expect("Failed to swap buffers");
		}
	}
}
