#!/usr/bin/python
from __future__ import print_function, unicode_literals, with_statement
import sys, os, os.path as path, platform, shutil, glob, subprocess, json
import pprint
pp = pprint.PrettyPrinter(indent=4)
try:
	from urllib.request import urlopen, Request
	from urllib.error import HTTPError
except ImportError:
	from urllib2 import urlopen, Request, HTTPError

try:
	import tkinter
	from tkinter import filedialog
	from tkinter import Listbox
	from tkinter import messagebox
	from tkinter import Checkbutton
	from tkinter import IntVar
except ImportError:
	import Tkinter as tkinter
	import tkFileDialog as filedialog
	import tkMessageBox as messagebox
	from Tkinter import Listbox
	from Tkinter import CheckButton
	from Tkinter import IntVar

# Python 2 Compatibility
try: input = raw_input
except NameError: pass

try:
	"".decode("utf-8")
	def decodeStr(string):
		return string.decode("utf-8")
except AttributeError:
	def decodeStr(string):
		return string

def printErrorMessage(text):
	"""
	Prints message in red if stdout is a tty
	"""
	if sys.stdout.isatty:
		print("\x1b[1m\x1b[31m" + text + "\x1b[0m")
	else:
		print(text)

def exitWithError():
	""" On Windows, prevent window closing immediately when exiting with error. Other plaforms just exit. """
	print("ERROR: The installer cannot continue. Press any key to exit...")
	if IS_WINDOWS:
		input()
	sys.exit(1)

def findWorkingExecutablePath(executable_paths, flags):
	"""
	Try to execute each path in executable_paths to see which one can be called and returns exit code 0
	The 'flags' argument is any extra flags required to make the executable return 0 exit code
	:param executable_paths: a list [] of possible executable paths (eg. "./7za", "7z")
	:param flags: any extra flags like "-h" required to make the executable have a 0 exit code
	:return: the path of the valid executable, or None if no valid executables found
	"""
	with open(os.devnull, 'w') as os_devnull:
		for path in executable_paths:
			try:
				if subprocess.call([path, flags], stdout=os_devnull) == 0:
					print("Found valid executable:", path)
					return path
			except:
				pass

	return None
################################################## Global Variables#####################################################

# The installer info version this installer is compatibile with
# Increment it when you make breaking changes to the json files
JSON_VERSION = 1

# Global variable controlling use of IPV6, toggled by a checkbox in the GUI. By default, IPV6 is NOT used.
class GlobalSettings:
	def __init__(self):
		self.USE_IPV6 = False

GLOBAL_SETTINGS = GlobalSettings()

###################################### Executable detection and Installation ###########################################

# If you double-click on the file in Finder on macOS, it will not open with a path that is near the .py file
# Since we want to properly find things like `./aria2c`, we should move to that path first.
dirname = os.path.dirname(sys.argv[0])
if dirname.strip():
	os.chdir(dirname)

# Define constants used throughout the script. Use function calls to enforce variables as const
IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"
IS_MAC = platform.system() == "Darwin"

#query available executables. If any installation of executables is done in the python script, it must be done
#before this executes
ARIA_EXECUTABLE = findWorkingExecutablePath(["./aria2c", "./.aria2c", "aria2c"], '-h')
if ARIA_EXECUTABLE is None:
	# TODO: automatically download and install dependencies
	print("ERROR: aria2c executable not found (aria2c). Please install the dependencies for your platform.")
	exitWithError()

SEVEN_ZIP_EXECUTABLE = findWorkingExecutablePath(["./7za", "./.7za", "7za", "./7z", "7z"], '-h')
if SEVEN_ZIP_EXECUTABLE is None:
	# TODO: automatically download and install dependencies
	print("ERROR: 7-zip executable not found (7za or 7z). Please install the dependencies for your platform.")
	exitWithError()

#when calling this function, use named arguments to avoid confusion!
def aria(downloadDir=None, inputFile=None, url=None):
	"""
	Calls aria2c with some default arguments:
	TODO: list what each default argument does as comments next to arguments array?

	:param downloadDir: The directory to store the downloaded file(s)
	:param inputFile: The path to a file containing multiple URLS to download (see aria2c documentation)
	:return Returns the exit code of the aria2c call
	"""
	arguments = [
		ARIA_EXECUTABLE,
		"--file-allocation=none",
		'--continue=true',
		'--retry-wait=5',
		'-m 0',
		'-x 8',
		'-s 8',
		'-j 1',
		'--follow-metalink=mem',  #always follow metalinks, for now
		'--check-integrity=true', #check integrity when using metalink
	]

	if not GLOBAL_SETTINGS.USE_IPV6:
		arguments.append('--disable-ipv6=true')

	#Add an extra command line argument if the function argument has been provided
	if downloadDir:
		arguments.append('-d ' + downloadDir)

	if inputFile:
		arguments.append('--input-file=' + inputFile)

	if url:
		arguments.append(url)

	return subprocess.call(arguments)

