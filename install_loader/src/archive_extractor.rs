use progress_streams::ProgressReader;
use std::path::{Path, PathBuf};
use std::sync::mpsc;
use std::sync::mpsc::{Receiver, Sender};
use std::{fs, thread};
use tar::Archive;
use xz2::read::XzDecoder;

enum ExtractionStatusInternal {
	NotStarted,
	Started(Receiver<Result<usize, &'static str>>),
	Finished,
}

pub enum ExtractionStatus {
	NotStarted,
	Started(Option<usize>),
	Finished,
	Error(&'static str),
}

pub struct ArchiveExtractor {
	receiver: ExtractionStatusInternal,
}

impl ArchiveExtractor {
	pub fn new() -> ArchiveExtractor {
		ArchiveExtractor {
			receiver: ExtractionStatusInternal::NotStarted,
		}
	}

	pub fn start_extraction(&mut self, sub_folder_path: &Path) {
		match self.receiver {
			ExtractionStatusInternal::NotStarted => {
				let (sender, receiver) = mpsc::channel::<Result<usize, &str>>();
				extract_archive_new_thread(sub_folder_path, sender);
				self.receiver = ExtractionStatusInternal::Started(receiver);
			}
			_ => {}
		}
	}

	// This doesn't correctly handle the case where
	pub fn poll_status(&mut self) -> ExtractionStatus {
		match &mut self.receiver {
			ExtractionStatusInternal::NotStarted => ExtractionStatus::NotStarted,
			ExtractionStatusInternal::Started(receiver) => {
				if let Ok(progress) = receiver.try_recv() {
					match progress {
						Ok(progress) => {
							if progress >= 100 {
								self.receiver = ExtractionStatusInternal::Finished
							}
							ExtractionStatus::Started(Some(progress))
						}
						Err(error_str) => ExtractionStatus::Error(error_str),
					}
				} else {
					// Extraction is started but no additional progress to tell
					ExtractionStatus::Started(None)
				}
			}
			ExtractionStatusInternal::Finished => ExtractionStatus::Finished,
		}
	}
}

fn extraction_required<P: AsRef<Path>>(saved_git_tag_path: P) -> bool {
	// try to load the last extracted installer's git tag
	let saved_git_tag = match fs::read_to_string(saved_git_tag_path) {
		Ok(val) => val,
		Err(_e) => return true,
	};

	println!(
		"[07th-Mod Installer Loader] Saved: {} -> New: {}",
		saved_git_tag,
		env!("TRAVIS_TAG")
	);

	return env!("TRAVIS_TAG").trim() != saved_git_tag.trim();
}

fn extract_archive_new_thread(
	sub_folder_path: &Path,
	progress_update: Sender<Result<usize, &'static str>>,
) {
	let mut path_copy = PathBuf::new();
	path_copy.push(sub_folder_path);
	thread::spawn(move || {
		println!("Spawning extraction thread");
		extract_archive(path_copy.as_path(), progress_update);
	});
}

fn extract_archive(sub_folder_path: &Path, progress_update: Sender<Result<usize, &str>>) {
	let saved_git_tag_path = sub_folder_path.join("installer_loader_extraction_lock.txt");

	if extraction_required(&saved_git_tag_path) {
		// During compilation, include the installer archive in .tar.xz format
		//NOTE: The below file must be placed adjacent to this source file!
		//The archive should not contain any subfolders - one will be created automatically
		let archive_bytes = include_bytes!("install_data.tar.xz");

		// Pipe from the XzDecoder (.xz handler) to the Archive (.tar handler), then extract all files.
		println!(
			"[07th-Mod Installer Loader] Please wait. Extracting to [{}]",
			sub_folder_path.display()
		);

		let mut progress_counter = ProgressCounter::new(archive_bytes.len(), 1_000_000);
		let intermediate_reader =
			ProgressReader::new(&archive_bytes[..], |progress_bytes: usize| {
				if let Some(percentage) = progress_counter.update(progress_bytes) {
					progress_update
						.send(Ok(percentage))
						.expect("Failed to send progress update - aborting extraction");
				}
			});

		let xz_reader = XzDecoder::new(intermediate_reader);

		if let Err(_e) = Archive::new(xz_reader).unpack(sub_folder_path) {
			progress_update
				.send(Err(
					"Can't extract files. Make sure all installers are closed, you have enough disk space, and try again.",
				))
				.expect("Failed to send error progress update");
		} else {
			// Extraction was successful. Write extraction lock with installer version,
			// so we don't need to extract again unless installer's version changes
			write_extraction_lock(&saved_git_tag_path);
		}
	} else {
		progress_update
			.send(Ok(100))
			.expect("Failed to send progress update - aborting extraction");
	}
}

fn write_extraction_lock<P: AsRef<Path>>(saved_git_tag_path: P) {
	fs::write(saved_git_tag_path, env!("TRAVIS_TAG"))
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
