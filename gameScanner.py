import json
import common
import os
import subprocess
try:
	from typing import List, Optional
except ImportError:
	pass # Just needed for pycharm comments

#contains all the install information required to install the game to a given path
class FullInstallConfiguration:
	def __init__(self, subModConfig, path, isSteam):
		# type: (SubModConfig, str, bool) -> None
		self.subModConfig = subModConfig
		self.installPath = path
		self.isSteam = isSteam
		self.useIPV6 = False

	#applies the fileOverrides to the files to
	def buildFileListSorted(self):
		# type: () -> List[ModFile]
		# convert the files list into a dict
		filesDict = {}
		for file in self.subModConfig.files:
			filesDict[file.name] = file

		for fileOverride in self.subModConfig.fileOverrides:
			# skip overrides where OS doesn't match
			if common.Globals.OS_STRING not in fileOverride.os:
				continue

			# skip overrides where isSteam doesn't match (NOTE: 'steam' can be null, which means that any type is acceptable
			if fileOverride.steam is not None and fileOverride.steam != self.isSteam:
				continue

			# for all other overrides, overwrite the value in the filesDict with a new ModFile
			currentModFile = filesDict[fileOverride.name]
			filesDict[fileOverride.name] = ModFile(currentModFile.name, fileOverride.url, currentModFile.priority)

		# sort the priority from Lowest to Highest (eg items with priority '0' will always be at start of the list)
		# this is because the low priority items should be extracted first, so the high priority items can overwrite them.
		return sorted(filesDict.values(), key=lambda x: x.priority)

# NOTE: the 'priority' indicates the order of extraction:
# Files are extracted in order 0,1,2,3 ...
# Therefore, the 'later extracted' files are higher priority, that is archives with priority 3 will overwrite priority 0,1,2 archives
class ModFile:
	def __init__(self, name, url, priority):
		# type: (str, str, int) -> None
		self.name = name
		self.url = url
		self.priority = priority #consider renaming this "extractionOrder"?

class ModFileOverride:
	def __init__(self, name, os, steam, url):
		# type: (str, List[str], Optional[bool], str) -> None
		self.name = name
		self.os = os #note: this is an ARRAY, eg ["mac", "linux"]
		self.steam = steam	#this can be 'none' if the override applies to both mac and steam
		self.url = url

class ModOptionGroup:
	def __init__(self, name, radioOptions, checkBoxOptions):
		# type: (str, List[ModOption], List[ModOption]) -> None
		"""
		Holds mod options.The options should be applicable to any submod within a mod
		:param name: The name of the group. Used as an identifier in the installer, and also displayed on the GUI
		:param radioOptions: List of ModOption which are mutually exclusive.
		:param checkBoxOptions: List of ModOption where you can choose any (or none)
		NOTE: the radioOptions and checkBoxOptions will be empty lists if they do not exist in the JSON.
		"""
		self.name = name # type: str
		self.radioOptions = radioOptions # type: List[ModOption]
		self.checkBoxOptions = checkBoxOptions # type: List[ModOption]

class ModOption:
	def __init__(self, name, data):
		# type: (str, str) -> None
		"""
		A single mod option, used within a ModOptionGroup.
		:param name: the name of the mod option
		:param data: the data associated with the option (for example, a URL). Can be None if no data is required
		:param value: This field is not populated in the JSON. It's used to indicate whether the user has activated
					  the option or not.
					  TODO: figure out a cleaner way to do this? I don't like having this mutable.
		"""
		self.name = name # type: str
		self.data = data # type: Optional[str]
		self.value = False # type: bool

