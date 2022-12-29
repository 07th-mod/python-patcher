use std::io;
#[cfg(windows)] use winres::WindowsResource;

fn main() -> io::Result<()> {

    // At compile time this includes the .ico file in the executable so it has the correct icon.
    #[cfg(windows)] {
        WindowsResource::new()
            .set_icon("src/resources/icon.ico")
            .compile()?;
    }
    Ok(())
}