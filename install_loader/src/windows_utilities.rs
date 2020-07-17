extern crate open;
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

/// This function checks for the 32-bit version of the Visual C++ Redist.
/// On 32 bit systems it checks the "System32" folder, and on 64-bit systems, it checks the "SysWOW64" folder.
/// See here for details: https://www.quora.com/What-is-the-difference-between-system32-and-SysWow64
/// It checks these folders for "ucrtbase.dll" and "vcruntime140.dll" (you probably only need to check for "ucrtbase.dll" though)
///
/// The Visual C++ Redist is required to run python, see: https://docs.python.org/3/using/windows.html#the-embeddable-package
pub fn x86_cpp_redist_is_installed() -> bool {
	// Need to handle if windows is not on the C: drive - use environment variable to determine location
	let windows_folder = std::env::var("windir").unwrap_or(String::from(r"C:\Windows"));

	let windows_dll_32bit_folder = match os_info::get().bitness() {
		os_info::Bitness::X32 => "System32", //32-bit windows stores 32-bit dlls in the System32 folder
		os_info::Bitness::X64 => "SysWOW64", //64-bit windows stores 32-bit dlls in the SysWOW64 folder
		_ => "SysWOW64", // I don't think this can happen on Windows - just assume 64-bit
	};

	for dll_filename in vec!["vcruntime140.dll", "ucrtbase.dll"] {
		let dll_path = Path::new(&windows_folder)
			.join(windows_dll_32bit_folder)
			.join(dll_filename);

		if !dll_path.exists() {
			println!("CPP Redist Check failed - can't find: [{:?}]", dll_path);
			return false;
		}
	}

	return true;
}

pub fn cpp_redist_download_in_browser() -> std::io::Result<std::process::ExitStatus> {
	open::that("https://aka.ms/vs/16/release/vc_redist.x86.exe")
}

pub fn cpp_redist_open_website() -> std::io::Result<std::process::ExitStatus> {
	open::that(
		"https://support.microsoft.com/en-au/help/2977003/the-latest-supported-visual-c-download",
	)
}

pub fn installer_is_in_temp_folder() -> Result<bool, Box<dyn Error>> {
	let app_data = format!("{}\\AppData", std::env::var("USERPROFILE")?);
	Ok(std::env::current_exe()?.starts_with(app_data.as_str()))
}

fn try_set_kill_on_job_close(job: &mut win32job::Job) -> Result<(), Box<dyn Error>> {
	let mut info = job.query_extended_limit_info()?;
	info.limit_kill_on_job_close();
	job.set_extended_limit_info(&mut info)?;
	job.assign_current_process()?;

	Ok(())
}

// Note: The program will be terminated once the returned Job object goes out of scope!
// Eg. to keep the program running, you must keep the Job object in scope.
//
// This follows the example at https://github.com/ohadravid/win32job-rs
// It forces any created sub processes to exit when the main process exits
// This includes the python process, and processes called from python like aria2c and 7z
// Also see: https://stackoverflow.com/questions/23434842/python-how-to-kill-child-processes-when-parent-dies/23587108
// On Windows 7, creating the job  seems to fail - see workaround at end of main()
pub fn new_job_kill_on_job_close() -> (Option<win32job::Job>, Result<(), Box<dyn Error>>) {
	// first, try to create a job object
	let mut job = match win32job::Job::create() {
		Ok(job) => job,
		Err(e) => return (None, Err(e.into())),
	};

	// if the job creation was successful, try to set it such that all processes are
	// killed when the job object goes out of scope (including *this* process!).
	match try_set_kill_on_job_close(&mut job) {
		Ok(_) => (Some(job), Ok(())),
		Err(e) => (Some(job), Err(e.into())),
	}
}
