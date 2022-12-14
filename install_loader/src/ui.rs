use glium::glutin::event::WindowEvent;
use imgui::*;
use tempfile::TempDir;

use crate::archive_extractor::{ArchiveExtractor, ExtractionStatus};
use crate::config::InstallerConfig;
use crate::process_runner::ProcessRunner;
use crate::{python_launcher, installer_webview};
use crate::support;
use crate::support::{AppBuilder, ApplicationGUI, NextFrameCommands};
use crate::version;
use crate::windows_utilities;
use std::path::PathBuf;

const MOUSE_ACTIVITY_TIMEOUT_SECS: u64 = 1;

pub struct TimeoutTimer {
	last_refresh: std::time::Instant,
	timeout: std::time::Duration,
}

impl TimeoutTimer {
	pub fn new(timeout: std::time::Duration) -> TimeoutTimer {
		TimeoutTimer {
			last_refresh: std::time::Instant::now(),
			timeout,
		}
	}

	pub fn refresh(&mut self) {
		self.last_refresh = std::time::Instant::now();
	}

	pub fn expired(&self) -> bool {
		return std::time::Instant::now().saturating_duration_since(self.last_refresh)
			> self.timeout;
	}
}

// Extension methods for imgui-rs
pub trait SimpleUI {
	fn simple_button(&self, label: &ImStr) -> bool;
	fn show_developer_tools(&self);
	fn text_red<T: AsRef<str>>(&self, text: T);
	fn text_yellow<T: AsRef<str>>(&self, text: T);
	fn build_ok_modal<T: AsRef<str>>(&self, modal_name: &ImStr, text: T);
}

impl<'ui> SimpleUI for Ui<'ui> {
	fn simple_button(&self, label: &ImStr) -> bool {
		self.button(label)
	}

	fn show_developer_tools(&self) {
		let mut show_demo_window = true;
		let mut show_metrics_window = true;
		self.show_demo_window(&mut show_demo_window);
		self.show_metrics_window(&mut show_metrics_window);
		self.show_default_style_editor();
	}

	fn text_red<T: AsRef<str>>(&self, text: T) {
		self.text_colored([1.0, 0.0, 0.0, 1.0], text);
	}

	fn text_yellow<T: AsRef<str>>(&self, text: T) {
		self.text_colored([1.0, 1.0, 0.0, 1.0], text);
	}

	fn build_ok_modal<T: AsRef<str>>(&self, modal_name: &ImStr, text: T) {
		self.popup_modal(modal_name).build(self, || {
			self.text(text);
			if self.button(im_str!("OK")) {
				self.close_current_popup();
			}
		});
	}
}

pub struct InstallStartedState {
	pub python_monitor: ProcessRunner,
	pub is_graphical: bool,
}

impl InstallStartedState {
	pub fn new(python_monitor: ProcessRunner, is_graphical: bool) -> InstallStartedState {
		InstallStartedState {
			python_monitor,
			is_graphical,
		}
	}
}

pub struct InstallFailedState {
	pub failure_reason: String,
	pub console_window_displayed: bool,
}

impl InstallFailedState {
	pub fn new(failure_reason: String) -> InstallFailedState {
		InstallFailedState {
			failure_reason,
			console_window_displayed: false,
		}
	}
}

pub struct ExtractingPythonState {
	pub extractor: ArchiveExtractor,
	pub progress_percentage: usize,
}

impl ExtractingPythonState {
	pub fn new() -> ExtractingPythonState {
		ExtractingPythonState {
			extractor: ArchiveExtractor::new(),
			progress_percentage: 0,
		}
	}
}

pub enum InstallerProgression {
	PreExtractionChecks,
	PreExtractionChecksFailed(String),
	ExtractingPython(ExtractingPythonState),
	UserNeedsCPPRedistributable,
	WaitingUserPickInstallType,
	InstallStarted(InstallStartedState),
	InstallFinished,
	InstallFailed(InstallFailedState),
	TempDirCleanupFailed(PathBuf),
}

pub struct InstallerState {
	// Installer state which depends on your progression through the installer
	pub progression: InstallerProgression,
	// If there is any installer state which doesn't depend on your current progression through the
	// installer, it should be put here.
}

