use std::iter::once;
use std::ptr::null_mut;

use winapi::um::winuser;
use winapi::um::winuser::{
	MessageBoxW, MB_ABORTRETRYIGNORE, MB_CANCELTRYCONTINUE, MB_ICONERROR, MB_ICONINFORMATION,
	MB_OK, MB_OKCANCEL, MB_RETRYCANCEL, MB_SYSTEMMODAL, MB_YESNO, MB_YESNOCANCEL,
};

#[allow(dead_code)]
#[derive(Debug, Copy, Clone)]
pub enum IconType {
	Error,
	Info,
	None,
}

#[allow(dead_code)]
#[derive(Debug, Copy, Clone)]
pub enum MessageBoxResult {
	Abort,
	Cancel,
	Continue,
	Ignore,
	No,
	Ok,
	Retry,
	TryAgain,
	Yes,
	Unknown,
}

#[allow(dead_code)]
#[derive(Debug, Copy, Clone)]
pub enum MessageBoxButtons {
	AbortRetryIgnore,
	CancelTryContinue,
	OK,
	OKCancel,
	RetryCancel,
	YesNo,
	YesNoCancel,
}

// Modified version of https://github.com/bekker/msgbox-rs, but added other types of messageboxes,
// and checking which button the user pressed.
pub fn create(
	title: &str,
	content: &str,
	icon_type: IconType,
	buttons: MessageBoxButtons,
) -> std::result::Result<MessageBoxResult, ()> {
	let lp_text: Vec<u16> = content.encode_utf16().chain(once(0)).collect();
	let lp_caption: Vec<u16> = title.encode_utf16().chain(once(0)).collect();

	let window_type = match icon_type {
		IconType::Error => MB_ICONERROR | MB_SYSTEMMODAL,
		IconType::Info => MB_ICONINFORMATION | MB_SYSTEMMODAL,
		IconType::None => MB_SYSTEMMODAL,
	};

	let window_type = window_type
		| match buttons {
			MessageBoxButtons::AbortRetryIgnore => MB_ABORTRETRYIGNORE,
			MessageBoxButtons::CancelTryContinue => MB_CANCELTRYCONTINUE,
			MessageBoxButtons::OK => MB_OK,
			MessageBoxButtons::OKCancel => MB_OKCANCEL,
			MessageBoxButtons::RetryCancel => MB_RETRYCANCEL,
			MessageBoxButtons::YesNo => MB_YESNO,
			MessageBoxButtons::YesNoCancel => MB_YESNOCANCEL,
		};

	unsafe {
		/*
		 * https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-messageboxw#return-value
		 * If the return value is zero, creating message box has failed
		 */
		match MessageBoxW(
			null_mut(),
			lp_text.as_ptr(),
			lp_caption.as_ptr(),
			window_type,
		) {
			0 => Err(()),
			value => Ok(match value {
				winuser::IDABORT => MessageBoxResult::Abort,
				winuser::IDCANCEL => MessageBoxResult::Cancel,
				winuser::IDCONTINUE => MessageBoxResult::Continue,
				winuser::IDIGNORE => MessageBoxResult::Ignore,
				winuser::IDNO => MessageBoxResult::No,
				winuser::IDOK => MessageBoxResult::Ok,
				winuser::IDRETRY => MessageBoxResult::Retry,
				winuser::IDTRYAGAIN => MessageBoxResult::TryAgain,
				winuser::IDYES => MessageBoxResult::Yes,
				_ => MessageBoxResult::Unknown,
			}),
		}
	}
}
