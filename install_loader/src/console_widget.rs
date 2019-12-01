use crate::ui::SimpleUI;
use imgui::*;
use std::collections::VecDeque;

enum MessageType {
	Info,
	Error,
	Input,
}

struct Message {
	message_type: MessageType,
	text: ImString,
}

impl Message {
	pub fn new(message_type: MessageType, text: ImString) -> Message {
		Message { message_type, text }
	}
}

pub struct ConsoleWidget {
	max_lines: usize,
	lines: VecDeque<Message>,
	input_buffer: ImString,
	viewport_size: [f32; 2],
}

impl ConsoleWidget {
	pub fn new(max_lines: usize, viewport_size: [f32; 2]) -> ConsoleWidget {
		ConsoleWidget {
			max_lines,
			lines: VecDeque::with_capacity(max_lines),
			input_buffer: ImString::with_capacity(1024),
			viewport_size,
		}
	}

	pub fn add_error(&mut self, text: String) {
		self.add_line_low_level(MessageType::Error, text);
	}

	pub fn add_input(&mut self, text: String) {
		self.add_line_low_level(MessageType::Input, text);
	}

	pub fn add_line(&mut self, text: String) {
		self.add_line_low_level(MessageType::Info, text);
	}

	fn add_line_low_level(&mut self, message_type: MessageType, text: String) {
		self.lines
			.push_back(Message::new(message_type, ImString::new(text)));
		if self.lines.len() > self.max_lines {
			self.lines.pop_front();
		}
	}

	// See the "ExampleAppConsole" example in https://github.com/ocornut/imgui/blob/master/imgui_demo.cpp
	// Accessible via the top menu->Examples->Console
	// NOTE: the returned string has no newline!
	pub fn show(&mut self, ui: &Ui) -> Option<String> {
		ChildWindow::new("child")
			.size(self.viewport_size)
			.border(true)
			.build(ui, || {
				for line in &self.lines {
					match line.message_type {
						MessageType::Info => ui.text(&line.text),
						MessageType::Error => ui.text_colored([1.0, 0.4, 0.4, 1.0], &line.text),
						MessageType::Input => ui.text_colored([1.0, 0.8, 0.6, 1.0], &line.text),
					};
				}

				// If scrolled all the way down, enable "autoscroll"
				if ui.scroll_y() >= ui.scroll_max_y() {
					ui.set_scroll_here_y_with_ratio(1.);
				}
			});

		// Text input
		ui.text("Console Input:");
		ui.same_line(0.);
		let input_width = ui.push_item_width(450.);
		let return_value = if ui
			.input_text(im_str!(""), &mut self.input_buffer)
			.enter_returns_true(true)
			.build()
		{
			Some(String::from(self.input_buffer.to_str()))
		} else {
			None
		};
		input_width.pop(ui);

		// When you press enter, focus is lost. The imGUI console example uses this code to
		// re-focus on the input textbox
		ui.set_item_default_focus();
		if return_value.is_some() {
			self.input_buffer.clear();
			ui.set_keyboard_focus_here(FocusedWidget::Previous);
		}

		ui.same_line(0.);
		if ui.simple_button(im_str!("Copy To Clipboard")) {
			ui.set_clipboard_text(&self.get_all_text());
		}

		return_value
	}

	fn get_all_text(&self) -> ImString {
		let total_text_length: usize = self
			.lines
			.iter()
			.map(|message| message.text.capacity())
			.sum();

		// Reserve the total number of characters + 1 for null terminator (not sure if that's required)
		let mut accumulator = ImString::with_capacity(total_text_length + 1);
		for message in self.lines.iter() {
			accumulator.push_str(message.text.to_str());
		}

		accumulator
	}
}
