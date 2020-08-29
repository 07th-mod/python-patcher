use fs2::FileExt;
use std::error::Error;
use std::fs::File;
use std::path::Path;

pub(crate) struct ProgramInstanceLock<P: AsRef<Path>> {
	path: P,
	file: Option<File>,
}

impl<P: AsRef<Path>> ProgramInstanceLock<P> {
	pub(crate) fn try_lock(lock_file_path: P) -> Result<ProgramInstanceLock<P>, Box<dyn Error>> {
		let lock_file = File::create(&lock_file_path)?;
		lock_file.try_lock_exclusive()?;
		Ok(ProgramInstanceLock {
			path: lock_file_path,
			file: Some(lock_file),
		})
	}
}

impl<P: AsRef<Path>> Drop for ProgramInstanceLock<P> {
	fn drop(&mut self) {
		// Unlock the file
		self.file.as_ref().map(|file| {
			file.unlock().unwrap_or_else(|e| {
				println!("Failed to unlock lock file: {}", e);
			})
		});

		// Release the file handle by setting self.file to None
		self.file = None;

		// Delete the file
		std::fs::remove_file(&self.path).unwrap_or_else(|e| {
			println!("Failed to remove installer lock file {}", e);
		});
	}
}
