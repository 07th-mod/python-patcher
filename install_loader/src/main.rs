#![warn(clippy::all)]

use std::path::{Path, PathBuf};

mod archive_extractor;
mod panic_handler;
mod process_runner;
mod support; // This module is copied from the imgui-rs examples
mod ui;
mod windows_utilities;
mod version;

// Please define these as paths relative to the current directory
struct InstallerConfig {
	sub_folder: &'static Path,
	logs_folder: PathBuf,
	python_path: PathBuf,
}

impl InstallerConfig {
	pub fn new() -> InstallerConfig {
		let sub_folder = Path::new("07th-mod_installer");
		let logs_folder = Path::new(sub_folder).join("INSTALLER_LOGS");
		let python_path = Path::new(sub_folder).join("python/python.exe");

		InstallerConfig {
			sub_folder,
			logs_folder,
			python_path,
		}
	}
}

fn main() -> std::io::Result<()> {
	panic_handler::set_hook(String::from("07th-mod_crash.log"));

	// Hide the console for windows users to make the installer less scary
	// the console window can un-hidden later if necessary
	windows_utilities::hide_console_window();

	// UI is on "main" thread, so the installer thread is forced to close when the UI window is closed.
	ui::ui_loop();

	Ok(())
}
