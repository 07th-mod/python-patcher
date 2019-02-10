import os
import threading

try:
    import queue
    from tkinter import *
    from tkinter.ttk import *
    from tkinter.scrolledtext import ScrolledText
except ImportError:
    import Queue as queue
    from Tkinter import *
    from ttk import *
    import Tkinter as tkinter
    import tkFileDialog as filedialog
    import tkMessageBox as messagebox

from gameScanner import SubModConfig

#as per https://legacy.python.org/getit/mac/tcltk/ tkinter "Apple 8.5.9" should ship with mac 10.8,
#which is the minimum MAC version for higurashi. It has some bugs relating to inputing certain characters,
#but I don't think we will encounter them
from gameScanner import scanForFullInstallConfigs, subModCompatibleWithPath

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

    def add_button(self, upper_text, lower_text, image, callback, *callback_args, **callback_kwargs):
        """

        :param upper_text: Text displayed on the first line, on the right of the button
        :param lower_text: Text displayed on the second line, on the right of the button
        :param image:      The image object displayed inside the button. REMEMBER TO KEEP A REFERENCE TO THE IMAGE OR IT WON'T BE SHOWN.
        :param callback:   The callback to be called when the button is pressed
        :param callback_args:    arguments to the callback function
        :param callback_kwargs:  keyword arguments to the callback function (eg a=5, b=7)
        :return: None
        """
        btn = make_two_line_button(self.frame, upper_text, lower_text, image, lambda: callback(*callback_args, **callback_kwargs))
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

        #hack to make terminal readonly while still letting us freeely insert text and let user copy from text
        #See: https://stackoverflow.com/questions/3842155/is-there-a-way-to-make-the-tkinter-text-widget-read-only
        self.terminal.bind("<Key>", lambda e: "break")
        self.terminal.insert(END, "terminal output goes here")

        self.notification_queue = queue.Queue(maxsize=100000)
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
                self.root.after(200, self.progress_receiver)
                return

            if msg_type == InstallStatusWidget.MSG_TYPE_OVERALL_PROGRESS:
                self.progress_overall["value"] = msg_data
            elif msg_type == InstallStatusWidget.MSG_TYPE_SUBTASK_PROGRESS:
                self.progress_subtask["value"] = msg_data
            elif msg_type == InstallStatusWidget.MSG_TYPE_TEXT:
                self.terminal.insert(END, msg_data)
            else:
                print("Error - invalid data received in progress receiver")

        self.root.after(200, self.progress_receiver)

    def pack(self):
        self.outer_frame.pack()

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

    def pack(self):
        self.outer_frame.pack(fill=BOTH, expand=1)


class InstallerGUI:
    def __init__(self, allSubModConfigs):
        """

        :param allSubModList: a list of SubModConfigs derived from the json file (should contain ALL submods in the file)
        """
        self.root = Tk()
        self.root.minsize(800, 500)
        self.wiz = InstallWizard2(self.root)
        self.wiz.pack()

        #Note: MUST keep a handle to the image, otherwise it will be garbage collected!!!
        self.img = PhotoImage(file="earth.gif")

        self.allSubModConfigs = allSubModConfigs
        self.showModList()

    def showModList(self):
        frame = self.wiz.get_new_frame_and_hide_old_frame("Choose which mod you want to install")
        btn_list = ImageButtonList(frame, max_per_column=3)

        for modName in SubModConfig.getUniqueModNamesInSubModList(self.allSubModConfigs):
            btn_list.add_button(modName, "", self.img, self.setModNameAndAdvance, modName)

        btn_list.pack()

    def setModNameAndAdvance(self, modName):
        # type: (str) -> None
        print("User Chose Mod: [{}]".format(modName))

        frame = self.wiz.get_new_frame_and_hide_old_frame("Choose which mod option you want to install")
        btn_list = ImageButtonList(frame, max_per_column=6)
        for subMod in [subMod for subMod in self.allSubModConfigs if subMod.modName == modName]:
            btn_list.add_button(subMod.subModName, "", self.img, self.setSubModAndAdvance, subMod)

        btn_list.pack()

    def setSubModAndAdvance(self, subMod):
        # type: (SubModConfig) -> None
        def askGameExeAndValidate():
            #this creates the default option, which allows you to select all identifiers and any extras specified here.
            extensionList = ["com.apple.application"] + subMod.identifiers
            fileList = [("Game Executable", x) for x in extensionList]
            fileList.append(("Any In Game Folder", "*.*"))

            gameExecutablePath = filedialog.askopenfilename(filetypes=fileList)
            if gameExecutablePath:
                installDir = os.path.normpath(os.path.join(gameExecutablePath, os.pardir))

                fullInstallConfigs = scanForFullInstallConfigs(subModConfigList=[subMod], possiblePaths=[installDir])
                if fullInstallConfigs:
                    print("Path Ok: ", installDir)
                    self.confirmationPage(fullInstallConfigs[0])
                else:
                    print("Path INVALID:", installDir)
                    messagebox.showerror("Error", "Can't install the mod to the path\n" + installDir)

        #do search over all possible install locations that the selected submod can be installed.
        fullInstallConfigs = scanForFullInstallConfigs([subMod])

        #show "no games autodetected - please choose manually" if none exist

        frame = self.wiz.get_new_frame_and_hide_old_frame("Choose which installation to install the mod to")
        btn_list = ImageButtonList(frame, max_per_column=6)
        for fullConfig in fullInstallConfigs:
            btn_list.add_button("Install Mod To:",
                                fullConfig.installPath,
                                self.img,
                                self.confirmationPage,
                                fullConfig)
        btn_list.pack()

        but = Button(frame, text="Find Game Exe Manually", command=askGameExeAndValidate)
        but.pack()

        label = Label(frame, text="HINT - Find any of these files:\n - " + "\n - ".join(subMod.identifiers))
        label.pack()

    def confirmationPage(self, fullInstallSettings):
        frame = self.wiz.get_new_frame_and_hide_old_frame("Please confirm your settings: ")

        #TODO: fix this later with two column layout
        for attr, value in fullInstallSettings.__dict__.items():
            if attr != "wiz":
                setting_text = Label(frame, text="{:20}: {}".format(attr, value), justify=LEFT)
                setting_text.pack(fill=BOTH, expand=1)

        start_install_button = Button(frame, text="Start Install!", command=lambda: self.advance_to_install_status_page(fullInstallSettings))
        start_install_button.pack()

    def advance_to_install_status_page(self, fullInstallSettings):
        #TODO: these imports are here to avoid circular imports. Fix properly later.
        import higurashiInstaller
        import uminekoInstaller

        frame = self.wiz.get_new_frame_and_hide_old_frame("Please wait for the installer to finish", disable_back=True)
        installStatusWidget = InstallStatusWidget(frame)
        installStatusWidget.pack()

        installerFunction = {
            "higurashi" : higurashiInstaller.main,
            "umineko" : uminekoInstaller.mainUmineko
        }.get(fullInstallSettings.subModConfig.family, None)

        if not installerFunction:
            messagebox.showerror("Error - Unknown Game Family",
                                 "I don't know how to install [{}] family of games. Please notify 07th-mod developers.")
            return

        t = threading.Thread(target=installerFunction, args=(fullInstallSettings, installStatusWidget), daemon=True)
        t.start()

    def mainloop(self):
        self.root.mainloop()

