import os
import threading

import commandLineParser
import gui
import gameScanner
import higurashiInstaller
import logger
import uminekoInstaller

try:
    from tkinter import *
    from tkinter.ttk import *
    from tkinter import filedialog
except ImportError:
    from Tkinter import *
    from ttk import *
    import Tkinter as tkinter
    import tkFileDialog as filedialog
    import tkMessageBox as messagebox


class InstallerGUI:
    def __init__(self, allSubModConfigs):
        """
        :param allSubModList: a list of SubModConfigs derived from the json file (should contain ALL submods in the file)
        """
        self.root = Tk()
        self.root.minsize(800, 500)
        self.wiz = gui.InstallWizard(self.root)
        self.wiz.pack()

        #Note: MUST keep a handle to the image, otherwise it will be garbage collected!!!
        self.img = PhotoImage(file="earth.gif")

        self.allSubModConfigs = allSubModConfigs
        self.showModList()

    def showModList(self):
        frame = self.wiz.get_new_frame_and_hide_old_frame("Choose which mod you want to install")
        btn_list = gui.ImageButtonList(frame, max_per_column=3)

        for modName in gameScanner.SubModConfig.getUniqueModNamesInSubModList(self.allSubModConfigs):
            btn_list.add_button(modName, "", self.img, self.setModNameAndAdvance, modName)

        btn_list.pack()

    def setModNameAndAdvance(self, modName):
        # type: (str) -> None
        print("User Chose Mod: [{}]".format(modName))

        frame = self.wiz.get_new_frame_and_hide_old_frame("Choose which mod option you want to install")
        btn_list = gui.ImageButtonList(frame, max_per_column=6)
        for subMod in [subMod for subMod in self.allSubModConfigs if subMod.modName == modName]:
            btn_list.add_button(subMod.subModName, "", self.img, self.setSubModAndAdvance, subMod)

        btn_list.pack()

    def setSubModAndAdvance(self, subMod):
        # type: (gameScanner.SubModConfig) -> None
        def askGameExeAndValidate():
            #this creates the default option, which allows you to select all identifiers and any extras specified here.
            extensionList = ["com.apple.application"] + subMod.identifiers
            fileList = [("Game Executable", x) for x in extensionList]
            fileList.append(("Any In Game Folder", "*.*"))

            gameExecutablePath = filedialog.askopenfilename(filetypes=fileList)
            if gameExecutablePath:
                installDir = os.path.normpath(os.path.join(gameExecutablePath, os.pardir))

                fullInstallConfigs = gameScanner.scanForFullInstallConfigs(subModConfigList=[subMod], possiblePaths=[installDir])
                if fullInstallConfigs:
                    print("Path Ok: ", installDir)
                    self.confirmationPage(fullInstallConfigs[0])
                else:
                    print("Path INVALID:", installDir)
                    messagebox.showerror("Error", "Can't install the mod to the path\n" + installDir)

        #do search over all possible install locations that the selected submod can be installed.
        fullInstallConfigs = gameScanner.scanForFullInstallConfigs([subMod])

        #show "no games autodetected - please choose manually" if none exist

        frame = self.wiz.get_new_frame_and_hide_old_frame("Choose which installation to install the mod to")
        btn_list = gui.ImageButtonList(frame, max_per_column=6)
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
        frame = self.wiz.get_new_frame_and_hide_old_frame("Please wait for the installer to finish", disable_back=True)
        installStatusWidget = gui.InstallStatusWidget(frame)
        installStatusWidget.pack()

        def ariaAndSevenZipMonitorCallback(message):
            status = commandLineParser.tryGetAriaStatusUpdate(message)
            if status:
                installStatusWidget.threadsafe_set_subtask_progress(status.percentCompleted)
                installStatusWidget.threadsafe_notify_text("Downloading - [{}] ({}%) ETA: {}".format(
                    status.amountCompletedString,
                    status.percentCompleted,
                    status.ETAString
                ))
                return

            status = commandLineParser.tryGetSevenZipStatusUpdate(message)
            if status:
                installStatusWidget.threadsafe_set_subtask_progress(status.percentCompleted)
                installStatusWidget.threadsafe_notify_text("Extracting - {:3}% num: {:8}\nfilename: {}".format(
                    status.percentCompleted,
                    status.numItemsCompleted,
                    status.currentlyProcessingFilename
                ))
                return

            status = commandLineParser.tryGetOverallStatus(message)
            if status:
                installStatusWidget.threadsafe_set_overall_progress(status.overallPercentage)
                installStatusWidget.threadsafe_notify_text("Overall Progress: {}% Task: {}".format(
                    status.overallPercentage,
                    status.currentTask
                ))
                return

            # if the message is not a aria or 7zip message, just show it in the gui log window
            installStatusWidget.threadsafe_append_log(message)

        logger.registerLoggerCallback("console_output_callback", ariaAndSevenZipMonitorCallback)

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
