use crate::version;
use progress_streams::ProgressReader;
use std::path::{Path, PathBuf};
use std::sync::mpsc::{self, TryRecvError};
use std::sync::mpsc::{Receiver, Sender};
use std::{fs, thread};
use tar::Archive;
use xz2::read::XzDecoder;

enum ExtractionReport {
	InProgress { percentage: usize },
	Finished,
}

enum ExtractionStateMachine {
	NotStarted,
	Started(Receiver<Result<ExtractionReport, String>>),
	Finished,
}

pub enum ExtractionStatus {
	NotStarted,
	Started(Option<usize>),
	Finished,
	Error(String),
}

pub struct ArchiveExtractor {
	receiver: ExtractionStateMachine,
}

impl ArchiveExtractor {
	pub fn new() -> ArchiveExtractor {
		ArchiveExtractor {
			receiver: ExtractionStateMachine::NotStarted,
		}
	}

	pub fn start_extraction(&mut self, sub_folder_path: &Path) {
		match self.receiver {
			ExtractionStateMachine::NotStarted => {
				let (sender, receiver) = mpsc::channel::<Result<ExtractionReport, String>>();
				extract_archive_new_thread(sub_folder_path, sender);
				self.receiver = ExtractionStateMachine::Started(receiver);
			}
			_ => {}
		}
	}

	// This doesn't correctly handle the case where
	pub fn poll_status(&mut self) -> ExtractionStatus {
		match &mut self.receiver {
			ExtractionStateMachine::NotStarted => ExtractionStatus::NotStarted,
			ExtractionStateMachine::Started(receiver) => {
				// Check if an extraction update was received, nothing was received, or if there was an error
				let progress = match receiver.try_recv() {
					Ok(progress) => progress,
					Err(e) => match e {
						TryRecvError::Empty => return ExtractionStatus::Started(None),
						TryRecvError::Disconnected => {
							return ExtractionStatus::Error(
								"ArchiveExtractor channel disconnected unexpectedly".to_string(),
							)
						}
					},
				};

				// If there was an extraction error, report the error
				let progress = match progress {
					Ok(progress) => progress,
					Err(error_str) => return ExtractionStatus::Error(error_str),
				};

				// If extraction complete, report 100%, and advance to final state
				// Otherwise, return the percentage completion and stay in same state
				let percentage: usize = match progress {
					ExtractionReport::Finished => {
						self.receiver = ExtractionStateMachine::Finished;
						100
					}
					ExtractionReport::InProgress { percentage } => percentage,
				};

				ExtractionStatus::Started(Some(percentage))
			}
			ExtractionStateMachine::Finished => ExtractionStatus::Finished,
		}
	}
}

fn extract_archive_new_thread(
	sub_folder_path: &Path,
	progress_update: Sender<Result<ExtractionReport, String>>,
) {
	let mut path_copy = PathBuf::new();
	path_copy.push(sub_folder_path);
	thread::spawn(move || {
		println!("Spawning extraction thread");
		extract_archive(path_copy.as_path(), progress_update);
	});
}

fn extract_archive(
	sub_folder_path: &Path,
	progress_update: Sender<Result<ExtractionReport, String>>,
) {
	let saved_git_tag_path = sub_folder_path.join("installer_loader_extraction_lock.txt");

	// During compilation, include the installer archive in .tar.xz format
	//NOTE: The below file must be placed adjacent to this source file!
	//The archive should not contain any subfolders - one will be created automatically
	let archive_bytes = include_bytes!("install_data.tar.xz");

	let cwd = std::env::current_dir()
		.map(|path| path.display().to_string())
		.unwrap_or(String::from("(Can't get cwd)"));

	println!(
		"07th-Mod Installer Loader: Please wait. Extracting to [{}\\{}]",
		cwd,
		sub_folder_path.display()
	);

	// Pipe from the XzDecoder (.xz handler) to the Archive (.tar handler), then extract all files.
	let mut progress_counter = ProgressCounter::new(archive_bytes.len(), 1_000_000);
	let intermediate_reader = ProgressReader::new(&archive_bytes[..], |progress_bytes: usize| {
		if let Some(percentage) = progress_counter.update(progress_bytes) {
			println!("Extraction {}%", percentage);
			progress_update
				.send(Ok(ExtractionReport::InProgress { percentage }))
				.expect("Failed to send progress update - aborting extraction");
		}
	});

	let xz_reader = XzDecoder::new(intermediate_reader);

	if let Err(_e) = Archive::new(xz_reader).unpack(sub_folder_path) {
		let error_message = format!("Can't extract files. Make sure all installers are closed, you have enough disk space, and try again.\n\
Also check permissions to write to the folder (try moving installer to a different folder)\n\
[{}\\{}]\n\
You can also try 'Run as Administrator', but the installer may not work correctly.", cwd, sub_folder_path.display());
		progress_update
			.send(Err(error_message))
			.expect("Failed to send error progress update");
	} else {
		// Extraction was successful. Write extraction lock with installer version,
		// so we don't need to extract again unless installer's version changes
		write_extraction_lock(&saved_git_tag_path);
		progress_update
			.send(Ok(ExtractionReport::Finished))
			.expect("Failed to send progress update - aborting extraction");
		println!("Extraction Complete.");
	}
}

fn write_extraction_lock<P: AsRef<Path>>(saved_git_tag_path: P) {
	fs::write(saved_git_tag_path, version::travis_tag())
		.unwrap_or_else(|e| println!("Warning - Failed to write loader extraction lock: {:?}", e))
}

struct ProgressCounter {
	bytes_so_far: usize,
	last_printed: usize,
	// The last byte count when the bytes were printed
	data_length: usize,
	print_interval: usize,
}

impl ProgressCounter {
	pub fn new(data_length: usize, print_interval: usize) -> ProgressCounter {
		ProgressCounter {
			bytes_so_far: 0,
			last_printed: 0,
			data_length,
			print_interval,
		}
	}

	pub fn update(&mut self, read: usize) -> Option<usize> {
		self.bytes_so_far += read;

		if (self.bytes_so_far - self.last_printed > self.print_interval)
			|| (self.bytes_so_far == self.data_length)
		{
			self.last_printed = self.bytes_so_far;
			Some(self.bytes_so_far * 100 / self.data_length)
		} else {
			None
		}
	}
}