struct UIState {
	window_size: [f32; 2],
	show_developer_tools: bool,
	show_console: bool,
	close_requested: bool,
	// If 'run' is false at the end of a frame, the program will exit
	run: bool,
	// A timer which times out if user hasn't moved their mouse for a while over this program
	mouse_activity_timer: TimeoutTimer,
	// True when this program has focus, false otherwise (not individual ImGUI windows)
	program_is_focused: bool,
	// True if the user ticked the Safe-Mode checkbox
	safe_mode_enabled: bool,
	// Set True to force app focus next frame
	focus_requested: bool,
	exit_modal_requested: bool,
}

impl UIState {
	pub fn new(window_size: [f32; 2]) -> UIState {
		UIState {
			window_size,
			show_developer_tools: false,
			show_console: false,
			close_requested: false,
			run: true,
			mouse_activity_timer: TimeoutTimer::new(std::time::Duration::from_secs(
				MOUSE_ACTIVITY_TIMEOUT_SECS,
			)),
			program_is_focused: true,
			safe_mode_enabled: false,
			focus_requested: true,
			exit_modal_requested: false,
		}
	}
}

struct InstallerGUI {
	// State which mainly relates to the presentation of the UI (ViewModel?)
	ui_state: UIState,
	// State which mainly relates to the execution of the installer
	state: InstallerState,
	// Configuration information which doesn't change during the course of the install is put here
	config: InstallerConfig,
	retry_using_temp_dir: bool,
}

impl InstallerGUI {
	pub fn init(
		window_size: [f32; 2],
		constants: InstallerConfig,
		initial_progression: InstallerProgression,
	) -> InstallerGUI {
		// Try to rename the old server-info.json file if it exists, to avoid reading
		// a server info file from a previous run of the installer
		let _ = std::fs::rename(&constants.server_info_path, &constants.server_info_old);

		InstallerGUI {
			ui_state: UIState::new(window_size),
			state: InstallerState {
				progression: initial_progression,
			},
			config: constants,
			retry_using_temp_dir: false,
		}
	}

	pub fn display_ui(&mut self, ui: &Ui) {
		ui.new_line();

		// Update the installer based on the extraction status
		self.extraction_update();

		// Handle when user attempts to close the program
		self.exit_handler(ui);

		// Main installer flow allowing user to progress through the installer
		self.display_main_installer_flow(ui);

		// Tools and information related to where the python part of the installer is extracted
		self.display_extraction_info(ui);

		ui.new_line();

		// Show the advanced tools section
		self.display_advanced_tools(ui);
	}

	// Monitor extraction and advance the installer state once extraction finished
	fn extraction_update(&mut self) {
		if let InstallerProgression::ExtractingPython(extraction_state) =
			&mut self.state.progression
		{
			match extraction_state.extractor.poll_status() {
				ExtractionStatus::NotStarted => extraction_state
					.extractor
					.start_extraction(&self.config.sub_folder),
				ExtractionStatus::Started(Some(progress)) => {
					extraction_state.progress_percentage = progress;
				}
				ExtractionStatus::Started(None) => {}
				ExtractionStatus::Finished => {
					self.state.progression = if windows_utilities::x86_cpp_redist_is_installed() {
						InstallerProgression::WaitingUserPickInstallType
					} else {
						InstallerProgression::UserNeedsCPPRedistributable
					};
				}
				ExtractionStatus::Error(error) => {
					println!("\n\nERROR: {}", error);
					self.state.progression =
						InstallerProgression::InstallFailed(InstallFailedState::new(error))
				}
			}
		}
	}

