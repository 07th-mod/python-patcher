#!/usr/bin/python
from __future__ import print_function, unicode_literals, with_statement

from common import *
import higurashiInstaller
import uminekoInstaller
from gameScanner import SubModConfig
from gameScanner import scanForFullInstallConfigs

import pprint
pp = pprint.PrettyPrinter(indent=4)

def check07thModServerConnection():
	"""
	Makes sure that we can connect to the 07th-mod server
	(Patches will fail to download if we can't)
	"""
	try:
		testFile = urlopen(Request("http://07th-mod.com/", headers={"User-Agent": ""}))
		testFile.close()
	except HTTPError as error:
		print(error)
		print("Couldn't reach 07th Mod Server.  The installer will not be able to download patch files.")
		print("Note that we have blocked Japan from downloading (VPNs are compatible with this installer, however)")
		exitWithError()

check07thModServerConnection()


rootWindow = tkinter.Tk()

# Scan for moddable games on the user's computer before starting installation
# higuModList = getModList("https://raw.githubusercontent.com/07th-mod/python-patcher/master/higurashiInstallData.json")
#umimodList = getModList("https://raw.githubusercontent.com/07th-mod/python-patcher/master/uminekoInstallData.json")

with open('uminekoInstallData.json', 'r', encoding="utf-8") as content_file:
	umimodList = json.loads(content_file.read())["mods"]

# with open('higurashiInstallData.json', 'r', encoding="utf-8") as content_file:
# 	higuModList = json.loads(content_file.read())["mods"]

#for now, don't try to load higurashi data. Eventually, merge both json into one

subModconfigList = []
for mod in umimodList:
	for submod in mod['submods']:
		conf = SubModConfig(mod, submod)
		print(conf)
		subModconfigList.append(conf)


configs = scanForFullInstallConfigs(subModconfigList)
# for each path, check which mods are compatible with that path

# class for main installer to provide progress updates, possible on a different thread
class ProgressNotifier:
	pass

progressNotifier = ProgressNotifier()

# for testing, just skip the GUI part
uminekoInstaller.mainUmineko(progressNotifier, configs.pop())



configList = []


for config in configList:
	print(config)

def closeAndStartHigurashi():
	rootWindow.withdraw()
	higurashiInstaller.main(rootWindow)
	rootWindow.destroy()

def closeAndStartUmineko():
	rootWindow.withdraw()
	uminekoInstaller.mainUmineko(rootWindow, configList)
	installFinishedMessage = "Install Finished. Temporary install files have been displayed - please delete the " \
							 "temporary files after checking the mod has installed correctly."
	print(installFinishedMessage)
	messagebox.showinfo("Install Completed", installFinishedMessage)
	rootWindow.destroy()




# Add an 'OK' button. When pressed, the dialog is closed
defaultPadding = {"padx": 20, "pady": 10}
b = tkinter.Button(rootWindow, text="Install Higurashi Mods", command=closeAndStartHigurashi)
b.pack(**defaultPadding)
b = tkinter.Button(rootWindow, text="Install Umineko Mods", command=closeAndStartUmineko)
b.pack(**defaultPadding)

tkinter.Label(rootWindow, text="Advanced Settings").pack()

# Add a checkbox to enable/disable IPV6. IPV6 is disabled by default due to some
# installations failing when IPV6 is used due to misconfigured routers/other problems.
use_ipv6_var = IntVar()
def onIPV6CheckboxToggled():
	GLOBAL_SETTINGS.USE_IPV6 = use_ipv6_var.get()
c = Checkbutton(rootWindow, text="Enable IPv6", var=use_ipv6_var, command=onIPV6CheckboxToggled)
c.pack()

rootWindow.mainloop()