def sevenZipExtract(archive_path, outputDir=None):
	arguments = [SEVEN_ZIP_EXECUTABLE, "x", archive_path, "-aoa"]
	if outputDir:
		arguments.append('-o' + outputDir)
	return subprocess.call(arguments)

####################################### TKINTER Functions and Classes ##################################################
# see http://effbot.org/tkinterbook/tkinter-dialog-windows.htm
class ListChooserDialog:

	def __init__(self, parent, listEntries, guiPrompt, allowManualFolderSelection):
		"""
		NOTE: do not call this constructor directly. Use the ListChooserDialog.showDialog function instead.
		"""
		self.top = tkinter.Toplevel(parent)
		defaultPadding = {"padx":20, "pady":10}

		# Set a description for this dialog (eg "Please choose a game to mod"
		tkinter.Label(self.top, text=guiPrompt).pack()

		# Define the main listbox to hold the choices given by the 'listEntries' parameter
		listboxFrame = tkinter.Frame(self.top)

		# Define a scrollbar and a listbox. The yscrollcommand is so that the listbox can control the scrollbar
		scrollbar = tkinter.Scrollbar(listboxFrame, orient=tkinter.VERTICAL)
		self.listbox = Listbox(listboxFrame, selectmode=tkinter.BROWSE, yscrollcommand=scrollbar.set)

		# Also configure the scrollbar to control the listbox, and pack it
		scrollbar.config(command=self.listbox.yview)
		scrollbar.pack(side=tkinter.RIGHT, fill=tkinter.Y)

		# Setting width to 0 forces auto-resize of listbox see: https://stackoverflow.com/a/26504193/848627
		for item in listEntries:
			self.listbox.insert(tkinter.END, item)
		self.listbox.config(width=0)
		self.listbox.pack(side=tkinter.LEFT, fill=tkinter.BOTH, expand=1)

		# Finally, pack the Frame so its contents are displayed on the dialog
		listboxFrame.pack(**defaultPadding)

		# If the user is allowed to choose a directory manually, add directory chooser button
		if allowManualFolderSelection:
			b2 = tkinter.Button(self.top, text="Choose Folder Manually", command=self.showDirectoryChooser)
			b2.pack(**defaultPadding)

		# Add an 'OK' button. When pressed, the dialog is closed
		b = tkinter.Button(self.top, text="OK", command=self.ok)
		b.pack(**defaultPadding)

		# This variable stores the returned value from the dialog
		self.result = None

	def showDirectoryChooser(self):
		if IS_MAC:
			self.result = filedialog.askopenfilename(filetypes=[(None, "com.apple.application")])
		else:
			self.result = filedialog.askdirectory()
		self.top.destroy()

	def ok(self):
		"""
		This function is called when the 'OK' button is pressed. It retrieves the value of the currently selected item,
		then closes the dialog
		:return:
		"""
		selected_value = None

		if len(self.listbox.curselection()) > 0:
			selected_index = self.listbox.curselection()[0]
			selected_value = self.listbox.get(selected_index)

		self.result = selected_value

		self.top.destroy()

	@staticmethod
	def showDialog(rootGUIWindow, choiceList, guiPrompt, allowManualFolderSelection):
		"""
		Static helper function to show dialog and get a return value. Arguments are the same as constructor
		:param rootGUIWindow: the parent tkinter object of the dialog (can be root window)
		:param choiceList: a list of strings that the user is to choose from
		:param guiPrompt: the description that will be shown on the dialog
		:param allowManualFolderSelection: if true, user is allowed to select a folder manually.
		:return: returns the value the user selected (string), or None if none available
		"""
		d = ListChooserDialog(rootGUIWindow, choiceList, guiPrompt, allowManualFolderSelection)
		rootGUIWindow.wait_window(d.top)
		return d.result

