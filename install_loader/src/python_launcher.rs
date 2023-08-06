use std::error::Error;
use std::ffi::OsStr;

use crate::config::{InstallerConfig, LaunchType};
use crate::process_runner::ProcessRunner;

pub fn launch_python_script(
	config: &InstallerConfig,
	launch_type: LaunchType,
) -> Result<ProcessRunner, Box<dyn Error>> {
	let mut args = vec!["-u", "-E"];

	match launch_type {
		LaunchType::TextMode => args.push("cli_interactive.py"),
		LaunchType::Browser => args.push("main.py"),
		LaunchType::WebView => {
			args.push("main.py");
			args.push("--no-launch-browser");
		}
	};

	let mut args : Vec<&OsStr> = args.iter().map(|arg| OsStr::new(arg)).collect();

	let maybe_path = std::env::current_exe();
	match maybe_path.as_ref() {
		Ok(path) => {
			args.push(OsStr::new("--launcher-path"));
			args.push(path.as_os_str());
		},
		Err(err) => {
			println!("WARNING: couldn't determine own .exe path! File chooser may not work properly.\nError:{:?}", err);
		}
	}

	ProcessRunner::new(&config.python_path, &config.sub_folder, &args)
}
