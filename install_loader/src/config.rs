use std::path::{Path, PathBuf};

// Please define these as paths relative to the current directory
pub struct InstallerConfig {
	pub sub_folder: &'static Path,
	pub logs_folder: PathBuf,
	pub python_path: PathBuf,
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
