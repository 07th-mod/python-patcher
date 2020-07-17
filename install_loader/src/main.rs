#![warn(clippy::all)]

use clap::{App, Arg, ArgMatches};
use std::error::Error;
use std::path::{Path, PathBuf};

mod archive_extractor;
mod panic_handler;
mod process_runner;
mod support; // This module is copied from the imgui-rs examples
mod ui;
mod version;
mod windows_dialog;
mod windows_utilities;

// Please define these as paths relative to the current directory
struct InstallerConfig {
	sub_folder: &'static Path,
	logs_folder: PathBuf,
	python_path: PathBuf,
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

fn handle_open_command(matches: &ArgMatches) -> Result<(), Box<dyn Error>> {
	// Expect filters to be given as description1, filter1, description2, filter2
	let filters: Vec<(&str, &str)> = match matches.values_of("filters") {
		Some(filter_args) if filter_args.len() > 0 => filter_args
			.collect::<Vec<&str>>()
			.chunks_exact(2)
			.map(|chunk| (chunk[0], chunk[1]))
			.collect(),
		// If a zero length filter is supplied then the dialog will have no file ext dropdown
		// Supplying a default filter ensures a file ext dropdown is shown.
		_ => vec![("All Files", "*.*")],
	};

	match windows_dialog::dialog_open(filters) {
		Ok(path) => {
			print!("{}", path);
			Ok(())
		}
		Err(error) if error.is::<windows_dialog::UserCancelled>() => Ok(()),
		Err(error) => Err(error),
	}
}

fn main() -> Result<(), Box<dyn Error>> {
	panic_handler::set_hook(String::from("07th-mod_crash.log"));

	// _maybe_job must be kept in scope for the remainder of the program!
	let (_maybe_job, register_job_result) = windows_utilities::new_job_kill_on_job_close();

	let open_about_msg = r#"Shows an open dialog and:
- if user selected a path, writes the chosen path to stdout, returns 0
- if user cancelled, writes nothing to stdout, returns 0
- if an errror occurred, writes the error to stdout, returns 1"#;

	let open_help_msg = r#"Sets the description and filters to use - defaults to all files.
For example, open "text and pdf" "*.txt;*.pdf" "main c file" "main.c""#;

	let matches = App::new("07th-mod Installer Loader")
		.version(version::travis_tag())
		.about("Loader which extracts and starts the Python-based 07th-mod Installer.")
		.subcommand(
			App::new("open")
				.about(open_about_msg)
				.arg(Arg::with_name("filters").help(open_help_msg).multiple(true)),
		)
		.get_matches();

	if let Some(matches) = matches.subcommand_matches("open") {
		return handle_open_command(matches);
	}

	if register_job_result.is_ok() {
		// Hide the console for windows users to make the installer less scary
		// the console window can un-hidden later if necessary
		windows_utilities::hide_console_window();

		// This function blocks forever until the user quits the graphical installer
		ui::ui_loop();
	} else {
		// If job object not registered properly, use fallback/console installer
		// This ensures that everything is cleaned up properly as windows will automatically
		// clean up child processes when the console window is closed.
		println!("Warning: Failed to register job object! You're probably using Windows 7!");
		println!("Don't worry - you can use the terminal based installer below");
		if let Err(error) = panic_handler::fallback_installer() {
			println!("Fallback Installer has failed with: {:?}", error);
			println!(
				"Please help us by reporting the error and submitting the crash log
 - on our Discord server: https://discord.gg/pf5VhF9
 - or, as a Github issue: https://github.com/07th-mod/python-patcher/issues"
			);
			panic_handler::pause("Press ENTER to quit the installer");
		}
	}

	Ok(())
}
