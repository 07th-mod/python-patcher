#!/usr/bin/python
from __future__ import print_function, unicode_literals, with_statement

import os
import sys

# Embedded python doesn't have current directory as path
if os.getcwd() not in sys.path:
	print("Startup: Adding {} to path".format(os.getcwd()))
	sys.path.append(os.getcwd())

import datetime
import pprint
import socket
import threading
import traceback

import common
import httpGUI
import installConfiguration
import logger
import fileVersionManagement

try: input = raw_input
except NameError: pass

pp = pprint.PrettyPrinter(indent=4)

try:
	from urllib.request import urlopen, Request
	from urllib.error import HTTPError
except ImportError:
	from urllib2 import urlopen, Request, HTTPError

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
	# Optional first argument tells the script the path of the launcher (currently only used with Windows launcher)
	if len(sys.argv) > 1:
		common.Globals.NATIVE_LAUNCHER_PATH = sys.argv[1]

	# If you double-click on the file in Finder on macOS, it will not open with a path that is near the .py file
	# Since we want to properly find things like `./aria2c`, we should move to that path first.
	dirname = os.path.dirname(sys.argv[0])
	if dirname.strip():
		os.chdir(dirname)
	# Enable developer mode if we detect the program is run from the git repository
	# Comment out this line to simulate a 'normal' installation - files will be fetched from the web.
	if os.path.exists("installData.json"):
		common.Globals.DEVELOPER_MODE = True
		print("""------ NOTE: Developer mode is enabled (will use installData.json from disk) ----""")

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
		raise SystemExit(-1)


	print("\n\n----------------------------------------- PLEASE READ -----------------------------------------\n")
	print(" - Do not close this window until you are finished with the installer! Closing this window will\n"
	      "   stop the installer!")
	print(" - A web page should have opened - do not close it! The web page is the installer's user interface.")
	print(" - On the web page, click the game you want to mod to start the installation.")
	print("\n----------------------------------------- PLEASE READ -----------------------------------------\n")

	installerGUI = httpGUI.InstallerGUI()

	def thread_getSubModConfigList():
		modList = getModList(common.Globals.DEVELOPER_MODE)
		common.Globals.loadCachedDownloadSizes(modList)
		return getSubModConfigList(modList)

	def thread_unimportantTasks():
		t_loadNews = common.makeThread(installerGUI.loadNews)
		t_loadDonations = common.makeThread(installerGUI.loadDonationStatus)
		t_loadNews.start()
		t_loadDonations.start()

		try:
			t_loadNews.join(timeout=6)
		except Exception as e:
			print(e)

		try:
			t_loadDonations.join(timeout=6)
		except Exception as e:
			print(e)

	def doInstallerInit():
		try:
			# Executable scanning must happen first, as other init operations might require Aria or CURL to download
			common.Globals.scanForExecutables()
			common.Globals.scanCertLocation()

			# Run remaining init tasks concurrently
			t_getSubModConfig = common.makeThread(thread_getSubModConfigList)
			t_unimportantTasks = common.makeThread(thread_unimportantTasks)

			common.startAndJoinThreads([t_getSubModConfig, t_unimportantTasks])

			if common.Globals.DEVELOPER_MODE:
				fileVersionManagement.Developer_ValidateVersionDataJSON(t_getSubModConfig.result)

			# Indicate init is complete. This causes the browser to advance from loading_screen.html to index.html
			installerGUI.setSubModconfigs(t_getSubModConfig.result)
		except Exception as e:
			errorString = "{}\n\n{}".format(e, traceback.format_exc())
			print(traceback.format_exc())
			# Indicate init failed. This causes the browser to show an error message.
			installerGUI.setInitError(errorString)

	# The installer initialization (scan for executables, check network, retrieve mod list) is launched
	# concurrently with the Web GUI. The Web GUI shows a loading screen until init is complete.
	threading.Thread(target=doInstallerInit).start()
	installerGUI.server_test()
