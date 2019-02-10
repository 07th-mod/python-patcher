#!/usr/bin/python
from __future__ import print_function, unicode_literals, with_statement

from common import *
from gameScanner import SubModConfig
from gui import InstallerGUI
import logger

import pprint
pp = pprint.PrettyPrinter(indent=4)

#redirect stdout to both a file and console
#TODO: on MAC using a .app file, not sure if this logfile will be writeable
#      could do a try-catch, and then only begin logging once the game path has been set?
sys.stdout = logger.Logger("logfile.log")

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
#modList = getModList("https://raw.githubusercontent.com/07th-mod/python-patcher/master/installData.json")

with open('installData.json', 'r', encoding="utf-8") as content_file:
	modList = json.loads(content_file.read())["mods"]

subModconfigList = []
for mod in modList:
	for submod in mod['submods']:
		conf = SubModConfig(mod, submod)
		print(conf)
		subModconfigList.append(conf)

gui = InstallerGUI(subModconfigList)
gui.mainloop()

exit()
