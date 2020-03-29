use std::error::Error;
use std::ffi::OsStr;
use std::path::Path;
use std::process::{Child, Command};

//spawn a thread to monitor the stdout and stderr
pub struct ProcessRunner {
	child: Child,
}

impl ProcessRunner {
	pub fn new<I, S>(
		full_executable_path: &Path,
		working_directory: &Path,
		arguments: I,
	) -> Result<ProcessRunner, Box<dyn Error>>
	where
		I: IntoIterator<Item = S> + std::fmt::Debug,
		S: AsRef<OsStr>,
	{
		println!(
			"Starting {:?} in directory {:?}  with arguments [{:?}]",
			full_executable_path, working_directory, arguments
		);

		let child = Command::new(full_executable_path)
			.current_dir(working_directory)
			.args(arguments)
			.spawn()?;

		Ok(ProcessRunner { child })
	}

	// Kill the process and wait for it to terminate
	pub fn kill_wait(&mut self) -> Result<(), Box<dyn Error>> {
		self.child.kill()?;
		self.child.wait()?;
		Ok(())
	}

	pub fn wait(&mut self) -> Result<(), Box<dyn Error>> {
		self.child.wait()?;
		Ok(())
	}

	pub fn task_has_failed_nonblocking(&mut self) -> bool {
		match self.child.try_wait() {
			Ok(Some(exit_status)) => !exit_status.success(),
			_ => false,
		}
	}
}
