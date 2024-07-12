#!/usr/bin/python
from __future__ import print_function, unicode_literals, with_statement

import argparse
import locale
import os
import sys
import platform

# Embedded python doesn't have current directory as path
import tempfile
import time

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
			subModconfigList.append(conf)
	return subModconfigList


def installerCommonStartupTasks():
	"""
	Peforms tasks common to both the normal GUI installer and the CLI Installer
	- Change current directory to path of the launched python file
	- Setup logging
	- Read the launcher path (works only on Windows)
	- Enable developer mode if installData.json found on disk
	- Log information about the environment (current dir, python version etc.)
	- On Windows, check for hostname problems
	"""
	errors = []

	print("Installer script name (argv[0]): [{}]".format(sys.argv[0]))

	# If you double-click on the file in Finder on macOS, it will not open with a path that is near the .py file
	# Since we want to properly find things like `./aria2c`, we should move to that path first.
	dirname = os.path.dirname(sys.argv[0])
	if dirname.strip():
		os.chdir(dirname)

	# redirect stdout to both a file and console
	# TODO: on MAC using a .app file, not sure if this logfile will be writeable
	#      could do a try-catch, and then only begin logging once the game path has been set?
	sys.stdout = logger.Logger(common.Globals.LOG_FILE_PATH)
	logger.setGlobalLogger(sys.stdout)
	sys.stderr = logger.StdErrRedirector(sys.stdout)

	parser = argparse.ArgumentParser()

	parser.add_argument(
		'--launcher-path',
		dest="launcher_path",
		default=None,
		help=('Optionally specify the path to the Windows install launcher. '
		'This Python script may call the install launcher with special arguments (eg. to open the file picker)')
	)

	parser.add_argument(
		"-ao",
		"--asset-os",
		action="store",
		dest="force_asset_os_string",
		metavar="ASSET_OS",
		default=None,
		choices=['windows', 'linux', 'mac'],
		help=(
			'Force the installer to install assets from another operating system'
			'Mainly used on Linux to install Windows assets for use under Wine'
		),
	)

	parser.add_argument(
		'--no-launch-browser',
		action='store_true',
        help=(
			'Launch the browser automatically after web server started'
		)
	)

	args = parser.parse_args()

	if args.no_launch_browser:
		common.Globals.LAUNCH_BROWSER = False

	# Optional first argument tells the script the path of the launcher (currently only used with Windows launcher)
	if args.launcher_path is not None:
		common.Globals.NATIVE_LAUNCHER_PATH = args.launcher_path
		print("Launcher is located at [{}]".format(common.Globals.NATIVE_LAUNCHER_PATH))
	else:
		if common.Globals.IS_WINDOWS:
			print("WARNING: Launcher path not given to Python script. Will try to use PowerShell file chooser instead of native one.")

	common.Globals.FORCE_ASSET_OS_STRING = args.force_asset_os_string
	if common.Globals.FORCE_ASSET_OS_STRING is not None:
		print("Warning: Force asset argument passed - will install {} assets despite os being {}".format(common.Globals.FORCE_ASSET_OS_STRING, common.Globals.OS_STRING))

	# Enable developer mode if we detect the program is run from the git repository
	# Comment out this line to simulate a 'normal' installation - files will be fetched from the web.
	if os.path.exists("installData.json"):
		common.Globals.DEVELOPER_MODE = True
		print("""------ NOTE: Developer mode is enabled (will use installData.json from disk) ----""")

	print("> Install Started On {}".format(datetime.datetime.now()))
	common.Globals.getBuildInfo()
	print("Python {}".format(sys.version))
	print("Operating System: {} {} {} ({})".format(platform.system(), platform.release(), platform.machine(), platform.version()))
	print("Locale - Default: {} | Preferred: {} | Filesystem: {}".format(sys.getdefaultencoding(), locale.getpreferredencoding(), sys.getfilesystemencoding()))
	print("Installer Build Information: {}".format(common.Globals.BUILD_INFO))
	print("Installer is being run from: [{}]".format(os.getcwd()))

	# Windows only checks
	if common.Globals.IS_WINDOWS:
		# Check for non-ascii characters in hostname, which prevent the server starting up
		if not all(ord(c) < 128 for c in socket.gethostname()):
			errors.append(
				"ERROR: It looks like your hostname [{}] contains non-ASCII characters. This may prevent the installer from starting up.\n"
				"Please change your hostname to only contain ASCII characters, then restart the installer.".format(socket.gethostname())
			)

		# Check if installer is being run from system root (C:\Windows for example)
		system_root = os.environ.get('SYSTEMROOT')
		if system_root:
			if os.path.realpath(os.getcwd()).startswith(os.path.realpath(system_root)):
				errors.append("ERROR: You are trying to run the installer from the system folder [{}]. Please do not use the start menu to launch the installer. Please run the installer from a user writeable folder instead".format(dirname))

	# Check if the current folder is writeable
	try:
		# Write some dummy data to a temp file
		test_data = "test"
		temp_file_handle, temp_file_path = tempfile.mkstemp(dir='.')
		with os.fdopen(temp_file_handle, 'w') as temp_file:
			temp_file.write(test_data)

		# Wait for the file to appear on the filesystem (in most cases this happens immediately)
		for i in range(3):
			if os.path.exists(temp_file_path):
				break
			time.sleep(.5)

		# Read back the file and check its contents is the same that was written earlier
		with open(temp_file_path) as temp_file:
			if temp_file.read() != test_data:
				errors.append(
					"ERROR: File written to installer folder was not readable [{}]. Please run the installer from a user writeable folder instead".format(temp_file_path))

		# Remove the temp file
		os.remove(temp_file_path)
	except Exception as e:
		traceback.print_exc()
		errors.append("ERROR: Installer folder is not writeable [{}]. Please run the installer from a user writeable folder instead. Full error:\n{}".format(os.getcwd(), e))

	if errors:
		print('\n--------------------------------------------------------------')
		print('The following problems were found during startup:')
		print('- ', end='')
		print('\n- '.join(errors))
		print('--------------------------------------------------------------')
		print('Please try to fix these errors before continuing, then restart the installer.')
		input('If you think the error was a false positive, press ENTER to continue anyway')
		input("If you're absolutely sure you want to continue, press ENTER again")

