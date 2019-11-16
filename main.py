#!/usr/bin/python
from __future__ import print_function, unicode_literals, with_statement

import datetime
import os
import pprint
import socket
import sys

import common
import gameScanner
import httpGUI
import installConfiguration
import logger

try: input = raw_input
except NameError: pass

pp = pprint.PrettyPrinter(indent=4)

try:
	from urllib.request import urlopen, Request
	from urllib.error import HTTPError
except ImportError:
	from urllib2 import urlopen, Request, HTTPError

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

def getModList(is_developer=True):
	if is_developer and os.path.exists('installData.json'):
		return common.getModList("installData.json", isURL=False)
	else:
		return common.getModList(common.Globals.GITHUB_MASTER_BASE_URL + "installData.json", isURL=True)

def getSubModConfigList(modList):
	subModconfigList = []
	for mod in modList:
		for submod in mod['submods']:
			conf = installConfiguration.SubModConfig(mod, submod)
			logger.printNoTerminal(conf)
			subModconfigList.append(conf)
	return subModconfigList

if __name__ == "__main__":
	# If you double-click on the file in Finder on macOS, it will not open with a path that is near the .py file
	# Since we want to properly find things like `./aria2c`, we should move to that path first.
	dirname = os.path.dirname(sys.argv[0])
	if dirname.strip():
		os.chdir(dirname)
	# Enable developer mode if we detect the program is run from the git repository
	# Comment out this line to simulate a 'normal' installation - files will be fetched from the web.
	if os.path.exists("installData.json"):
		common.Globals.DEVELOPER_MODE = True
	print("NOTE: Developer mode is enabled (installData.json detected on disk)")

	# redirect stdout to both a file and console
	# TODO: on MAC using a .app file, not sure if this logfile will be writeable
	#      could do a try-catch, and then only begin logging once the game path has been set?
	sys.stdout = logger.Logger(common.Globals.LOG_FILE_PATH)
	logger.setGlobalLogger(sys.stdout)
	sys.stderr = logger.StdErrRedirector(sys.stdout)

	print("> Install Started On {}".format(datetime.datetime.now()))
	common.Globals.getBuildInfo()
	print("Python {}".format(sys.version))
	print("Installer Build Information: {}".format(common.Globals.BUILD_INFO))
	print("Installer is being run from: [{}]".format(os.getcwd()))

	# On Windows, check for non-ascii characters in hostname, which prevent the server starting up
	if common.Globals.IS_WINDOWS and not all(ord(c) < 128 for c in socket.gethostname()):
		print("-------------------------------------------------------------")
		print("ERROR: It looks like your hostname [{}] contains non-ASCII characters. This may prevent the installer from starting up.".format(socket.gethostname()))
		print("Please change your hostname to only contain ASCII characters, then restart the installer.")
		print("You can press ENTER to try to run the installer despite this problem.")
		print("-------------------------------------------------------------")
		input()

	check07thModServerConnection()
	common.Globals.scanForExecutables()
	modList = getModList(common.Globals.DEVELOPER_MODE)
	common.Globals.loadCachedDownloadSizes(modList)
	subModconfigList = getSubModConfigList(modList)
	

	print("\n\n----------------------------------------- PLEASE READ -----------------------------------------\n")
	print(" - Do not close this window until you are finished with the installer! Closing this window will\n"
	      "   stop the installer!")
	print(" - A web page should have opened - do not close it! The web page is the installer's user interface.")
	print(" - On the web page, click the game you want to mod to start the installation.")
	print("\n----------------------------------------- PLEASE READ -----------------------------------------\n")

	installerGUI = httpGUI.InstallerGUI(subModconfigList)
	installerGUI.server_test()

	exit()
