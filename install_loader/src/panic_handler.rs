use backtrace::Backtrace;
use std::fs::File;
use std::io;
use std::io::{BufRead, Write};
use std::panic::PanicInfo;

use crate::windows_utilities;

/// This function blocks until the user to presses enter in the console
fn pause(msg: &str) {
	// We want the cursor to stay at the end of the line, so we print without a newline and flush manually.
	let mut stderr = io::stderr();
	write!(stderr, "{}", msg).unwrap();
	stderr.flush().unwrap();

	// Block until user presses Enter
	let stdin = io::stdin();
	for _line in stdin.lock().lines() {
		break;
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
		r#"The 07th-mod Installer has crashed! :(

Please help us by reporting the error and submitting the crash log
 - on our Discord server: https://discord.gg/pf5VhF9
 - or, as a Github issue: https://github.com/07th-mod/python-patcher/issues

-----------Error Summary-----------
"#,
	);

	// Print installer version
	expl.push_str(&format!("Installer Version: [{}]\n", env!("TRAVIS_TAG")));

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
				"\nThe crash log has been written to:\n [{:}]\n",
				&windows_utilities::get_existing_file_normalized_path(&log_filename)
					.unwrap_or(log_filename.clone()),
			);
		} else {
			eprintln!("Error: Crash log could not be written!");
		}

		// Don't immediately show backtrace as it may confuse the user - wait till they press enter
		pause("Press ENTER to show detailed crash information...");
		eprintln!("{}", backtrace);
		eprintln!("\nTIP: Press CTRL-A, CTRL-C to copy this text, then paste it to us on Discord");

		// Prevent window from closing immediately (so user can read error message)
		pause("\nPress ENTER to close this window...");
	}));
}