########################################## Installer Functions  and Classes ############################################
class Installer:
	def __init__(self, directory, info):
		"""
		Installer Init

		:param str directory: The directory of the game
		:param dict info: The info dictionary from server JSON file for the requested target
		"""
		self.directory = directory
		self.info = info

		if IS_MAC:
			self.dataDirectory = path.join(self.directory, "Contents/Resources/Data")
		else:
			self.dataDirectory = path.join(self.directory, info["dataname"])

		self.assetsDir = path.join(self.dataDirectory, "StreamingAssets")

		possibleSteamPaths = [
			path.join(self.directory, "steam_api.dll"),
			path.join(self.directory, "Contents/Plugins/CSteamworks.bundle"),
			path.join(self.directory, "libsteam_api.so")
		]

		self.isSteam = False
		for possibleSteamPath in possibleSteamPaths:
			if path.exists(possibleSteamPath):
				self.isSteam = True

		self.downloadDir = info["name"] + "Download"

	def backupUI(self):
		"""
		Backs up the `sharedassets0.assets` file
		"""
		uiPath = path.join(self.dataDirectory, "sharedassets0.assets")
		backupPath = path.join(self.dataDirectory, "sharedassets0.assets.backup")
		if path.exists(uiPath) and not path.exists(backupPath):
			os.rename(uiPath, backupPath)

	def cleanOld(self):
		"""
		Removes folders that shouldn't persist through the install
		(CompiledUpdateScripts, CG, and CGAlt)
		"""
		oldCG = path.join(self.assetsDir, "CG")
		oldCGAlt = path.join(self.assetsDir, "CGAlt")
		compiledScriptsPattern = path.join(self.assetsDir, "CompiledUpdateScripts/*.mg")

		for mg in glob.glob(compiledScriptsPattern):
			os.remove(mg)

		if path.isdir(oldCG):
			shutil.rmtree(oldCG)

		if path.isdir(oldCGAlt):
			shutil.rmtree(oldCGAlt)

	def download(self):
		"""
		Downloads the required files for the mod.
		- The JSON file contains the list of files for each platform to download (see the constructor of this class).
		- This function first selects the appropriate section of the JSON file, depending on the current platform
		- Then, the URLs listed in the JSON file are written out to a file called 'downloadList.txt'
		- Finally, aria2c is called to download the files listed in 'downloadList.txt'
		"""
		if IS_WINDOWS:
			try:
				files = self.info["files"]["win"]
			except KeyError:
				if self.isSteam:
					files = self.info["files"]["win-steam"]
				else:
					files = self.info["files"]["win-mg"]
		else:
			try:
				files = self.info["files"]["unix"]
			except KeyError:
				if self.isSteam:
					files = self.info["files"]["unix-steam"]
				else:
					files = self.info["files"]["unix-mg"]
		try:
			os.mkdir(self.downloadDir)
		except OSError:
			pass
		fileList = open("downloadList.txt", "w")
		for file in files:
			fileList.write(file + "\n")
		fileList.close()

		aria(downloadDir=self.downloadDir, inputFile='downloadList.txt')

		os.remove("downloadList.txt")

	def extractFiles(self):
		"""
		Extracts downloaded files using 7zip: "Overwrite All existing files without prompt."
		"""
		for file in sorted(os.listdir(self.downloadDir)):
			sevenZipExtract(path.join(self.downloadDir, file))

	def moveFilesIntoPlace(self, fromDir=None, toDir=None):
		"""
		Moves files from the directory they were extracted to
		to the game data folder

		fromDir and toDir are for recursion, leave them at their defaults to start the process
		"""
		if fromDir is None: fromDir = self.info["dataname"]
		if toDir is None: toDir = self.dataDirectory

		for file in os.listdir(fromDir):
			src = path.join(fromDir, file)
			target = path.join(toDir, file)
			if path.isdir(src):
				if not path.exists(target):
					os.mkdir(target)
				self.moveFilesIntoPlace(fromDir=src, toDir=target)
			else:
				if path.exists(target):
					os.remove(target)
				shutil.move(src, target)
		os.rmdir(fromDir)

	def cleanup(self):
		"""
		General cleanup and other post-install things

		Removes downloaded 7z files
		On mac, modifies the application Info.plist with new values if available
		"""
		try:
			shutil.rmtree(self.downloadDir)
		except OSError:
			pass

		if IS_MAC:
			# Allows fixing up application Info.plist file so that the titlebar doesn't show `Higurashi01` as the name of the application
			# Can also add a custom CFBundleIdentifier to change the save directory (e.g. for Console Arcs)
			infoPlist = path.join(self.directory, "Contents/Info.plist")
			infoPlistJSON = subprocess.check_output(["plutil", "-convert", "json", "-o", "-", infoPlist])
			parsed = json.loads(infoPlistJSON)
			if "CFBundleName" in self.info and parsed["CFBundleName"] != self.info["CFBundleName"]:
				subprocess.call(["plutil", "-replace", "CFBundleName", "-string", self.info["CFBundleName"], infoPlist])
			if "CFBundleIdentifier" in self.info and parsed["CFBundleIdentifier"] != self.info["CFBundleIdentifier"]:
				subprocess.call(["plutil", "-replace", "CFBundleIdentifier", "-string", self.info["CFBundleIdentifier"], infoPlist])

