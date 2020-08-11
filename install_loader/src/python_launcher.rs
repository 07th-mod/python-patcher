use std::error::Error;
use std::ffi::OsStr;

use crate::config::InstallerConfig;
use crate::process_runner::ProcessRunner;

pub fn launch_python_script(
	config: &InstallerConfig,
	graphical: bool,
) -> Result<ProcessRunner, Box<dyn Error>> {
	let script_name = OsStr::new(if graphical {
		"main.py"
	} else {
		"cli_interactive.py"
	});

	let mut args = vec![OsStr::new("-u"), OsStr::new("-E"), script_name];

	let maybe_path = std::env::current_exe();
	match maybe_path.as_ref() {
		Ok(path) => args.push(path.as_os_str()),
		Err(err) => {
			println!("WARNING: couldn't determine own .exe path! File chooser may not work properly.\nError:{:?}", err);
		}
	}

	ProcessRunner::new(&config.python_path, config.sub_folder, &args)
}
