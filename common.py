import sys, os, os.path as path, platform, subprocess, json

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

try:
	"".decode("utf-8")
	def decodeStr(string):
		return string.decode("utf-8")
except AttributeError:
	def decodeStr(string):
		return string

try:
	from urllib.request import urlopen, Request
	from urllib.error import HTTPError
except ImportError:
	from urllib2 import urlopen, Request, HTTPError

# Python 2 Compatibility
try: input = raw_input
except NameError: pass

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

# Set os string matching string used in the JSON file, for convenience
OS_STRING = "win"
if IS_LINUX:
	OS_STRING = "linux"
elif IS_MAC:
	OS_STRING = "mac"

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

