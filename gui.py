import queue
import threading
import time
from queue import Queue
from tkinter import *
import tkinter as tk
from tkinter.filedialog import askdirectory
from tkinter.scrolledtext import ScrolledText

#as per https://legacy.python.org/getit/mac/tcltk/ tkinter "Apple 8.5.9" should ship with mac 10.8,
#which is the minimum MAC version for higurashi. It has some bugs relating to inputing certain characters,
#but I don't think we will encounter them

"""
Apple 8.5.9

This release is included in Mac OS X 10.9, 10.8, and 10.7. As of this writing, there are at least two known issues with Tk 8.5.9 that are present in 
Apple 8.5.9 Tk but fixed in more recent upstream 8.5 releases. The more serious problem is an immediate crash in Tk when entering a composition character, 
like Option-u on a US keyboard. (This problem is documented as Tk bug 2907388.) There is also the more general problem of input manager support for 
composite characters (Tk bug 3205153) which has also been fixed in more recent Tcl/Tk 8.5 releases. You can avoid these problems by using a current 
python.org installer that links with ActiveTcl 8.5.15.0. This is an Aqua Cocoa Tk.
"""

#too hard to support tkinter 8.4, so better hope you hvae 8.5 on your computer
if False:
    default_padding = {"padx":3, "pady":3}
    frame_padding = {"padding": 3}
else:
    from tkinter.ttk import *
    default_padding = {"padx":3, "pady":3}
    frame_padding = {"padding": 3}

def make_two_line_button(root, upper_text, lower_text, image, callback):
    return make_button(root, "{}\n{}".format(upper_text, lower_text), image, callback)

# extra frame is required to provide padding between each button.
# if padding is applied directly to button then the inner contents of the button is padded not the outside.
def make_button(root, text, image, callback):
    frame = Frame(root, **frame_padding)
    but = Button(frame, image=image, command=callback)
    but.pack(side=LEFT)
    label = Label(frame,text=text)
    label.pack(side=LEFT)
    return frame

class ImageButtonList:
    def __init__(self, root, max_per_column):
        #self.window = tk.Toplevel()
        self.frame = Frame(root, **frame_padding)
        self.button_list = []
        self.max_per_column = max_per_column
        self.result = None

    def add_button_default(self, upper_text, lower_text, image, default_value):
        self.add_button(upper_text, lower_text, image, lambda: default_value)

    def add_button(self, upper_text, lower_text, image, callback):
        def do_callback_and_close_window_and_run_callback_with_result():
            self.result = callback()

        btn = make_two_line_button(self.frame, upper_text, lower_text, image, do_callback_and_close_window_and_run_callback_with_result)
        btn.grid(row=len(self.button_list)%self.max_per_column,
                 column = len(self.button_list)//self.max_per_column,
                 sticky="W")

        self.button_list.append(btn)

    def pack(self):
        return self.frame.pack(fill=BOTH, expand=1)

    def get_widget(self):
        return self.frame

