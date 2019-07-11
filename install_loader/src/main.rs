#![warn(clippy::all)]

use xz2::read::XzDecoder;
use tar::Archive;
use std::path::Path;
use std::{fs, process};

fn extraction_required<P: AsRef<Path>>(saved_git_tag_path : P) -> bool {
	// try to load the last extracted installer's git tag
	let saved_git_tag = match fs::read_to_string(saved_git_tag_path) {
		Ok(val) => val,
		Err(_e) => return true,
	};

	println!("[07th-Mod Installer Loader] Saved: {} -> New: {}", saved_git_tag, env!("TRAVIS_TAG"));

	return env!("TRAVIS_TAG").trim() != saved_git_tag.trim();
}

fn write_extraction_lock<P: AsRef<Path>>(saved_git_tag_path : P) {
	fs::write(saved_git_tag_path, env!("TRAVIS_TAG"))
		.unwrap_or_else(|e| println!("Warning - Failed to write loader extraction lock: {:?}", e))
}

fn press_key_to_exit(message : &str, error : &std::error::Error) -> ! {
	println!();
	println!("------------------------------------------------------------");
	println!("ERROR: {}", message);
	println!("Reason: {}", error);
	println!("------------------------------------------------------------");
	println!();
	println!("Press ENTER to quit the installer...");

	let mut line = String::new();
	let _ = std::io::stdin().read_line(&mut line);
	process::exit(-1);
}

fn main() -> std::io::Result<()> {
	// Tell the user not to close the terminal window
	println!();
	println!("------------------------------------------------------------");
	println!("Do NOT close this window, unless you are finished installing");
	println!("------------------------------------------------------------");
	println!();

	// Extract all files to this subfolder (relative to the executable)
	let sub_folder_path = Path::new("07th-mod_installer");
	let saved_git_tag_path = sub_folder_path.join("installer_loader_extraction_lock.txt");

	if extraction_required(&saved_git_tag_path)
	{
		// During compilation, include the installer archive in .tar.xz format
		//NOTE: The below file must be placed adjacent to this source file!
		//The archive should not contain any subfolders - one will be created automatically
		let archive_bytes = include_bytes!("install_data.tar.xz");

		// Pipe from the XzDecoder (.xz handler) to the Archive (.tar handler), then extract all files.
		println!("[07th-Mod Installer Loader] Please wait. Extracting to [{}]", sub_folder_path.display());
		Archive::new(XzDecoder::new(&archive_bytes[..]))
			.unpack(sub_folder_path)
			.unwrap_or_else(|e| {
				press_key_to_exit("Can't extract files. Make sure all installers are closed and try again.", &e);
			});

		write_extraction_lock(&saved_git_tag_path);
	}

	// Start the installer, and wait for installer to finish
	println!("[07th-Mod Installer Loader] Running installer");
	std::process::Command::new(
sub_folder_path.join(Path::new("python/python.exe"))
		)
		.current_dir(sub_folder_path)
		.args(&["-E", "main.py"])
		.spawn()
		.unwrap_or_else(|e| { press_key_to_exit("Can't run python script", &e); } )
		.wait()
		.unwrap_or_else(|e| { press_key_to_exit("Failed to wait on install to finish", &e); });

	println!("[07th-Mod Installer Loader] Exited");

	Ok(())
}
