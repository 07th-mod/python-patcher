use crate::windows_utilities;
use imgui::ImString;
use std::path::PathBuf;

// Please define these as paths relative to the current directory
pub struct InstallerConfig {
	pub sub_folder: PathBuf,
	pub sub_folder_display: ImString,
	pub logs_folder: PathBuf,
	pub python_path: PathBuf,
	pub is_retry: bool,
}

impl InstallerConfig {
	pub fn new(root: &PathBuf, is_retry: bool) -> InstallerConfig {
		let sub_folder = PathBuf::from(root);
		let sub_folder_display = ImString::new(windows_utilities::absolute_path_str(
			&sub_folder,
			"couldn't determine path",
		));
		let logs_folder = sub_folder.join("INSTALLER_LOGS");
		let python_path = sub_folder.join("python/python.exe");

		InstallerConfig {
			sub_folder,
			sub_folder_display,
			logs_folder,
			python_path,
			is_retry,
		}
	}
}
