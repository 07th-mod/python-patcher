extern crate winapi;

use regex::Regex;
use std::error::Error;
use std::ffi::OsStr;
use std::fmt::Debug;
use std::path::Path;
use std::process;
use std::process::Command;
use std::ptr;

// https://stackoverflow.com/questions/29763647/how-to-make-a-program-that-does-not-display-the-console-window
// https://msdn.microsoft.com/en-us/library/windows/desktop/ms633548%28v=vs.85%29.aspx
// cmd_show should be one of SW_HIDE, SW_SHOW etc. from winapi::um::winuser
fn set_console_window_display_mode(cmd_show: winapi::ctypes::c_int) {
	let window = unsafe { winapi::um::wincon::GetConsoleWindow() };
	if window != ptr::null_mut() {
		unsafe {
			winapi::um::winuser::ShowWindow(window, cmd_show);
		}
	}
}

pub fn hide_console_window() {
	set_console_window_display_mode(winapi::um::winuser::SW_HIDE);
}

pub fn show_console_window() {
	set_console_window_display_mode(winapi::um::winuser::SW_SHOW);
}

/***
Tries to open a given path using the system 'open' function
The path can be a on-disk folder or a URL
NOTE: this function call does not block! (uses subprocess.Popen)
NOTE: paths won't open properly on windows if they contain backslashes. Set 'normalizePath' to handle this problem.
:param path: the path to show
:return: true if successful, false otherwise

This function might be Windows specific. Move to a different file if it becomes cross-platform
***/
pub(crate) fn system_open<S>(path: S) -> Result<process::Child, Box<dyn Error>>
where
	S: AsRef<OsStr> + Debug,
{
	let normalized_path = get_existing_file_normalized_path(&path)?;

	println!(
		"Path [{:?}] has been intepreted as [{:?}]",
		&path, normalized_path
	);

	Ok(Command::new("explorer").arg(normalized_path).spawn()?)
}

/// Gets normalized path of an EXISTING file. This function will fail if the path/file doesn't exist
pub fn get_existing_file_normalized_path<S>(path: S) -> Result<String, Box<dyn Error>>
where
	S: AsRef<OsStr> + Debug,
{
	let canonical_path = Path::new(&path).canonicalize()?;
	let canonical_path = canonical_path
		.to_str()
		.ok_or("Can't determine canonical path")?;

	// Path returned from canonicalize() has UNC prefix like "\\?\", which is removed below
	Ok(Regex::new(r"^\\\\\?\\")?
		.replace(canonical_path, "")
		.to_string())
}