#directly represents a single submod from the json file
class SubModConfig:
	subModUniqueIDCounter = 0

	#object initialized in factory func
	def __init__(self, mod, subMod):
		# Generate a unique ID for each subModConfig. This variable is not present in the JSON file.
		self.id = SubModConfig.subModUniqueIDCounter
		SubModConfig.subModUniqueIDCounter += 1

		self.family = mod['family'] # type: str
		self.modName = mod['name']  # type: str
		self.target = mod['target'] # type: str
		self.CFBundleName = mod.get('CFBundleName') # type: Optional[str]
		self.CFBundleIdentifier = mod.get('CFBundleIdentifier') # type: Optional[str]
		self.dataName = mod['dataname'] # type: str
		self.identifiers = mod['identifiers'] # type: List[str]
		self.subModName = subMod['name'] # type: str

		self.files = [] # type: List[ModFile]
		for subModFile in subMod['files']:
			self.files.append(ModFile(name=subModFile['name'], url = subModFile['url'], priority=subModFile['priority']))

		self.fileOverrides = [] # type: List[ModFileOverride]
		for subModFileOverride in subMod['fileOverrides']:
			self.fileOverrides.append(ModFileOverride(name=subModFileOverride['name'], os=subModFileOverride['os'], steam=subModFileOverride['steam'], url=subModFileOverride['url']))

		self.modOptions = [] # type: List[ModOptionGroup]

		def jsonModOptionListToPythonModOptionList(jOptionList):
			return [ModOption(jOption['name'], jOption.get('data', None)) for jOption in jOptionList]

		for jsonModOptionGroup in mod.get('modOptionGroups', []):
			self.modOptions.append(
				ModOptionGroup(jsonModOptionGroup['name'],
				               jsonModOptionListToPythonModOptionList(jsonModOptionGroup.get('radio', [])),
				               jsonModOptionListToPythonModOptionList(jsonModOptionGroup.get('checkBox',[])))
			)

	def __repr__(self):
		return "Type: [{}] Game Name: [{}]".format(self.modName, self.subModName)

	# Submod lists may contain many entries with the same modName (eg a list may have [umi-question:voice, umi-question:full, umi-question:1080p])
	# This function gets the unique modNames. It also preserves the original order of the list.
	@staticmethod
	def getUniqueModNamesInSubModList(subModList):
		# type: ([SubModConfig]) -> [str]
		uniqueModNames = []
		alreadySeenNames = set()
		for subMod in subModList:
			if subMod.modName not in alreadySeenNames:
				uniqueModNames.append(subMod.modName)
				alreadySeenNames.add(subMod.modName)

		return uniqueModNames

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

	if common.Globals.IS_WINDOWS:
		allPossibleGamePaths.extend(findPossibleGamePathsWindows())

	if common.Globals.IS_MAC:
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
				gogPath = os.path.join(gamePath, "Contents/Resources/game")
				if os.path.exists(gogPath):
					allPossibleGamePaths.append(gogPath)
		else:
			print("Warning: ran findPossibleGamePaths with an unknown game")

	#if all methods fail, return empty list
	return sorted(allPossibleGamePaths)

# Get paths which COULD be game paths.
def getMaybeGamePaths():
	"""
	If supported, searches the computer for things that might be Higurashi games
	Currently only does things on Mac OS and Windows
	TODO: Find ways to search for games on Linux

	:param str gameName: The name of the game to search for (should be either "Higurashi" or "Umineko"), used to reduce the time spent searching on Mac OS
	:return: A list of game paths that might be Higurashi games
	:rtype: list[str]
	"""
	allPossibleGamePaths = []

	if common.Globals.IS_WINDOWS:
		allPossibleGamePaths.extend(findPossibleGamePathsWindows())

	if common.Globals.IS_MAC:
		# mdfind is kind of slow, don't run it more than we have to
		allPossibleGamePaths.extend(
			x for x in subprocess.check_output(["mdfind", "kind:Application", "Higurashi"])
				.decode("utf-8")
				.split("\n") if x
		)

		for gamePath in subprocess.check_output(["mdfind", "kind:Application", "Umineko"]).decode("utf-8").split("\n"):
			allPossibleGamePaths.append(gamePath)
			# GOG installer makes a `.app` that contains the actual game at `/Contents/Resources/game`
			gogPath = os.path.join(gamePath, "Contents/Resources/game")
			if os.path.exists(gogPath):
				allPossibleGamePaths.append(gogPath)

	# if all methods fail, return empty list
	return sorted(allPossibleGamePaths)

