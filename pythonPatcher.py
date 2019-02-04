#!/usr/bin/python
from __future__ import print_function, unicode_literals, with_statement

from common import *
import higurashiInstaller
import uminekoInstaller
from gameScanner import SubModConfig, SubModFilter
from gameScanner import scanForFullInstallConfigs
from gui import InstallerGUI

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

subModFilter = SubModFilter(subModconfigList)

#ask the user which family of games they want
families = subModFilter.getFamilyList()
print(families)

#filter out by users choice of family
subModsFilteredByFamily = subModFilter.filterByFamily(families[0])

#ask the user what submod they want to install
modNameList = subModsFilteredByFamily.getSubModNameList()
print(modNameList)

#filter out by user's choice of sub mod name
finalSubModList = subModsFilteredByFamily.filterByModName(modNameList[0])
print(finalSubModList.getSubMods())


configs = scanForFullInstallConfigs(subModconfigList)

gui = InstallerGUI()
gui.mainloop()

# # class for main installer to provide progress updates, possible on a different thread
# class ProgressNotifier:
# 	pass
#
# progressNotifier = ProgressNotifier()
#
# # for testing, just skip the GUI part
# uminekoInstaller.mainUmineko(progressNotifier, configs.pop())

exit()
