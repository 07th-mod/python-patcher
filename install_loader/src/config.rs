use crate::windows_utilities;
use imgui::ImString;
use std::path::PathBuf;

#[derive(Debug, Copy, Clone, PartialEq, Eq)]
pub enum LaunchType {
	TextMode,	// Launch the fallback text-mode installer (user interacts with installer via terminal)
	Browser,	// Launch the python installer web server, and let the python script launch the web browser to view it
	WebView,	// Launch the python installer web server, then launch a webview window via Rust to view it
}

// Please define these as paths relative to the current directory
pub struct InstallerConfig {
	pub sub_folder: PathBuf,
	pub sub_folder_display: ImString,
	pub logs_folder: PathBuf,
	pub python_path: PathBuf,
	pub use_temp_dir: bool,
	pub server_info_path: PathBuf,
	pub server_info_old: PathBuf,
	pub webview_data_directory: PathBuf,
}

impl InstallerConfig {
	pub fn new(root: &PathBuf, use_temp_dir: bool) -> InstallerConfig {
		let sub_folder = PathBuf::from(root);
		let sub_folder_display = ImString::new(windows_utilities::absolute_path_str(
			&sub_folder,
			"couldn't determine path",
		));
		let logs_folder = sub_folder.join("INSTALLER_LOGS");
		let python_path = sub_folder.join("python/python.exe");
		let server_info_path = sub_folder.join("server-info.json");
		let server_info_old = sub_folder.join("server-info-old.json");
		let webview_data_directory = sub_folder.join("webview");

		InstallerConfig {
			sub_folder,
			sub_folder_display,
			logs_folder,
			python_path,
			use_temp_dir,
			server_info_path,
			server_info_old,
			webview_data_directory
		}
	}
}