if __name__ == "__main__":
	installerCommonStartupTasks()

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
		t_loadDonations = common.makeThread(installerGUI.loadDonationStatus)
		t_loadLatestInstallerStatus = common.makeThread(common.Globals.loadInstallerLatestStatus)
		t_preloadModUpdatesHTML = common.makeThread(installerGUI.preloadModUpdatesHTML)
		t_loadDonations.start()
		t_loadLatestInstallerStatus.start()
		t_preloadModUpdatesHTML.start()

		try:
			t_loadDonations.join(timeout=6)
		except Exception as e:
			print(e)

		try:
			t_loadLatestInstallerStatus.join(timeout=6)
		except Exception as e:
			print(e)

		try:
			t_preloadModUpdatesHTML.join(timeout=6)
		except Exception as e:
			print(e)


	def doInstallerInit():
		try:
			if common.Globals.IS_MAC:
				common.Globals.macUnQuarantineExecutable("./.aria2c")
				common.Globals.macUnQuarantineExecutable("./.7za")

			# Executable scanning must happen first, as other init operations might require Aria or CURL to download
			common.Globals.scanForExecutables()
			common.Globals.scanCertLocation()
			common.Globals.chooseCurlCertificate()
			common.Globals.chooseURLOpenCertificate()

			# Run remaining init tasks concurrently
			t_getSubModConfig = common.makeThread(thread_getSubModConfigList)
			t_unimportantTasks = common.makeThread(thread_unimportantTasks)

			common.startAndJoinThreads([t_getSubModConfig, t_unimportantTasks])

			if common.Globals.DEVELOPER_MODE:
				fileVersionManagement.Developer_ValidateVersionDataJSON(t_getSubModConfig.result)

			# Indicate init is complete. This causes the browser to advance from loading_screen.html to index.html
			installerGUI.setSubModconfigs(t_getSubModConfig.result)
		except Exception as e:
			print(traceback.format_exc())
			# Indicate init failed. This causes the browser to show an error message.
			installerGUI.setInitError(e, traceback.format_exc())

	# The installer initialization (scan for executables, check network, retrieve mod list) is launched
	# concurrently with the Web GUI. The Web GUI shows a loading screen until init is complete.
	threading.Thread(target=doInstallerInit).start()

	try:
		installerGUI.server_test()
	except KeyboardInterrupt:
		installerGUI.shutdown()

	logger.Logger.globalLogger.close_all_logs()