def getModList(jsonURL):
	"""
	Gets the list of available mods from the 07th Mod server

	:return: A list of mod info objects
	:rtype: list[dict]
	"""
	try:
		file = urlopen(Request(jsonURL, headers={"User-Agent": ""}))
	except HTTPError as error:
		print(error)
		print("Couldn't reach 07th Mod Server to download patch info")
		print("Note that we have blocked Japan from downloading (VPNs are compatible with this installer, however)")
		exitWithError()

	info = json.load(file)
	file.close()
	try:
		version = info["version"]
		if version > JSON_VERSION:
			printErrorMessage("Your installer is out of date.")
			printErrorMessage("Please download the latest version of the installer and try again.")
			print("\nYour installer is compatible with mod listings up to version " + str(JSON_VERSION) + " but the latest listing is version " + str(version))
			exitWithError()
	except KeyError:
		print("Warning: The mod info listing is missing a version number.  Things might not work.")
		return info
	return info["mods"]

def findPossibleGamePathsWindows():
	"""
	Blindly retrieve all game folders in the `Steam\steamappps\common` folder (no filtering is performed)
	TODO: scan other locations than just the steamapps folder
	:return: a list of absolute paths, which are the folders in the `Steam\steamappps\common` folder
	:rtype: list[str]
	"""
	try:
		import winreg
	except ImportError:
		import _winreg as winreg

	registrySteamPath = None
	try:
		registryKey = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam')
		registrySteamPath, _regType = winreg.QueryValueEx(registryKey, 'SteamPath')
		winreg.CloseKey(registryKey)
	except WindowsError:
		print("findPossibleGamePaths: Couldn't read Steam registry key - Steam not installed?")
		return []

	# normpath added so returned paths have consistent slash directions (registry key has forward slashes on Win...)
	try:
		for root, dirs, _files in os.walk(os.path.join(registrySteamPath, r'steamapps\common')):
			return [os.path.normpath(os.path.join(root, x)) for x in dirs]
	except:
		print("findPossibleGamePaths: Couldn't open registry key folder - Steam folder deleted?")
		return []


def findPossibleGamePaths(gameName):
	"""
	If supported, searches the computer for things that might be Higurashi games
	Currently only does things on Mac OS and Windows
	TODO: Find ways to search for games on Linux

	:param str gameName: The name of the game to search for (should be either "Higurashi" or "Umineko"), used to reduce the time spent searching on Mac OS
	:return: A list of game paths that might be Higurashi games
	:rtype: list[str]
	"""
	allPossibleGamePaths = []

	if IS_WINDOWS:
		allPossibleGamePaths.extend(findPossibleGamePathsWindows())

	if IS_MAC:
		# mdfind is kind of slow, don't run it more than we have to
		if gameName == "Higurashi":
			allPossibleGamePaths.extend(
				x for x in subprocess
					.check_output(["mdfind", "kind:Application", "Higurashi"])
					.decode("utf-8")
					.split("\n") if x
			)
		elif gameName == "Umineko":
			for gamePath in subprocess.check_output(["mdfind", "kind:Application", "Umineko"]).decode("utf-8").split("\n"):
				# GOG installer makes a `.app` that contains the actual game at `/Contents/Resources/game`
				gogPath = path.join(gamePath, "Contents/Resources/game")
				if path.exists(gogPath):
					allPossibleGamePaths.append(gogPath)
		else:
			print("Warning: ran findPossibleGamePaths with an unknown game")

	#if all methods fail, return empty list
	return sorted(allPossibleGamePaths)

def getGameNameFromGamePath(gamePath, modList):
	"""
	Given the path to a game folder, gets the name of the game in the folder, ONLY if a mod exists for that game
	The returned name will match the 'dataname' field in the JSON file, or be None type if no name could be determined.

	:param str gamePath: The path to the game folder
	:param list[dict] modList: The list of available mods (used for finding game names)
	:return: The name of the game , or None if no game was matched
	:rtype: str or None
	"""
	name = None

	if IS_MAC:
		try:
			info = subprocess.check_output(["plutil", "-convert", "json", "-o", "-", path.join(gamePath, "Contents/Info.plist")])
			parsed = json.loads(info)
			name = parsed["CFBundleExecutable"] + "_Data"
		except (OSError, KeyError):
			return None
	else:
		#create a set data structure, containing all the mod data folder names
		allModDataFolders = set([mod["dataname"] for mod in modList])
		try:
			for file in os.listdir(gamePath):
				if file in allModDataFolders:
					name = file
					break
		except:
			print("getGameNameFromGamePath failed on path [{}]".format(gamePath))

	if name is None:
		return None

	for mod in modList:
		if mod["dataname"] == name:
			return mod["target"]
	return None

