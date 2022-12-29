#![warn(clippy::all)]

use crate::program_instance_lock::ProgramInstanceLock;
use crate::windows_message_box::{IconType, MessageBoxButtons, MessageBoxResult};
use clap::{App, Arg, ArgMatches};
use std::error::Error;
use std::path::PathBuf;

mod archive_extractor;
mod config;
mod panic_handler;
mod process_runner;
mod program_instance_lock;
mod python_launcher;
mod support; // This module is copied from the imgui-rs examples
mod ui;
mod version;
mod windows_dialog;
mod windows_message_box;
mod windows_utilities;
mod installer_webview;
mod resources;

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

fn fix_cwd() -> Result<PathBuf, Box<dyn Error>> {
	let exe_path = std::env::current_exe()?;
	let containing_path = exe_path.parent().ok_or("Invalid Path")?;
	std::env::set_current_dir(containing_path)?;
	Ok(containing_path.to_path_buf())
}

fn main() -> Result<(), Box<dyn Error>> {
	let no_launcher_gui = option_env!("NO_LAUNCHER_GUI").is_some();
	panic_handler::set_hook(String::from("07th-mod_crash.log"));

	//////////////////////////// Begin file chooser code ///////////////////////////////////////////
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

	//////////////////////////// Begin normal installer code ///////////////////////////////////////
	// Change current directory to .exe path, if current .exe path is known
	let old_cwd = std::env::current_dir();
	match fix_cwd() {
		Ok(new_cwd) => println!(
			"Successfully changed path from {:?} to {:?}",
			old_cwd, new_cwd
		),
		Err(e) => println!(
			"Couldn't fix exe path - cwd remains as [{:?}]. Error: [{}]",
			std::env::current_dir(),
			e
		),
	}

	// _maybe_job must be kept in scope for the remainder of the program!
	let (_maybe_job, register_job_result) = windows_utilities::new_job_kill_on_job_close();

	// Hide the console to make the installer less scary
	if !no_launcher_gui {
		windows_utilities::hide_console_window();
	}

	// _program_lock must be created after _maybe_job so that its drop() is called first
	let _program_lock = match ProgramInstanceLock::try_lock("07th-mod-installer-running.lock") {
		Ok(lock) => Some(lock),
		Err(e) => {
			let current_dir_string = std::env::current_dir()
				.map_or("Can't determine CWD".into(), |path| format!("{:?}", path));

			let user_choice = windows_message_box::create(
				"07th-Mod Installer Already Running",
				r#"Warning: The installer is already running. It's recommended that you close installer before starting it again.

Continue anyway?
(Please also make sure the current folder is writeable)"#,
				IconType::Info,
				MessageBoxButtons::YesNo,
			);

			match user_choice.unwrap_or(MessageBoxResult::Unknown) {
				MessageBoxResult::Yes => {}
				MessageBoxResult::No => return Ok(()),
				_ => {
					panic_handler::pause(&format!(
						r#"Failed to create lock file: {:?}

Please check the installer not already running, and folder [{}] is writeable"#,
						e, current_dir_string
					));
				}
			}

			None
		}
	};

	if no_launcher_gui {
		return panic_handler::fallback_installer_pause();
	} else if register_job_result.is_ok() {
		// This function blocks forever until the user quits the graphical installer
		ui::ui_loop();
	} else {
		// If job object not registered properly, use fallback/console installer
		// This ensures that everything is cleaned up properly as windows will automatically
		// clean up child processes when the console window is closed.
		println!("Warning: Failed to register job object! You're probably using Windows 7!");
		println!("Don't worry - you can use the terminal based installer below");
		return panic_handler::fallback_installer_pause();
	}

	Ok(())
}
