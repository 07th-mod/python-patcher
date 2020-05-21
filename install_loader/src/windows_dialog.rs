use std::error::Error;
use std::fmt::Display;
use std::ptr;
use widestring::U16CString;
use winapi::shared::guiddef::IID;
use winapi::shared::minwindef::DWORD;
use winapi::shared::winerror::{ERROR_CANCELLED, HRESULT, HRESULT_FROM_WIN32};
use winapi::um::combaseapi::{CoCreateInstance, CoInitializeEx};
use winapi::um::shobjidl::IFileDialog;
use winapi::um::shobjidl_core::IModalWindow;
use winapi::um::shobjidl_core::IShellItem;
use winapi::um::shtypes::COMDLG_FILTERSPEC;
use winapi::um::unknwnbase::LPUNKNOWN;
use winapi::um::winnt::LPWSTR;

#[derive(Debug, Clone)]
struct WinHRESULTFailed;

impl Display for WinHRESULTFailed {
	fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
		write!(f, "HRESULT was an error")
	}
}

impl Error for WinHRESULTFailed {
	fn source(&self) -> Option<&(dyn Error + 'static)> {
		None
	}
}

#[derive(Debug, Clone)]
struct UserCancelled;

impl Display for UserCancelled {
	fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
		write!(f, "User cancelled dialog")
	}
}

impl Error for UserCancelled {
	fn source(&self) -> Option<&(dyn Error + 'static)> {
		None
	}
}

// Helper trait to convert HRESULT into a Result type
trait HRESULTAsResult {
	fn as_result(&self) -> Result<(), WinHRESULTFailed>;
	fn into_result(self) -> Result<(), WinHRESULTFailed>;
}

impl HRESULTAsResult for HRESULT {
	fn as_result(&self) -> Result<(), WinHRESULTFailed> {
		(*self).into_result()
	}

	fn into_result(self) -> Result<(), WinHRESULTFailed> {
		if !winapi::shared::winerror::SUCCEEDED(self) {
			return Err(WinHRESULTFailed);
		}
		Ok(())
	}
}

// The values below are copied from
// https://github.com/Raymai97/WinFTW.rs/blob/0bc88a01574e354956962e8ba49fd8ab8957691f/src/ole/native.rs
#[allow(non_upper_case_globals)]
pub const IID_IFileDialog: IID = IID {
	Data1: 0x42f85136,
	Data2: 0xdb7e,
	Data3: 0x439c,
	Data4: [0x85, 0xf1, 0xe4, 0x07, 0x5d, 0x13, 0x5f, 0xc8],
};

/// Shows a Windows File Open Dialog and returns the path chosen by the user.
///
///
/// # Failures
///
/// This function will return an error if one of the winapi functions fails, or if
/// there is a a conversion error converting to/from windows wide strings, or if the user cancelled
///
/// # Arguments
///
/// ## filters
///
/// filter is the raw filter that is used by the windows api. Specify as filters separated by `;`
/// Example filters: vec![
///		("text files", "*.txt"),
///		("text and pdf", "*.txt;*.pdf"),
///		("main c file", "main.c"),
///	]
/// Filters are described in more detail here:
/// https://docs.microsoft.com/en-us/windows/win32/api/shobjidl_core/nf-shobjidl_core-ifiledialog-setfiletypes
///
/// # Return Value
///
/// - Returns the path the user chose on success.
/// - If the user cancelled, returns `UserCancelled` error
/// - If a call resulted in a error HRESULT, returns `WinHRESULTFailed`
/// - Can also return an error on wide string conversion like `NulError` and `FromUtf16Error`
///
/// # Notes
/// Code is based on the following, but updated for new winapi:
/// https://github.com/Raymai97/WinFTW.rs/blob/0bc88a01574e354956962e8ba49fd8ab8957691f/src/dlg/filedlg.rs
/// Also based on this winapi example: https://docs.microsoft.com/en-us/windows/win32/learnwin32/example--the-open-dialog-box
/// ```
pub fn dialog_open(filters: Vec<(&str, &str)>) -> Result<String, Box<dyn Error>> {
	// Convert rust string into wide strings
	let mut filter_as_wstring: Vec<(U16CString, U16CString)> = Vec::new();
	for (description, filter) in filters {
		filter_as_wstring.push((
			U16CString::from_str(description)?,
			U16CString::from_str(filter)?,
		))
	}

	// Create an array of COMDLG_FILTERSPEC which holds struct of pointers to the above wide strings
	let rg_spec: Vec<COMDLG_FILTERSPEC> = (&filter_as_wstring)
		.into_iter()
		.map(|(description, filter)| COMDLG_FILTERSPEC {
			pszName: description.as_ptr(),
			pszSpec: filter.as_ptr(),
		})
		.collect();

	unsafe {
		// Initialize the COM library
		CoInitializeEx(
			ptr::null_mut(),
			winapi::um::objbase::COINIT_APARTMENTTHREADED,
		)
		.into_result()?;

		// Create the instance of the FileOpenDialog
		let mut p_file_dialog: *mut IFileDialog = ptr::null_mut();

		CoCreateInstance(
			&winapi::um::shobjidl_core::CLSID_FileOpenDialog,
			ptr::null_mut() as LPUNKNOWN,
			winapi::um::combaseapi::CLSCTX_INPROC,
			&IID_IFileDialog,
			&mut p_file_dialog as *mut _ as *mut _,
		)
		.into_result()?;

		// Get ref so can call their functions
		let file_dialog = &*p_file_dialog;

		file_dialog.SetFileTypes(rg_spec.len() as DWORD, rg_spec.as_ptr());

		// Show the dialog (Show() is defined on IModalWindow, so need cast)
		let show_hresult = (file_dialog as &IModalWindow).Show(ptr::null_mut());

		// Check if the user cancelled the dialog
		if show_hresult == HRESULT_FROM_WIN32(ERROR_CANCELLED) {
			Err(UserCancelled)?;
		}

		// Check for any other error
		show_hresult.into_result()?;

		// Get the result of the fileOpen dialogue
		let mut p_shell_item = ptr::null_mut() as *mut IShellItem;
		file_dialog.GetResult(&mut p_shell_item).into_result()?;

		// Retrieve the chosen path as a LPWSTR
		let mut path_as_wide_string = ptr::null_mut() as LPWSTR;
		(&*p_shell_item)
			.GetDisplayName(
				winapi::um::shobjidl_core::SIGDN_FILESYSPATH,
				&mut path_as_wide_string,
			)
			.into_result()?;

		// Convert windows LPWSTR to rust string
		let path = U16CString::from_ptr_str(path_as_wide_string).to_string()?;

		// Uninitialize the COM library
		winapi::um::combaseapi::CoUninitialize();

		Ok(path)
	}
}