class InstallStatusWidget:
    MSG_TYPE_OVERALL_PROGRESS = 0
    MSG_TYPE_SUBTASK_PROGRESS = 1
    MSG_TYPE_TEXT = 2

    def __init__(self, root):
        self.root = root

        self.outer_frame = Frame(root)
        self.label_overall = Label(self.outer_frame, text="Overall Progress")
        self.progress_overall = Progressbar(self.outer_frame, length=400)
        self.label_subtask = Label(self.outer_frame, text="SubTask Progress")
        self.progress_subtask = Progressbar(self.outer_frame, length=400)
        self.terminal = ScrolledText(self.outer_frame)  #behaves the same as the text widget, but has a scroll bar.

        self.label_overall.pack()
        self.progress_overall.pack()
        self.label_subtask.pack()
        self.progress_subtask.pack()
        self.terminal.pack(fill=BOTH, expand=1, pady=20)
        self.outer_frame.pack()

        #hack to make terminal readonly while still letting us freeely insert text and let user copy from text
        #See: https://stackoverflow.com/questions/3842155/is-there-a-way-to-make-the-tkinter-text-widget-read-only
        self.terminal.bind("<Key>", lambda e: "break")
        self.terminal.insert(END, "terminal output goes here")

        self.notification_queue = Queue(maxsize=100000)
        self.queue_full_error = False
        root.after(200, self.progress_receiver)

    #set progress where value is a integer from 0-100
    #call this from other thread
    def threadsafe_set_overall_progress(self, value):
        self.try_put_in_queue((InstallStatusWidget.MSG_TYPE_OVERALL_PROGRESS, value))

    # call this from other thread
    def threadsafe_set_subtask_progress(self, value):
        self.try_put_in_queue((InstallStatusWidget.MSG_TYPE_SUBTASK_PROGRESS, value))

    # call this from other thread
    def threadsafe_set_text(self, text):
        self.try_put_in_queue((InstallStatusWidget.MSG_TYPE_TEXT, text))

    def try_put_in_queue(self, item):
        try:
            self.notification_queue.put_nowait(item)
        except queue.Full:
            if not self.queue_full_error:
                self.queue_full_error = True
                print("WARNING: Install status message queue is full (possibly GUI was closed but console left open)")

    def progress_receiver(self):
        #process up to 100 message or until empty
        for _ in range(0, 100):
            try:
                msg_type, msg_data = self.notification_queue.get_nowait()
            except queue.Empty:
                root.after(200, self.progress_receiver)
                return

            if msg_type == InstallStatusWidget.MSG_TYPE_OVERALL_PROGRESS:
                self.progress_overall["value"] = msg_data
            elif msg_type == InstallStatusWidget.MSG_TYPE_SUBTASK_PROGRESS:
                self.progress_subtask["value"] = msg_data
            elif msg_type == InstallStatusWidget.MSG_TYPE_TEXT:
                self.terminal.insert(END, msg_data)
            else:
                print("Error - invalid data received in progress receiver")

        root.after(200, self.progress_receiver)

# Forward  button - if not set, defaults to a disabled button
# Backward button - for first page, is disabled. For all other pages, automatically moves you back to the previous page by destroying the widget
class InstallWizard2:
    def __init__(self, root):
        #outer frame which holds everything
        self.outer_frame = Frame(root)

        #inner frame which is only used to make sure inner contents is centered vertically and horizontally
        self.content_frame_wrapper = Frame(self.outer_frame)
        self.content_frame_wrapper.pack(fill=X, expand=1)

        #inner frame holding all frames defined in get_new_frame_and_hide_old_frame(). Has a line drawn around it.
        self.content_frame = Frame(self.content_frame_wrapper, relief=GROOVE, padding=15)
        self.content_frame.pack()

        self.page_name_frame = Frame(self.content_frame)
        self.page_name_frame.pack()

        self.buttons_frame = Frame(self.outer_frame)
        self.back_button = Button(self.buttons_frame, text="Back", state=DISABLED, command=self.back_button_callback)
        self.forward_button = Button(self.buttons_frame, text="Next", state=NORMAL, command=self.next_button_callback)
        self.back_button.pack(side=LEFT)
        self.forward_button.pack(side=RIGHT)
        self.buttons_frame.pack(side=BOTTOM)

        self.page_frames = []
        self.page_texts = []
        self.forward_callbacks = [] #actions to take when forward button is pressed
        self.back_callbacks = []    #actions to take when back button is pressed
        self.disable_back = []
        self.page_count = 0

    #execute the user defined callback to generate the new page
    def next_button_callback(self):
        if self.forward_callbacks[self.page_count-1]:
            self.forward_callbacks[self.page_count-1]()

    #excute the user defined callback, then go back a page
    def back_button_callback(self):
        print("back callback is ", self.back_callbacks[self.page_count-1])
        if self.back_callbacks[self.page_count-1]:
            self.back_callbacks[self.page_count-1]()
        self.back()

    # use `hide_buttons` to hide the back/next buttons. You must implement your own buttons to go forward and backward in this case
    # which call `get_new_frame_and_hide_old_frame` or `back` respectively.
    def get_new_frame_and_hide_old_frame(self, text, forward_callback=None, backward_callback=None, disable_back=False):
        # Create a new frame, increment page count
        page_frame = Frame(self.content_frame)
        page_frame.pack()
        self.page_frames.append(page_frame)
        self.page_count += 1

        # Maintain a list of callbacks for each page, so they don't need to be re-entered when going "back" a page
        self.forward_callbacks.append(forward_callback)
        self.back_callbacks.append(backward_callback)
        self.disable_back.append(disable_back)

        # Disable back button on first page
        if self.page_count == 1 or disable_back:
            self.back_button.config(state=DISABLED)
        else:
            self.back_button.config(state=NORMAL)

        # Disable forward button if foward callback is not defined
        if forward_callback is None:
            self.forward_button.pack_forget() #config(state=DISABLED)
        else:
            self.forward_button.pack(side=RIGHT) #config(state=NORMAL)

        # Hide the previous frame
        page_index = self.page_count-1
        if page_index > 0:
            print("forgetting", page_index-1)
            self.page_frames[page_index-1].pack_forget()
            self.page_texts[page_index - 1].pack_forget()

        # Update the text
        page_name = Label(self.page_name_frame, text=text)
        page_name.pack(side=LEFT)
        self.page_texts.append(page_name)

        return page_frame

    def back(self):
        #delete curent page, and update page count
        page_index = self.page_count-1
        print("deleting index", page_index)
        self.page_frames[page_index].destroy()
        self.page_frames.pop()
        self.page_texts[page_index].destroy()
        self.page_texts.pop()
        self.forward_callbacks.pop()
        self.back_callbacks.pop()
        self.disable_back.pop()
        self.page_count -= 1

        page_index = self.page_count - 1

        # Disable back button on first page
        if self.page_count == 1 or self.disable_back[page_index]:
            self.back_button.config(state=DISABLED)
        else:
            self.back_button.config(state=NORMAL)

        # Disable forward button if foward callback is not defined
        if self.forward_callbacks[page_index] is None:
            self.forward_button.pack_forget()  # config(state=DISABLED)
        else:
            self.forward_button.pack(side=RIGHT)  # config(state=NORMAL)

        #pack the previous frame, so it is shown again
        self.page_frames[page_index].pack()
        self.page_texts[page_index].pack()
        print("Page count is", self.page_count)

    def pack(self):
        self.outer_frame.pack(fill=BOTH, expand=1)

