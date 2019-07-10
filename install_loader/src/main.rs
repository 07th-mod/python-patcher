#![warn(clippy::all)]

use xz2::read::XzDecoder;
use tar::Archive;
use std::path::Path;

fn main() -> std::io::Result<()> {
	// Tell the user not to close the terminal window
	println!();
	println!("------------------------------------------------------------");
	println!("Do NOT close this window, unless you are finished installing");
	println!("------------------------------------------------------------");
	println!();

	// Extract all files to this subfolder (relative to the executable)
	let sub_folder_path = Path::new("07th-mod_installer");

	// During compilation, include the installer archive in .tar.xz format
	//NOTE: The below file must be placed adjacent to this source file!
	//The archive should not contain any subfolders - one will be created automatically
	let archive_bytes = include_bytes!("install_data.tar.xz");

	// Pipe from the XzDecoder (.xz handler) to the Archive (.tar handler), then extract all files.
	println!("[07th-Mod Installer Loader] Please wait. Extracting to [{}]", sub_folder_path.display());
	Archive::new(XzDecoder::new(&archive_bytes[..]))
		.unpack(sub_folder_path).expect("Failed to extract tar archive");

	// Start the installer, and wait for installer to finish
	println!("[07th-Mod Installer Loader] Running installer");
	let mut installer_handle= std::process::Command::new(
		sub_folder_path.join(Path::new("python/python.exe"))
		)
		.current_dir(sub_folder_path)
		.args(&["-E", "main.py"])
		.spawn()
		.expect("loader: failed to run batch file");
	installer_handle.wait().expect("loader: failed to wait on install to finish");

	println!("[07th-Mod Installer Loader] Exited");

	Ok(())
}
