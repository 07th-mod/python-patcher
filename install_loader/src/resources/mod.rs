use anyhow::Result;

struct GenericIcon {
	width: u32,
	height: u32,
	data: Vec<u8>,
}

// The icon used for the window is embedded as a .png file
// At runtime, it is decoded and used for both the launcher window
// and the wry webview window icon
fn get_icon() -> Result<GenericIcon> {
	let raw_png = include_bytes!("icon_small.png");
	let decoder = png::Decoder::new(&raw_png[..]);
	let mut reader = decoder.read_info()?;
	let mut buf = vec![0; reader.output_buffer_size()];

	// Assume the .png only has 1 frame. Truncate buffer to just the first frame.
	let info = reader.next_frame(&mut buf)?;
	buf.truncate(info.buffer_size());

	Ok(GenericIcon {
		width: info.width,
		height: info.height,
		data: buf,
	})
}

pub fn get_wry_icon() -> Result<wry::application::window::Icon> {
	let icon = get_icon()?;
	Ok(wry::application::window::Icon::from_rgba(
		icon.data,
		icon.width,
		icon.height,
	)?)
}

pub fn get_glium_icon() -> Result<glium::glutin::window::Icon> {
	let icon = get_icon()?;
	Ok(glium::glutin::window::Icon::from_rgba(
		icon.data,
		icon.width,
		icon.height,
	)?)
}
