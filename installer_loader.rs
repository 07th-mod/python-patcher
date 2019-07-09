use std::fs::File;
use std::io::prelude::*;

macro_rules! seven_zip_path { () => {"7za.exe"} }
macro_rules! archive_path { () => {"07th-Mod.Installer.Windows.7z"} }

fn write_bytes_to_file(data : &[u8], file_path : &str) {
    let mut file = File::create(file_path).expect(&format!("Failed to create {}", file_path));
    file.write_all(data).expect(&format!("Failed to save data to {}", file_path));
}

//NOTE: Any files included using include_bytes! must be placed adjacent to this source file!
fn main() -> std::io::Result<()> {
    // Copy out the 7z .exe from this binary
    println!("[07th-Mod Installer Loader] Copying 7z exe from binary");
    write_bytes_to_file(include_bytes!(seven_zip_path!()), seven_zip_path!());

    // Copy out the installer archive from this binary
    println!("[07th-Mod Installer Loader] Copying installer archive from binary");
    write_bytes_to_file(include_bytes!(archive_path!()), archive_path!());

    // Extract the installer files, and wait for extraction to finish
    println!("[07th-Mod Installer Loader] Extracting install files");
    let mut seven_zip_handle = std::process::Command::new("7za")
        .args(&["x", archive_path!(), "-aoa"])
        .spawn()
        .expect("loader: failed to start extracting archive");
    seven_zip_handle.wait().expect("loader: failed to wait on extracting archive");

    // Start the installer batch file, and wait for installer to finish
    println!("[07th-Mod Installer Loader] Running installer");
    let mut installer_handle= std::process::Command::new("07th-Mod_Installer_Windows/install.bat")
        .spawn()
        .expect("loader: failed to run batch file");
    installer_handle.wait().expect("loader: failed to wait on install to finish");

    println!("[07th-Mod Installer Loader] Exited");

    Ok(())
}