	// This modal prevents users accidentally terminating the install before it has finished
	// If python is extracting or installation has started, show a popup for user to confirm exit
	// In any other case, just let the user exit immediately
	fn exit_handler(&mut self, ui: &Ui) {
		let confirm_exit_modal_name = im_str!("Confirm Exit");
		if self.ui_state.close_requested {
			self.ui_state.close_requested = false;

			// This match statement decides which states require an exit confirmation
			match self.state.progression {
				InstallerProgression::PreExtractionChecks
				| InstallerProgression::PreExtractionChecksFailed(_)
				| InstallerProgression::ExtractingPython(_)
				| InstallerProgression::UserNeedsCPPRedistributable
				| InstallerProgression::WaitingUserPickInstallType
				| InstallerProgression::InstallFinished
				| InstallerProgression::TempDirCleanupFailed(_) => self.quit(),
				InstallerProgression::InstallStarted(_)
				| InstallerProgression::InstallFailed(_) => {
					self.ui_state.focus_requested = true;
					self.ui_state.exit_modal_requested = true;
				}
			}
		}

		// Work around popup modal being wrong size if popup occurs when window is not visible
		// by waiting until window visible is complete before opening the modal
		if !self.ui_state.focus_requested && self.ui_state.exit_modal_requested {
			self.ui_state.exit_modal_requested = false;
			ui.open_popup(confirm_exit_modal_name);
		}

		// Exit confirmation modal triggered by the above
		ui.popup_modal(confirm_exit_modal_name)
			.always_auto_resize(true)
			.build(ui, || {
				ui.text("Closing this window will terminate the installer!");
				if ui.button(im_str!("OK - Quit Installer")) {
					ui.close_current_popup();
					self.quit();
				}
				if ui.button(im_str!("Cancel")) {
					ui.close_current_popup();
				}
			});
	}

