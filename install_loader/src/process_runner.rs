use crate::windows_utilities;
use std::error::Error;
use std::ffi::OsStr;
use std::os::windows::io::AsRawHandle;
use std::path::Path;
use std::process::{Child, Command};
use win32job::Job;

//spawn a thread to monitor the stdout and stderr
pub struct ProcessRunner {
	child: Child,
	job: Option<Job>,
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

		let (job, register_job_result) =
			windows_utilities::new_job_kill_on_job_close_id(child.as_raw_handle());

		if let Err(e) = register_job_result {
			println!("Failed to create job object: {}", e);
		}

		Ok(ProcessRunner { child, job })
	}

	// Kill the process and wait for it to terminate
	pub fn kill_wait(&mut self) -> Result<(), Box<dyn Error>> {
		self.child.kill()?;
		self.child.wait()?;
		self.job = None;
		Ok(())
	}

	pub fn wait(&mut self) -> Result<(), Box<dyn Error>> {
		self.child.wait()?;
		Ok(())
	}

	pub fn try_wait(&mut self) -> std::io::Result<Option<std::process::ExitStatus>> {
		self.child.try_wait()
	}
}