def promptChoice(rootGUIWindow, choiceList, guiPrompt, canOther=False):
	"""
	Prompts the user to choose from a list
	:param list[str] choiceList: The list of choices
	:param str guiPrompt: The prompt to use in GUI mode
	:param str textPrompt: The prompt to use in CLI mode.  Note that the user will be directed to select from a list of integers representing options so please mention that.
	:param bool canOther: Whether or not to give the user an Other option, which will instruct them to give a path to an application
	:param str textPromptWithOther: The text prompt to use if there's both options and the `Other` option available.  If `canOther` is true, `textPrompt` will be used if there are only options (so it's just Other) and this will be used otherwise.  If `canOther` is false, this will be ignored.
	:return: The string that the user selected, or if canOther is true, possibly a path that was not in the option list
	:rtype: str
	"""
	result = ListChooserDialog.showDialog(rootGUIWindow, choiceList, guiPrompt, allowManualFolderSelection=canOther)
	if not result:
		exitWithError()

	return decodeStr(result)

def printSupportedGames(modList):
	"""
	Prints a list of games that have mods available for them
	:param list[dict] modList: The list of available mods
	"""
	print("Supported games:")
	for game in set(x["target"] for x in modList):
		print("  " + game)


def main():
	print("Getting latest mod info...")
	modList = getModList("https://raw.githubusercontent.com/07th-mod/resources/master/higurashiInstallData.json")
	foundGames = [path for path in findPossibleGamePaths("Higurashi") if getGameNameFromGamePath(path, modList) is not None]

	#gameToUse is the path to the game install directory, for example "C:\games\Steam\steamapps\common\Higurashi 02 - Watanagashi"
	gameToUse = promptChoice(
		rootGUIWindow = rootWindow,
		choiceList=foundGames,
		guiPrompt="Please choose a game to mod",
		canOther=True
	)

	#target name, for example 'Watanagashi', that the user has selected
	targetName = getGameNameFromGamePath(gameToUse, modList)
	if not targetName:
		print(gameToUse + " does not appear to be a supported higurashi game.")
		printSupportedGames(modList)
		exitWithError()

	print("targetName", targetName)

	# Using the targetName (eg. 'Watanagashi'), check which mods have a matching name
	# Multiple mods may be returned (eg the 'full' patch and 'voice only' patch may have the same 'target' name
	possibleMods = [x for x in modList if x["target"] == targetName]
	if len(possibleMods) > 1:
		modName = promptChoice(
			rootGUIWindow = rootWindow,
			choiceList=[x["name"] for x in possibleMods],
			guiPrompt="Please choose a mod to install")
		mod = [x for x in possibleMods if x["name"] == modName][0]
	else:
		mod = possibleMods[0]

	installer = Installer(gameToUse, mod)
	print("Downloading...")
	installer.download()
	print("Extracting...")
	installer.backupUI()
	installer.cleanOld()
	installer.extractFiles()
	print("Moving files into place...")
	installer.moveFilesIntoPlace()
	print("Done!")
	installer.cleanup()

################################################## UMINEKO INSTALL #####################################################

UMINEKO_ANSWER_MODS = ["mod_voice_only", "mod_full_patch", "mod_adv_mode"]
UMINEKO_QUESTION_MODS = ["mod_voice_only", "mod_full_patch", "mod_1080p"]
umi_debug_mode = False

# You can use the 'exist_ok' of python3 to do this already, but not in python 2
def makeDirsExistOK(directoryToMake):
	try:
		os.makedirs(directoryToMake)
	except OSError:
		pass

def tryShowFolder(path):
	"""
	Tries to show a given path in the system file browser
	NOTE: this function call does not block! (uses subprocess.Popen)
	:param path: the path to show
	:return: true if successful, false otherwise
	"""
	try:
		if IS_WINDOWS:
			return subprocess.Popen(["explorer", path]) == 0
		elif IS_MAC:
			return subprocess.Popen(["open", path]) == 0
		else:
			return subprocess.Popen(["xdg-open", path]) == 0
	except:
		return False

