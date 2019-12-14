extern crate kernel32;
extern crate user32;
extern crate winapi;

use std::error::Error;
use std::ffi::OsStr;
use std::fmt::Debug;
use std::path::Path;
use std::process::{Child, Command};
use std::ptr;

// https://stackoverflow.com/questions/29763647/how-to-make-a-program-that-does-not-display-the-console-window
// https://msdn.microsoft.com/en-us/library/windows/desktop/ms633548%28v=vs.85%29.aspx
// cmd_show should be one of SW_HIDE, SW_SHOW etc. from winapi::um::winuser
fn set_console_window_display_mode(cmd_show: winapi::ctypes::c_int) {
	let window = unsafe { kernel32::GetConsoleWindow() };
	if window != ptr::null_mut() {
		unsafe {
			user32::ShowWindow(window, cmd_show);
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
pub(crate) fn system_open<S: AsRef<OsStr> + Debug>(path: S) -> Result<Child, Box<dyn Error>> {
	let canonical_path = Path::new(&path).canonicalize()?;
	let re = regex::Regex::new(r"^\\\\\?\\").unwrap();
	let fixed_path = re.replace(canonical_path.to_str().unwrap(), "");

	println!(
		"Path [{:?}] has been intepreted as [{:?}]",
		path, fixed_path
	);
	let child = Command::new("explorer")
		.arg(fixed_path.to_string())
		.spawn()?;
	Ok(child)
}
