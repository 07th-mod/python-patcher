#!/usr/bin/python
from __future__ import print_function, unicode_literals, with_statement

import datetime
import io
import json
import os, sys
import common
import gameScanner
import installerGUI
import logger
import httpGUI
from gui import _TKAskYesNo

import pprint
pp = pprint.PrettyPrinter(indent=4)

try:
	from urllib.request import urlopen, Request
	from urllib.error import HTTPError
except ImportError:
	from urllib2 import urlopen, Request, HTTPError

# If you double-click on the file in Finder on macOS, it will not open with a path that is near the .py file
# Since we want to properly find things like `./aria2c`, we should move to that path first.
dirname = os.path.dirname(sys.argv[0])
if dirname.strip():
	os.chdir(dirname)

if __name__ == "__main__":
	# Enable developer mode if we detect the program is run from the git repository
	# Comment out this line to simulate a 'normal' installation - files will be fetched from the web.
	if os.path.exists("installData.json"):
		common.Globals.DEVELOPER_MODE = True

	#redirect stdout to both a file and console
	#TODO: on MAC using a .app file, not sure if this logfile will be writeable
	#      could do a try-catch, and then only begin logging once the game path has been set?
	sys.stdout = logger.Logger(common.Globals.LOG_FILE_PATH)
	logger.setGlobalLogger(sys.stdout)
	sys.stderr = logger.StdErrRedirector(sys.stdout)

	print("\n\n------------------ Install Started On {} ------------------ ".format(datetime.datetime.now()))

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
			common.exitWithError()

	check07thModServerConnection()


	common.Globals.scanForExecutables()

	# Scan for moddable games on the user's computer before starting installation
	if common.Globals.DEVELOPER_MODE and os.path.exists("installData.json"):
		# Use local `installData.json` if it's there (if cloned from github)
		modList = common.getModList("installData.json")
	else:
		modList = common.getModList("https://raw.githubusercontent.com/07th-mod/python-patcher/master/installData.json")

	subModconfigList = []
	for mod in modList:
		for submod in mod['submods']:
			conf = gameScanner.SubModConfig(mod, submod)
			print(conf)
			subModconfigList.append(conf)

	installerGUI = httpGUI.InstallerGUI(subModconfigList)
	installerGUI.server_test()

	exit()