def uminekoDownload(downloadTempDir, url_list):
	print("Downloading:{} to {}".format(url_list, downloadTempDir))
	makeDirsExistOK(downloadTempDir)

	for url in url_list:
		print("will try to download {} into {} ".format(url, downloadTempDir))
		if not umi_debug_mode:
			if aria(downloadTempDir, url=url) != 0:
				print("ERROR - could not download [{}]. Installation Stopped".format(url))
				exitWithError()


def uminekoExtractAndCopyFiles(fromDir, toDir):
	"""
	This function extracts all archives from the "fromDir" to the "toDir". It also will copy any files in the "fromDir"
	to the "toDir". Finally, if there are any *.utf files in the fromDir, they will be renamed to 0.u in the "toDir"
	depending on the operating system.

	NOTE: this function makes some assumptions about the archive files:
	- all archive files have either the extension .7z, .zip (or both)
	- the archives are intended to be extracted in the order: 'graphics' 'voices' 'update', then any other type of archive

	:param fromDir: source directory to copy/extract files from
	:param toDir: destination directory to place copied/extracted files
	:return: None
	"""
	def sortingFunction(filenameAnyCase):
		filename = filenameAnyCase.lower()
		if 'graphics' in filename:
			return 0
		elif 'voices' in filename:
			return 1
		elif 'update' in filename:
			return 2
		else:
			return 3

	print("extracting from {} to {}".format(fromDir, toDir))

	archives = []
	otherFiles = []

	for filename in os.listdir(fromDir):
		if '.7z' in filename.lower() or '.zip' in filename.lower():
			archives.append(filename)
		else:
			otherFiles.append(filename)

	#sort the archive files so they are extracted in the correct order
	archives.sort(key=sortingFunction)

	for archive_name in archives:
		archive_path = path.join(fromDir, archive_name)
		print("Trying to extract file {} to {}".format(archive_path, toDir))
		if not umi_debug_mode:
			if sevenZipExtract(archive_path, outputDir=toDir) != 0:
				print("ERROR - could not extract [{}]. Installation Stopped".format(archive_path))
				exitWithError()

	#copy all non-archive files to the game folder. If a .utf file is found, rename it depending on the OS
	for sourceFilename in otherFiles:
		fileNameNoExt, extension = os.path.splitext(sourceFilename)

		destFilename = sourceFilename

		#on any OS besides MAC, rename 0.utf files to 0.u files. On mac, leave filenames unchanged.
		if not IS_MAC and extension.lower() == '.utf':
			destFilename = fileNameNoExt + '.u'

		sourceFullPath = os.path.join(fromDir, sourceFilename)
		destFullPath = os.path.join(toDir, destFilename)

		print("Trying to copy", sourceFullPath, "to", destFullPath)
		shutil.copy(sourceFullPath, destFullPath)

def deleteAllInPathExceptSpecified(paths, extensions, searchStrings):
	"""
	Deletes all files in the specified paths, unless they have both a desired extension and a desired search string.
	NOTE: if file has multiple extensions, all will be matched. Eg. .zip.001 will match the extension 'zip' and '001'

	:param paths: A list[] of paths which will have its files deleted according to the below critera
	:param extensions: files to keep must have one of the extensions in this list[] (without the '.', such as 'zip')
	:param searchStrings: files to keep must contain these search strings.
	:return:
	"""
	for path in paths:
		if not os.path.isdir(path):
			print("removeFilesWithExtensions: {} is not a dir or doesn't exist - skipping".format(path))
			continue

		for fileAnyCase in os.listdir(path):
			splitFileName = fileAnyCase.lower().split('.')

			hasCorrectExtension = False
			for extension in splitFileName[1:]:
				if extension in extensions:
					hasCorrectExtension = True

			hasCorrectSearchString = False
			if not searchStrings:
				hasCorrectSearchString = True
			else:
				for searchString in searchStrings:
					if searchString in splitFileName[0]:
						hasCorrectSearchString = True

			# Keep the file if it has both the correct extension and search string. Otherwise, delete it
			fullDeletePath = os.path.join(path, fileAnyCase)
			if hasCorrectExtension and hasCorrectSearchString:
				print("Keeping file:", fullDeletePath)
			else:
				print("Deleting file:", fullDeletePath)
				if not umi_debug_mode:
					os.remove(fullDeletePath)

