use std::error::Error;
use std::ffi::OsStr;
use std::io::{BufRead, BufReader, Read, Write};
use std::path::Path;
use std::process::{Child, Command, Stdio};
use std::sync::mpsc;
use std::sync::mpsc::{Receiver, SendError, Sender, TryRecvError};
use std::thread;

// Note on using this on windows:
// If you attempt to type into the main console just after it starts can prevent stdin being
// captured properly (probably a windows issue?). After it's running, this problem doesn't seem to
// occur.
//
// For now, use the "stdin_has_terminated" function to detect if this happens and warn the user.

// Spawn a new thread for writing to the given readable
// The returned Send<String> allows you to write to stdin of the process
fn nonblock_writeable<W: Write + Send + 'static>(
	mut writeable: W,
	terminate_on_write_error: bool,
) -> (Sender<String>, Receiver<()>) {
	let (termination_check_sender, termination_check_receiver) = mpsc::channel::<()>();

	let (sender, receiver) = mpsc::channel::<String>();
	//let mut line_writer = LineWriter::new(writeable);

	// spawn a new thread to prevent blocking if writeable blocks
	thread::spawn(move || {
		let _ = termination_check_sender;
		loop {
			match receiver.recv() {
				Ok(line) => {
					println!("Thread received {}", line);
					if let Err(e) = writeable.write_all(line.as_bytes()) {
						println!(
							"write_all failed on writeable of data [{}] Error: [{}]",
							line, e
						);
						if terminate_on_write_error {
							return;
						}
					}
				}
				Err(e) => {
					println!(
						"recv() failed in nonblock_writeable() - UI thread exited? [{}]",
						e
					);
					return;
				}
			}
		}
	});

	println!("Stdin Thread terminated");

	(sender, termination_check_receiver)
}

// Spawn a new thread which reads lines from the given readable
// The returned Receiver<String> allows you to read out the lines in a non-blocking fashion
fn nonblock_readable<R: Read + Send + 'static>(readable: R) -> Receiver<String> {
	let mut buf_reader = BufReader::new(readable);
	// Channel to receive std on
	let (sender, receiver) = mpsc::channel::<String>();

	// spawn a new thread to continously read from stdout
	thread::spawn(move || loop {
		let mut s = String::new();
		if let Ok(_amt_read) = buf_reader.read_line(&mut s) {
			if let Err(e) = sender.send(s) {
				println!("capture_stdio thread error: {:?}", e);
				return;
			}
		} else {
			return;
		}
	});

	println!("Stdout Thread terminated");

	receiver
}

//spawn a thread to monitor the stdout and stderr
pub struct ProcessMonitor {
	child: Child,
	stdout: Receiver<String>,
	stderr: Receiver<String>,
	stdin: Sender<String>,
	stdin_termination_check: Receiver<()>,
}

impl ProcessMonitor {
	pub fn new<I, S>(
		full_executable_path: &Path,
		working_directory: &Path,
		arguments: I,
	) -> Result<ProcessMonitor, Box<dyn Error>>
	where
		I: IntoIterator<Item = S> + std::fmt::Debug,
		S: AsRef<OsStr>,
	{
		println!(
			"Starting {:?} in directory {:?}  with arguments [{:?}]",
			full_executable_path, working_directory, arguments
		);

		let mut child = Command::new(full_executable_path)
			.stdout(Stdio::piped())
			.stderr(Stdio::piped())
			.stdin(Stdio::piped())
			.current_dir(working_directory)
			.args(arguments)
			.spawn()?;

		if let Some(stdout) = child.stdout.take() {
			if let Some(stderr) = child.stderr.take() {
				if let Some(stdin) = child.stdin.take() {
					let (stdin, stdin_termination_check) = nonblock_writeable(stdin, true);

					Ok(ProcessMonitor {
						child,
						stdout: nonblock_readable(stdout),
						stderr: nonblock_readable(stderr),
						// Don't terminate if write to stdin fails - for this application, if user input is missed it's OK
						stdin,
						stdin_termination_check,
					})
				} else {
					Err("Failed to 'take' stdin")?
				}
			} else {
				Err("Failed to 'take' stderr")?
			}
		} else {
			Err("Failed to 'take' stdout")?
		}
	}

	// Try to read a line from stdout
	pub fn stdout_read_line(&mut self) -> Result<String, TryRecvError> {
		return self.stdout.try_recv();
	}

	// Try to read a line from stderr
	pub fn stderr_read_line(&mut self) -> Result<String, TryRecvError> {
		return self.stderr.try_recv();
	}

	// Writes raw text to stdin of the process. You should add a newline if you need it.
	pub fn stdin_write(&mut self, s: String) -> Result<(), SendError<String>> {
		return self.stdin.send(s);
	}

	pub fn stdin_write_add_nl(&mut self, s: &String) -> Result<(), SendError<String>> {
		return self.stdin_write(format!("{}\n", s));
	}

	// Kill the process and wait for it to terminate
	pub fn kill_wait(&mut self) -> Result<(), Box<dyn Error>> {
		self.child.kill()?;
		self.child.wait()?;
		Ok(())
	}

	pub fn stdin_has_terminated(&self) -> bool {
		match self.stdin_termination_check.try_recv() {
			Err(TryRecvError::Disconnected) => true,
			_ => false,
		}
	}
}