	/// Note: Should add a 'return' after every state change.
	/// The rust compiler will (rightfully) complain if you try to mutate the state after
	/// changing state, as it would no longer be correctly destructured/matched at that point.
	///
	/// Adding a return after changing state ensures that no other code can act on the now invalidly
	/// destructured state. On the next time the function is called, the match statement can then
	/// correctly destructure/match the new state.
	fn display_main_installer_flow(&mut self, ui: &Ui) {
		// Display parts of the UI which depend on the installer progression
		match &mut self.state.progression {
			InstallerProgression::PreExtractionChecks => {
				if windows_utilities::installer_is_in_temp_folder().unwrap_or(false) {
					self.state.progression = InstallerProgression::PreExtractionChecksFailed(
						String::from("WARNING: It appears you're running the installer from a temporary folder, which may cause the installer to fail.\n
Please download the installer to your Downloads or other known location, then run it from there.")
					);
					return;
				}

				self.state.progression =
					InstallerProgression::ExtractingPython(ExtractingPythonState::new());
				return;
			}
			InstallerProgression::PreExtractionChecksFailed(reason) => {
				ui.text_yellow(reason);
				if ui.simple_button(im_str!("Try to continue install anyway")) {
					self.state.progression =
						InstallerProgression::ExtractingPython(ExtractingPythonState::new());
					return;
				}
			}
			InstallerProgression::ExtractingPython(extraction_state) => {
				ui.text_yellow(im_str!("Please wait for extraction to finish..."));
				ProgressBar::new((extraction_state.progress_percentage as f32) / 100.0f32)
					.size([500.0, 24.0])
					.overlay_text(&im_str!(
						"{}% extracted",
						extraction_state.progress_percentage
					))
					.build(&ui);
			}
			InstallerProgression::UserNeedsCPPRedistributable => {
				let download_failure_modal_name = im_str!("Download Failure (C++ Redistributable)");
				let open_failure_modal_name = im_str!("Open Failure (C++ Redistributable)");
				let redist_missing_modal_name = im_str!("Redist Missing (C++ Redistributable)");

				ui.text_yellow(im_str!("Warning: You are missing the Visual C++ Redistributable (x86), needed to run the installer!"));
				ui.text_yellow(im_str!(
					"Please download and install it using the buttons below."
				));

				ui.new_line();
				if ui.simple_button(im_str!("Option 1: Download Directly")) {
					if let Err(_) = windows_utilities::cpp_redist_download_in_browser() {
						ui.open_popup(download_failure_modal_name);
					}
				}
				if ui.simple_button(im_str!(
					"Option 2: Visit C++ Redistributable Website (Choose [x86: vc_redist.x86.exe])"
				)) {
					if let Err(_) = windows_utilities::cpp_redist_open_website() {
						ui.open_popup(open_failure_modal_name);
					}
				}
				ui.text(im_str!(
					"If the redist install gets stuck for a long time, restart your computer and try again"
				));

				ui.new_line();
				if ui.simple_button(im_str!("Click here when you have finished installing")) {
					if windows_utilities::x86_cpp_redist_is_installed() {
						self.state.progression = InstallerProgression::WaitingUserPickInstallType;
						return;
					} else {
						ui.open_popup(redist_missing_modal_name);
					}
				}

				// Modal informing the user that the page/download couldn't be opened
				ui.build_ok_modal(
					download_failure_modal_name,
					im_str!("Couldn't download directly - please visit website to download"),
				);
				ui.build_ok_modal(
					open_failure_modal_name,
					im_str!("Couldn't open Microsoft website - please try to visit manually"),
				);

				// Exit confirmation modal triggered by the above
				ui.popup_modal(redist_missing_modal_name).build(ui, || {
					ui.text("You still seem to be missing the redist. Are you sure you want to continue?");
					if ui.button(im_str!("Yes, continue anyway")) {
						ui.close_current_popup();
						self.state.progression = InstallerProgression::WaitingUserPickInstallType;
						return;
					}
					if ui.button(im_str!("No, let me fix it")) {
						ui.close_current_popup();
					}
				});
			}
			InstallerProgression::WaitingUserPickInstallType => {
				ui.text_red(im_str!("Please click 'Run Installer'"));

				let install_button_clicked = ui.simple_button(im_str!("Run Installer"));
				ui.same_line_with_spacing(0., 20.);
				ui.checkbox(
					im_str!("Text-Mode Installer"),
					&mut self.ui_state.safe_mode_enabled,
				);
				if install_button_clicked {
					if let Err(e) = self.start_install(!self.ui_state.safe_mode_enabled) {
						println!("Failed to start install! {:?}", e)
					}
				}

				ui.new_line();

				ui.text_yellow(im_str!("If you have problems:"));
				ui.text_yellow(im_str!(" - try refreshing the webpage"));
				ui.text_yellow(im_str!(" - try 'Restart using temporary folder'"));
				ui.text_yellow(im_str!(" - try enabling 'Text-Mode Installer'"));

				if !self.config.is_retry
					&& ui.simple_button(im_str!("Restart using temporary folder"))
				{
					self.retry_using_temp_dir = true;
				}
			}
			InstallerProgression::InstallStarted(graphical_install) => {
				if graphical_install.is_graphical {
					ui.text(im_str!(
						"Please wait - Installer will launch in your web browser"
					));
					ui.text_yellow(im_str!("If you have problems:"));
					ui.text_yellow(im_str!(" - try refreshing the webpage"));
					ui.text_yellow(im_str!(" - try restarting this launcher, then try 'Restart using temporary folder'"));
					ui.text_yellow(im_str!(" - try restarting this launcher, then enable the 'Text-Mode Installer' option"));
				} else {
					ui.text_yellow(im_str!(
						"Console Installer Started - Please use the console window that just opened."
					));
				}

				if let Some(exit_status) =
					graphical_install.python_monitor.try_wait().unwrap_or(None)
				{
					if exit_status.success() {
						self.quit();
					} else {
						self.state.progression =
							InstallerProgression::InstallFailed(InstallFailedState::new(
								String::from("Python Installer Failed - See Console Window"),
							))
					};
					return;
				}
			}
			InstallerProgression::InstallFinished => {
				ui.text_yellow(im_str!(
					"The install is finished. Cleaning up...please wait"
				));
				self.ui_state.run = false;
			}
			InstallerProgression::InstallFailed(install_failed_state) => {
				ui.text_red(im_str!("The installation failed!"));
				ui.text_red(im_str!("[{}]", install_failed_state.failure_reason));
				if ui.simple_button(im_str!("Open 07th-mod Support Page")) {
					let _ = open::that("https://07th-mod.com/wiki/Installer/support/");
				}

				if !install_failed_state.console_window_displayed {
					windows_utilities::show_console_window();
					install_failed_state.console_window_displayed = true;
				}
			}
			InstallerProgression::TempDirCleanupFailed(last_temp_dir) => {
				ui.text_yellow(im_str!("Warning: Failed to delete extraction folder."));
				ui.text_yellow(im_str!("Please delete this folder manually to save disk space, or by running disk cleanup."));

				if ui.simple_button(im_str!("Open Extraction Folder")) {
					let _ = windows_utilities::system_open(last_temp_dir.clone());
				}
			}
		};
	}

	// Advanced tools used if something went wrong. Hidden by default unless you expand the header
	fn display_advanced_tools(&mut self, ui: &Ui) {
		// Advanced Tools Section
		if CollapsingHeader::new(im_str!("Advanced Tools")).build(&ui) {
			// Button which shows the python installer logs folder.
			// NOTE: the output of this launcher is currently not logged.
			if ui.button(im_str!("Show Installer Logs")) {
				let _ = windows_utilities::system_open(&self.config.logs_folder);
			}

			// Button which forces re-extraction
			match self.state.progression {
				InstallerProgression::WaitingUserPickInstallType
				| InstallerProgression::InstallFinished
				| InstallerProgression::InstallFailed(_) => {
					ui.same_line();
					if ui.simple_button(im_str!("Force Re-Extraction")) {
						self.state.progression =
							InstallerProgression::ExtractingPython(ExtractingPythonState::new());
					}
				}
				_ => {}
			}

			// Show windows' 'cmd' console
			if ui.checkbox(
				im_str!("Show Debug Console"),
				&mut self.ui_state.show_console,
			) {
				if self.ui_state.show_console {
					windows_utilities::show_console_window();
				} else {
					windows_utilities::hide_console_window();
				}
			}
			ui.same_line();

			// Show ImGUI Developer tools (and any other tools)
			ui.checkbox(
				im_str!("Show Developer Tools"),
				&mut self.ui_state.show_developer_tools,
			);
			ui.same_line();
		}
	}

	fn display_extraction_info(&mut self, ui: &Ui) {
		match self.state.progression {
			InstallerProgression::PreExtractionChecks
			| InstallerProgression::PreExtractionChecksFailed(_)
			| InstallerProgression::ExtractingPython(_)
			| InstallerProgression::TempDirCleanupFailed(_) => return,
			_ => {}
		}

		if self.config.is_retry {
			ui.text_wrapped(im_str!("NOTE: You are running the installer from a temp folder. Once you close this window, all partially completed downloads will be deleted."));
		}

		if ui.simple_button(im_str!("Open Extraction Folder:")) {
			let _ = windows_utilities::system_open(self.config.sub_folder.clone());
		}
		ui.same_line_with_spacing(0., 20.);
		ui.text_wrapped(&self.config.sub_folder_display);
	}



	// Start either the graphical or console install. Advances the installer progression to "InstallStarted"
	fn start_install(&mut self, is_graphical: bool) -> Result<(), Box<dyn std::error::Error>> {
		if !is_graphical {
			windows_utilities::show_console_window();
		}

		let launch_browser = false;

		let python_monitor = python_launcher::launch_python_script_all_options(
			&self.config,
			is_graphical,
			launch_browser,
		)?;

		// TODO: fallback to the below if above fails
		//let python_monitor = python_launcher::launch_python_script(&self.config, is_graphical)?;

		self.state.progression = InstallerProgression::InstallStarted(InstallStartedState::new(
			python_monitor,
			is_graphical,
		));

		// TODO: only launch installer once it has finished starting up
		// not sure of best way to do this - either write to a file once installer started up
		// or monitor console output for startup indicator string.

		// TODO: fall back to old method of launching browser if this fails
		match installer_webview::launch(&self.config) {
			Ok(_) => {}
			Err(e) => {
				println!("Failed to launch webview: {e}")
			}
		}

		Ok(())
	}

	// Close the UI and the installer thread
	fn quit(&mut self) {
		// Attempt to kill the python process, if the installer has already been started.
		// Even if killing fails, attempt to wait on the process.
		// This will make it obvious if something went wrong as the UI will (probably) hang,
		// so the user can close the program using task manager.
		if let InstallerProgression::InstallStarted(settings) = &mut self.state.progression {
			let _ = settings.python_monitor.kill_wait();
		}

		self.state.progression = InstallerProgression::InstallFinished;
	}

	// Power saving mode is determined by the following
	// - If the program has focus, power saving mode is disabled
	// - If no mouse activity is detected for MOUSE_ACTIVITY_TIMEOUT_SECS seconds,
	//   power saving mode is disabled
	// - Otherwise, power saving mode is enabled.
	fn should_save_power(&self) -> bool {
		!self.ui_state.program_is_focused && self.ui_state.mouse_activity_timer.expired()
	}
}

impl ApplicationGUI for InstallerGUI {
	fn run_ui(&mut self, ui: &mut Ui) -> NextFrameCommands {
		// Prevent high cpu/gpu usage due to unlimited framerate when window minimized on Windows
		// as well as generally reducing usage if the user isn't using the program
		if self.should_save_power() {
			std::thread::sleep(std::time::Duration::from_millis(100));
		}

		let unround_style = ui.push_style_var(StyleVar::WindowRounding(0.0));

		// Hide developer tools by default
		if self.ui_state.show_developer_tools {
			ui.show_developer_tools();
		}

		// Main window containing the installer
		Window::new(im_str!("07th-Mod Installer Launcher"))
			.position([0.0, 0.0], Condition::Always)
			.size(self.ui_state.window_size, Condition::Always)
			.no_decoration() //remove title bar etc. so it acts like the "Main" window of the program
			.build(ui, || {
				self.display_ui(ui);
			});

		unround_style.pop();

		let force_show_window = self.ui_state.focus_requested;
		self.ui_state.focus_requested = false;

		NextFrameCommands {
			run: self.ui_state.run,
			force_show_window,
			retry_using_tempdir: self.retry_using_temp_dir,
		}
	}