def backupOrRemoveFiles(folderToBackup):
	"""
	Backs up files for both question and answer arcs
	If a backup already exists, the file is instead removed

	:param folderToBackup: Folder to scan for files. Backups will be placed in the same folder, with extension '.backup'
	:return:
	"""
	pathsToBackup = ['Umineko5to8.exe', 'Umineko5to8', 'Umineko5to8.app',
	                 'Umineko1to4.exe', 'Umineko1to4', 'Umineko1to4.app',
	                 '0.utf', '0.u']

	for pathToBackup in pathsToBackup:
		fullFilePath = os.path.join(folderToBackup, pathToBackup)
		backupPath = fullFilePath + '.backup'

		#only process the file if it exists on disk
		if not os.path.isfile(fullFilePath) and not os.path.isdir(fullFilePath):
			continue

		# backup the file/folder if no backup has been performed previously - otherwise delete the file
		if os.path.isfile(backupPath) or os.path.isdir(backupPath):
			print("backupOrRemoveFiles: removing", fullFilePath, "as backup already exists")
			if os.path.isfile(backupPath):
				os.remove(fullFilePath)
			else:
				shutil.rmtree(fullFilePath)
		else:
			print("backupOrRemoveFiles: backing up", fullFilePath)
			shutil.move(fullFilePath, backupPath)

def installUmineko(gameInfo, modToInstall, gamePath, isQuestionArcs):
	print("User wants to install", modToInstall)
	print("game info:", gameInfo)
	print("game path:", gamePath)

	# do a quick verification that the directory is correct before starting installer
	if not os.path.isfile(os.path.join(gamePath, "arc.nsa")):
		print("There is no 'arc.nsa' in the game folder. Are you sure the correct game folder was selected?")
		print("ERROR - wrong game path. Installation Stopped.")
		exitWithError()

	# Create aliases for the temp directories, and ensure they exist beforehand
	downloadTempDir = path.join(gamePath, "temp")
	advDownloadTempDir = path.join(gamePath, "temp_adv")

	if path.isdir(downloadTempDir):
		print("Information: Temp directories already exist - continued or overwritten install")

		if "voice_only" in modToInstall:
			continueInstallation = messagebox.askyesno("Voice Only Warning",
			                       "We have detected you have run the 'Voice Only' installer before.\n\n" +
			                       "If you switching from 'full patch' to 'voice only', please quit the " +
			                       "installer and completely delete the game directory, then re-install the game\n\n" +
			                       "If you are just upgrading or continuing your voice only install, you can continue the installlation.\n\n" +
			                       "Continue the installation?")

			if not continueInstallation:
				print("User cancelled install (Voice Only)")
				exitWithError()

	makeDirsExistOK(downloadTempDir)
	makeDirsExistOK(advDownloadTempDir)

	# Wipe non-checksummed install files in the temp folder. Print if not a fresh install.
	deleteAllInPathExceptSpecified([downloadTempDir, advDownloadTempDir],
	                               extensions=['7z', 'zip'],
	                               searchStrings=['graphic', 'voice'])

	# Backup/clear the .exe and script files
	backupOrRemoveFiles(gamePath)

	def makeExecutable(executablePath):
		current = os.stat(executablePath)
		os.chmod(executablePath, current.st_mode | 0o111)

	# Download and extract files for Question/Answer Arcs
	if isQuestionArcs:
		if modToInstall == "mod_voice_only":
			uminekoDownload(downloadTempDir, url_list=gameInfo["files"]["voice_only"])
		elif modToInstall == "mod_full_patch":
			uminekoDownload(downloadTempDir, url_list=gameInfo["files"]["full"])
		elif modToInstall == "mod_1080p":
			if IS_WINDOWS:
				uminekoDownload(downloadTempDir, url_list=gameInfo["files"]["1080p_windows"])
			else:
				uminekoDownload(downloadTempDir, url_list=gameInfo["files"]["1080p_linux_mac"])
		else:
			print("ERROR - unknown mod")
			exitWithError()

		uminekoExtractAndCopyFiles(fromDir=downloadTempDir, toDir=gamePath)

		# need to un-quarantine .app file on MAC
		if IS_MAC:
			subprocess.call(["xattr", "-d", "com.apple.quarantine", os.path.join(gamePath, "Umineko1to4.app")])

		makeExecutable(os.path.join(gamePath, "Umineko1to4"))
		makeExecutable(os.path.join(gamePath, "Umineko1to4.app/Contents/MacOS/umineko4"))
	else:
		if modToInstall == "mod_voice_only":
			uminekoDownload(downloadTempDir, url_list=gameInfo["files"]["voice_only"])
			uminekoExtractAndCopyFiles(fromDir=downloadTempDir, toDir=gamePath)
		elif modToInstall == "mod_full_patch":
			uminekoDownload(downloadTempDir, url_list=gameInfo["files"]["full"])
			uminekoExtractAndCopyFiles(fromDir=downloadTempDir, toDir=gamePath)
		elif modToInstall == "mod_adv_mode":
			uminekoDownload(downloadTempDir, url_list=gameInfo["files"]["full"])
			uminekoExtractAndCopyFiles(fromDir=downloadTempDir, toDir=gamePath)
			uminekoDownload(advDownloadTempDir, url_list=gameInfo["files"]["adv"])
			uminekoExtractAndCopyFiles(fromDir=advDownloadTempDir, toDir=gamePath)
		else:
			print("ERROR - unknown mod")
			exitWithError()

		# need to un-quarantine .app file on MAC
		if IS_MAC:
			subprocess.call(["xattr", "-d", "com.apple.quarantine", os.path.join(gamePath, "Umineko5to8.app")])

		makeExecutable(os.path.join(gamePath, "Umineko5to8"))
		makeExecutable(os.path.join(gamePath, "Umineko5to8.app/Contents/MacOS/umineko8"))

	# write batch file to let users launch game in debug mode
	with open(os.path.join(gamePath, "Umineko1to4_DebugMode.bat"), 'w') as f:
		f.writelines(["Umineko1to4.exe --debug", "pause"])
	with open(os.path.join(gamePath, "Umineko5to8_DebugMode.bat"), 'w') as f:
		f.writelines(["Umineko5to8.exe --debug", "pause"])

	# Patched game uses mysav folder, which Steam can't see so can't get incompatible saves by accident.
	# Add batch file which reverses this behaviour by making a linked folder from (saves->mysav)
	with open(os.path.join(gamePath, "EnableSteamSync.bat"), 'w') as f:
		f.writelines(["mklink saves mysav /J", "pause"])

	# For now, don't copy save data

	# Open the temp folder so users can delete/backup any temp install files
	if IS_WINDOWS:
		tryShowFolder(downloadTempDir)
		if 'adv' in modToInstall:
			tryShowFolder(advDownloadTempDir)