#settings common to both installers
class BaseInstallerSettings:
    def __init__(self, wizard):
        self.use_ipv6 = False
        self.install_path = None
        self.mod_type = None
        self.wiz = wizard

    def make_settings_confirmation_widget(self, root):
        frame = Frame(root)

        #TODO: fix this later with two column layout
        for attr, value in self.__dict__.items():
            if attr != "wiz":
                setting_text = Label(root, text="{:20}: {}".format(attr, value), justify=LEFT)
                setting_text.pack(fill=BOTH, expand=1)

        return frame


class HigurashiInstaller(BaseInstallerSettings):
    def __init__(self, wizard):
        BaseInstallerSettings.__init__(self, wizard)
        #TODO: put higurashi specific settings here

    def advance_to_choose_game_folder_higurashi(self):
        name_path_tuples = [("Higurashi Ep. 1", r"c:\program files\steam\higurashi\one\two\three"),
                           ("Higurashi Ep. 2", r"c:\program files\steam\higurashi"),
                           ("Higurashi Ep. 3", r"c:\program files\steam\higurashi"),
                           ("Higurashi Ep. 4", r"c:\program files\steam\higurashi"),
                           ("Higurashi Ep. 5", r"c:\program files\steam\higurashi"),
                           ("Higurashi Ep. 6", r"c:\program files\steam\higurashi"),
                           ("Higurashi Ep. 7", r"c:\program files\steam\higurashi"),
                           ("Higurashi Ep. 8", r"c:\program files\steam\higurashi"),
                           ("Higurashi Ep. 9", r"c:\program files\steam\higurashi"), ]

        frame = self.wiz.get_new_frame_and_hide_old_frame("Choose which Episode to install:", forward_callback=None, backward_callback=lambda: print("advance_to_choose_game_folder_umineko"))

        btn_list = ImageButtonList(frame, max_per_column=6)

        def set_path_and_advance(path):
            if path:
                self.install_path = path
            else:
                #need to do verificartion of path here! copy from higurashiinstaller.py
                self.install_path = askdirectory()

            if self.install_path != "":
                self.advance_to_choose_mod_type_higurashi()

        for name, path in name_path_tuples:
            btn_list.add_button(name, path, img, lambda: set_path_and_advance(path))

        btn_list.add_button("Higurashi Ep. C", r"Can't Find Path - Choose Manually", img, lambda: set_path_and_advance(None))
        btn_list.pack()


    def advance_to_choose_mod_type_higurashi(self):
        frame = self.wiz.get_new_frame_and_hide_old_frame("Choose which mod to install:", backward_callback=lambda: print("choose mod type back"))

        def set_mod_type_and_advance(mod_type):
            self.mod_type = mod_type
            self.advance_to_confirmation_page()

        btn_list = ImageButtonList(frame, max_per_column=6)
        btn_list.add_button("Full Patch", r"Patch Graphics, Voices, etc.", img, lambda:set_mod_type_and_advance("FULL"))
        btn_list.add_button("ADV Mode", r"Use ADV mode (see wiki for description)", img, lambda:set_mod_type_and_advance("ADV"))
        btn_list.add_button("Voice Only", r"Only Patch Voices", img, lambda:set_mod_type_and_advance("VOICE_ONLY"))
        btn_list.pack()


    def advance_to_confirmation_page(self):
        frame = self.wiz.get_new_frame_and_hide_old_frame("Please confirm your settings, then click next to begin the installation")
        install_button = Button(frame, text="Start Install!", command=self.advance_to_install_status_page)
        settings_confirmation_widget = self.make_settings_confirmation_widget(frame)
        settings_confirmation_widget.pack()
        install_button.pack()


    def advance_to_install_status_page(self):
        frame = self.wiz.get_new_frame_and_hide_old_frame("Please wait for the installer to finish", disable_back=True)
        install_widget = InstallStatusWidget(frame)

        thread = HigurashiInstallerThread(install_widget, config=self)
        thread.start()