	fn handle_event(&mut self, event: &WindowEvent) {
		match event {
			WindowEvent::Focused(focused) => self.ui_state.program_is_focused = *focused,
			WindowEvent::CursorMoved { .. } => self.ui_state.mouse_activity_timer.refresh(),
			WindowEvent::CloseRequested => self.ui_state.close_requested = true,
			_ => {}
		}
	}
}

struct InstallerBuilder {
	temp_dir: Option<TempDir>,
}

impl InstallerBuilder {
	fn new() -> InstallerBuilder {
		InstallerBuilder { temp_dir: None }
	}
}

impl AppBuilder<InstallerGUI> for InstallerBuilder {
	fn window_size(&self) -> [f64; 2] {
		[1000., 500.]
	}

	fn window_name(&self) -> String {
		format!("07th-Mod Installer Launcher [{}]", version::travis_tag())
	}

	fn build(&self) -> InstallerGUI {
		let window_size = self.window_size();
		// if self.retry {
		InstallerGUI::init(
			[window_size[0] as f32, window_size[1] as f32],
			InstallerConfig::new(&PathBuf::from("07th-mod_installer"), false),
			InstallerProgression::PreExtractionChecks,
		)
	}

	fn build_cleanup_error(&self, failed_cleanup_path: PathBuf) -> InstallerGUI {
		let window_size = self.window_size();
		// if self.retry {
		InstallerGUI::init(
			[window_size[0] as f32, window_size[1] as f32],
			InstallerConfig::new(&PathBuf::from("07th-mod_installer"), false),
			InstallerProgression::TempDirCleanupFailed(failed_cleanup_path),
		)
	}