def mainUmineko():

	# Given a game path, returns the corresponding game install information for that path
	# In the JSON, this is one of the elements of the top level array
	# It will return 'None' if the game path is invalid (not an Umineko game). Use this feature to scan for valid game paths.
	def getUminekoGameInformationFromGamePath(modList, gamePath):
		for uminekoGameInfo in modList:
			try:
				for filename in os.listdir(gamePath):
					if uminekoGameInfo['dataname'].lower() in filename.lower():
						return uminekoGameInfo
			except:
				print("getGameNameFromGamePath failed on path [{}]".format(gamePath))

		return None

	print("Getting latest mod info (Umineko)...")
	modList = getModList("https://raw.githubusercontent.com/07th-mod/resources/master/uminekoInstallData.json")

	gamePathList = [gamePath for gamePath in findPossibleGamePaths("Umineko") if getUminekoGameInformationFromGamePath(modList, gamePath) is not None]
	print("Detected {} game folders: {}".format(len(gamePathList), gamePathList))

	userSelectedGamePath = promptChoice(
		rootGUIWindow=rootWindow,
		choiceList= gamePathList,
		guiPrompt="Please choose a game to mod",
		canOther=True
	)

	print("Selected game folder: [{}]".format(userSelectedGamePath))
	gameInfo = getUminekoGameInformationFromGamePath(modList, userSelectedGamePath)
	print("Selected Game Information:")
	pp.pprint(gameInfo)

	isQuestionArcs = None
	modNames = None
	if gameInfo['name'] == 'UminekoAnswer':
		modNames = UMINEKO_ANSWER_MODS
		isQuestionArcs = False
	elif gameInfo['name'] == 'UminekoQuestion':
		modNames = UMINEKO_QUESTION_MODS
		isQuestionArcs = True
	else:
		print("Unknown Umineko game [{}]".format(gameInfo['name']))
		exitWithError()

	# ask user which mod they want to apply to their game
	userSelectedMod = promptChoice(
		rootGUIWindow=rootWindow,
		choiceList=modNames,
		guiPrompt="Please choose which mod to install for " + gameInfo['displayName'],
		canOther=False
	)

	installUmineko(gameInfo, userSelectedMod, userSelectedGamePath, isQuestionArcs)

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

def closeAndStartHigurashi():
	rootWindow.withdraw()
	main()
	rootWindow.destroy()

def closeAndStartUmineko():
	rootWindow.withdraw()
	mainUmineko()
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