def getPossibleIdentifiersFromPath(path):
	# type: (str) -> List[str]
	if not os.path.exists(path):
		return []
	infoPlist = os.path.join(path, "Contents/Info.plist")
	if common.Globals.IS_MAC and os.path.exists(infoPlist):
		try:
			info = subprocess.check_output(
				["plutil", "-convert", "json", "-o", "-", infoPlist]
			)
			parsed = json.loads(info)
			name = parsed["CFBundleExecutable"] + "_Data" # type: str
			# GoG Umineko installs will be formatted like this but we *don't* want to use it
			if name.startswith("Higurashi"):
				return [name]
			else:
				return []
		except (subprocess.CalledProcessError, KeyError):
			pass
	return os.listdir(path)


def scanForFullInstallConfigs(subModConfigList, possiblePaths=None):
	# type: (List[SubModConfig], [str]) -> [FullInstallConfiguration]
	"""
	This function has two purposes:
		- When given a specific game path ('possiblePaths' argument), it checks if any of the given SubModConfig
		  can be installed into that path. Each SubModConfig which can be installed into that path will be returned
		  as a FullInstallConfiguration object.

		- When not given a specific game path, it searches the computer for valid installations where the given
		  SubModConfig could be installed to. Each valid (installation + SubModConfig) combination will be returned
		  as a FullInstallConfiguration object.

	:param subModConfigList: A **list** of SubModConfig which are to be searched for on disk
	:param possiblePaths: (Optional) Specify a path to check if the given SubModConfig can be installed into that path.
	:return:    A list of FullInstallConfig, each representing a valid install path that the
				given SubModConfig(s) couldbe installed into.
	"""

	returnedFullConfigs = []
	if not possiblePaths:
		possiblePaths = getMaybeGamePaths()

	subModConfigDictionary = {}
	for subMod in subModConfigList:
		for identifier in subMod.identifiers:
			subModConfigDictionary[identifier] = subMod

	for gamePath in possiblePaths:
		possibleIdentifiers = getPossibleIdentifiersFromPath(gamePath)
		for possibleIdentifier in possibleIdentifiers:
			try:
				subModConfig = subModConfigDictionary[possibleIdentifier]
				possibleSteamPaths = [
					os.path.join(gamePath, "steam_api.dll"),
					os.path.join(gamePath, "Contents/Plugins/CSteamworks.bundle"),
					os.path.join(gamePath, "libsteam_api.so")
				]

				isSteam = False
				for possibleSteamPath in possibleSteamPaths:
					if os.path.exists(possibleSteamPath):
						isSteam = True

				returnedFullConfigs.append(FullInstallConfiguration(subModConfig, gamePath, isSteam))
				break
			except KeyError:
				pass

	return returnedFullConfigs

def scanUserSelectedPath(subModConfigList, gameExecutablePath):
	# type: (List[SubModConfig], [str]) -> ([FullInstallConfiguration], str)
	"""
	Scans a user-selected path for configs. Unlike the normal "scanForFullInstallConfigs()" function,
	this will attempt to search all parent directories, incase a user has selected a subdirectory of the game directory
	by accident.
	:param subModConfigList:
	:param gameExecutablePath:
	:return: A tuple - The first is an array of valid FullInstallConfigurations.
					 - The second is an error message (on success a 'success' message is generated)
	"""
	if gameExecutablePath:
		if os.path.isfile(gameExecutablePath):
			gameExecutablePath = os.path.dirname(gameExecutablePath)

		# Search upwards for the game path, in case user has selected a deep subfolder of the game path
		alreadyScanned = set()
		for scanAttempt in range(10):
			fullInstallConfigs = scanForFullInstallConfigs(subModConfigList=subModConfigList, possiblePaths=[gameExecutablePath])
			if fullInstallConfigs:
				return fullInstallConfigs, "scanUserSelectedPath(): Path [{}] Ok".format(gameExecutablePath)

			alreadyScanned.add(gameExecutablePath)
			gameExecutablePath = os.path.dirname(gameExecutablePath)
			if gameExecutablePath in alreadyScanned:
				break

		# Failed to find path. Notify user which paths tried to be searched to find the file.
		errorStrings = ["scanUserSelectedPath(): Can't install the mod. Searched:"] + sorted(list(alreadyScanned))
		errorMessage = '\n - '.join(errorStrings)
		return None, errorMessage

	return None, "scanUserSelectedPath(): game executable path is falsey: [{}]".format(gameExecutablePath)