	fn build_retry(&mut self) -> Result<InstallerGUI, Box<dyn std::error::Error>> {
		// Note: Temp dir will attempt to delete itself once it goes out of scope, so make
		// sure to keep it in scope until you are finished with it
		let temp_dir = TempDir::new()?;

		let window_size = self.window_size();
		let retval = Ok(InstallerGUI::init(
			[window_size[0] as f32, window_size[1] as f32],
			InstallerConfig::new(&PathBuf::from(temp_dir.path()), false),
			InstallerProgression::PreExtractionChecks,
		));

		self.temp_dir = Some(temp_dir);

		retval
	}

	fn cleanup(&mut self) -> Option<PathBuf> {
		if let Some(temp_dir) = self.temp_dir.take() {
			// Give some time for any file handles to close
			std::thread::sleep(std::time::Duration::from_secs(2));

			let temp_dir_path = PathBuf::from(temp_dir.path());
			let printable_tempdir =
				windows_utilities::absolute_path_str(&temp_dir_path, "Couldn't display tempdir");

			if let Err(e) = temp_dir.close() {
				println!(
					"Failed to clean up Temp dir {} due to {}",
					printable_tempdir, e
				);
				return Some(temp_dir_path);
			}

			println!("Temp dir {} cleaned up successfully", printable_tempdir);
		}

		None
	}
}

pub fn ui_loop() {
	let builder = InstallerBuilder::new();
	let system = support::init(&builder.window_name(), builder.window_size());
	system.main_loop(builder);
}
