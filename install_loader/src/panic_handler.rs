use backtrace::Backtrace;

use std::error::Error;
use std::fs::File;
use std::io;
use std::io::{BufRead, Write};
use std::panic::PanicInfo;

use crate::archive_extractor;
use crate::archive_extractor::ExtractionStatus;
use crate::config::InstallerConfig;
use crate::python_launcher;
use crate::version;
use crate::windows_utilities;
use std::path::PathBuf;

/// This function blocks until the user to presses enter in the console
pub fn pause(msg: &str) -> Option<String> {
	// We want the cursor to stay at the end of the line, so we print without a newline and flush manually.
	let mut stderr = io::stderr();
	let _ = write!(stderr, "\n\n{}", msg);
	let _ = stderr.flush();

	// Block until user presses Enter
	let stdin = io::stdin();
	for line in stdin.lock().lines() {
		match line {
			Ok(line) => return Some(line.trim().to_string()),
			Err(_) => break,
		}
	}

	None
}

fn loop_until_valid_input(msg: &str, choices: Vec<&str>) -> String {
	loop {
		match pause(msg) {
			Some(msg) => {
				if choices.contains(&msg.as_str()) {
					return msg;
				}
			}
			_ => {}
		}
	}
}

/// Creates a new file, then writes string to file
fn write_string_to_file(path: &str, s: &String) -> Result<(), io::Error> {
	File::create(path)?.write_all(s.as_bytes())
}

/// Generate a short, end-user readable crash message using the PanicInfo struct you receive in
/// the panic handler hook
fn get_short_crash_message(info: &PanicInfo) -> String {
	let mut expl = String::new();

	expl.push_str(
		r#"The 07th-mod Installer has crashed, however fallback mode is still available, follow the prompts below!

Please help us by reporting the error and submitting the crash log
 - on our Discord server: https://discord.gg/pf5VhF9
 - or, as a Github issue: https://github.com/07th-mod/python-patcher/issues

-----------Error Summary-----------
"#,
	);

	// Print installer version
	expl.push_str(&format!("Installer Version: [{}]\n", version::travis_tag()));

	// Retrieve information about the panic and append to crash message
	let location_str = match info.location() {
		Some(location) => format!("{}", location),
		None => format!("Panic location unknown."),
	};

	let msg = match info.payload().downcast_ref::<&'static str>() {
		Some(s) => *s,
		None => match info.payload().downcast_ref::<String>() {
			Some(s) => &s[..],
			None => "Box<Any>",
		},
	};

	expl.push_str(format!("Thread panicked at '{}', {}\n", msg, location_str).as_str());

	expl.push_str("-----------------------------------\n");

	expl
}

pub fn fallback_installer() -> Result<(), Box<dyn Error>> {
	eprintln!("\n------------- NOTE: 'Fallback Mode' is available ----------");

	// Check if the installer is being run from a temporary folder
	let msg = r"Warning: It appears you're running the installer from a temporary folder, which may cause the installer to fail.
Please download the installer to your Downloads or other known location, then run it from there.

> (If you wish to continue anyway, type 'y' and press ENTER)
";
	if windows_utilities::installer_is_in_temp_folder().unwrap_or(false) {
		loop_until_valid_input(msg, vec!["y"]);
	}

	// Check for VC redist
	let msg_vc_1 = r#"Warning: You are missing the Visual C++ Redistributable (x86), needed to run the installer!
0: to download directly (https://aka.ms/vs/16/release/vc_redist.x86.exe)
1: open the Microsoft website to download it yourself

> (Please type '0' or '1', then press ENTER)
"#;

	let msg_vc_2 = r#"Press ENTER once you've finished installing the redist
If no web page opened, you can use these links to manually download:
Direct Download: https://aka.ms/vs/16/release/vc_redist.x86.exe
Info Page: https://support.microsoft.com/en-au/help/2977003/the-latest-supported-visual-c-download

> (Once you've finished installing the redist, press ENTER)
"#;

	let msg_vc_3 = r#"It looks like the redist is still not installed.
Please make sure it's installed.

> (If you wish to continue anyway, type 'y' and press ENTER)
"#;

	if !windows_utilities::x86_cpp_redist_is_installed() {
		match loop_until_valid_input(msg_vc_1, vec!["0", "1"]).as_str() {
			"0" => {
				let _ = windows_utilities::cpp_redist_download_in_browser();
			}
			"1" => {
				let _ = windows_utilities::cpp_redist_open_website();
			}
			_ => {}
		};

		pause(msg_vc_2);

		if !windows_utilities::x86_cpp_redist_is_installed() {
			loop_until_valid_input(msg_vc_3, vec!["y"]);
		}
	}

	// Check whether the user wants to run the web installer or text installer
	let graphical = {
		let user_choice = pause(
			r#"Please choose which installer to run:
  0: Web-based installer (Try this first)
  1: Simple Text-based installer

> (Please type '0' or '1', then press ENTER)
"#,
		);

		match user_choice {
			Some(x) if x == "1" => false,
			_ => true,
		}
	};

	let config = InstallerConfig::new(&PathBuf::from("07th-mod_installer"), false);
	let mut extractor = archive_extractor::ArchiveExtractor::new();
	extractor.start_extraction(&config.sub_folder);

	loop {
		match extractor.poll_status() {
			ExtractionStatus::Started(Some(progress)) => {
				println!("Extraction is {}% complete", progress);
			}
			ExtractionStatus::Finished => {
				break;
			}
			ExtractionStatus::Error(err) => {
				println!("Error during extraction: {}", err);
				break;
			}
			_ => {}
		}
		std::thread::sleep(std::time::Duration::from_millis(500));
	}

	println!("Extraction Complete - Please wait while installer starts in your browser...");

	python_launcher::launch_python_script(&config, graphical)?.wait()
}

/// When called, changes the default panic handler to print useful information to the end user and
/// log it to the specified file.
/// The function will wait until the user presses "Enter" before terminating, so the user can read
/// the error message.
pub fn set_hook(log_filename: String) {
	std::panic::set_hook(Box::new(move |info: &PanicInfo| {
		// Console window might have been hidden previously - forcibly show it so user can read it
		windows_utilities::show_console_window();

		// Generate the short crash error message, and print it to stderr.
		// Will also be written to file later.
		let mut short_error_message = get_short_crash_message(info);
		eprintln!("{}", short_error_message);

		// Append backtrace to the short error message, then write it all to file
		let backtrace = format!("\n\n{:?}", Backtrace::new());
		short_error_message.push_str(&backtrace);

		// Write log file, then print where the log file was written
		if let Ok(()) = write_string_to_file(&log_filename, &short_error_message) {
			eprintln!(
				"The crash log has been written to:\n [{:}]\n",
				&windows_utilities::get_existing_file_normalized_path(&log_filename)
					.unwrap_or(log_filename.clone()),
			);
		} else {
			eprintln!("Error: Crash log could not be written!");
		}

		if let Err(error) = fallback_installer() {
			println!("Fallback Installer Error: {}", error);
		};

		pause("\nInstaller finished. Press any key to exit.");
	}));
}