class HigurashiInstallerThread(threading.Thread):
   def __init__(self, install_widget, config):
        threading.Thread.__init__(self, daemon=True)
        #only either read the variables, or call functions prepended with 'threadsafe_" from these objects
        #do not attempt to call other functions, or write to these objects, as they're not properly thread safe
        self.install_widget = install_widget
        self.config = config

   def run(self):
       for i in range(0, 10000):
           self.install_widget.threadsafe_set_overall_progress(i / 100)
           time.sleep(.01)


class InstallerGUI:
    def __init__(self, configList):
        self.root = Tk()
        self.wiz = InstallWizard2(self.root)
        self.wiz.pack()

    #installer GUI needs to ask, then filter:
    # - WHICH game family (Umineko or Higurashi) [mods:family] field
    # - WHICH mod they want to install (Himatsubushi, Console Arcs, Umineko Chiru) [mods:name] field

    # - display
    #   - a list of autodetected game paths with the above criteria (should only ever be one mod option which satisfies the above criteria)
    #   - the option to TRY to select a custom path (which still has to be validated )

    # - let user choose the submod they want to install, if there is more than one submod

    def mainloop(self):
        self.root.mainloop()

#
#
# root = Tk()
#
# img = PhotoImage(file="earth.gif").subsample(4)
#
# root.minsize(800, 500)
#
# wiz = InstallWizard2(root)
#
# def advance_to_intro_page():
#     frame = wiz.get_new_frame_and_hide_old_frame("Please choose which game you want to install",
#                                                  forward_callback=None, #disable forward callback
#                                                  backward_callback=lambda: print("advance intro page(never called)"))
#     button_higurashi = Button(frame, text="Install Higurashi Mod", command=higu_installer.advance_to_choose_game_folder_higurashi)
#     button_umineko = Button(frame, text="Install Umineko Mod", command=advance_to_choose_game_folder_umineko)
#     button_higurashi.pack(**default_padding)
#     button_umineko.pack(**default_padding)
#
# def advance_to_choose_game_folder_umineko():
#     frame = wiz.get_new_frame_and_hide_old_frame("Umineko placeholder")
#
# higu_installer = HigurashiInstaller(wiz)
#
#
# advance_to_intro_page()
#
# wiz.pack()
#
#
# root.mainloop()
#
# print("finished")
