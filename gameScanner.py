from __future__ import unicode_literals

import glob
import json
import re

import common
import os
import subprocess
import traceback

try:
	from typing import List, Optional
except ImportError:
	pass # Just needed for pycharm comments

class OldUnityException(Exception):
	def __init__(self, version):
		# type: (str) -> None
		self.version = version # type: str

	def __str__(self):
		return "Your game uses Unity "  + self.version + " which isn't supported by this mod.  Please update your game to a newer version."

class FailedFileOverrideException(Exception):
	def __init__(self, name, candidates, unity, steam):
		# type: (str, List[ModFileOverride], Optional[str], bool) -> None
		self.name = name
		self.candidates = candidates # type: List[ModFileOverride]
		self.unity = unity
		self.steam = steam

	def describe(self, candidate):
		# type: (ModFileOverride) -> str
		out = "("
		if candidate.steam is not None:
			out += "steam: {}".format(candidate.steam)
		if candidate.unity is not None:
			if len(out) > 1:
				out += ", "
			out += "unity: " + candidate.unity
		return out + ")"

	def __str__(self):
		if not self.candidates:
			return "Your current OS is not supported by the file {} in this mod".format(self.name)
		hasUnity = any(x.unity is not None for x in self.candidates)
		out = "Failed to find a {} file to use, your game has the properties (steam: {}".format(self.name, self.steam)
		if hasUnity:
			out += ", unity: {}".format(self.unity)
		out += ") but the available versions had the requirements " + ", ".join(self.describe(candidate) for candidate in self.candidates)
		return out

#contains all the install information required to install the game to a given path
class FullInstallConfiguration:
	def __init__(self, subModConfig, path, isSteam):
		# type: (SubModConfig, str, bool) -> None
		self.subModConfig = subModConfig # type: SubModConfig
		self.installPath = path # type: str
		self.isSteam = isSteam # type: bool
		self.useIPV6 = False

	#applies the fileOverrides to the files to
	def buildFileListSorted(self, datadir=""):
		# type: (str) -> List[ModFile]
		# convert the files list into a dict
		filesDict = {}
		for file in self.subModConfig.files:
			filesDict[file.name] = file

		unityVersion = None
		assetsbundlePath = os.path.join(datadir, "resources.assets")
		if os.path.exists(assetsbundlePath):
			with open(assetsbundlePath, "rb") as assetsBundle:
				unityVersion = assetsBundle.read(28)[20:].decode("utf-8").rstrip("\0")
				print("Read unity version " + unityVersion)
				if int(unityVersion[0]) < 5:
					raise OldUnityException(unityVersion)

		for fileOverride in self.subModConfig.fileOverrides:
			# skip overrides where OS doesn't match
			if common.Globals.OS_STRING not in fileOverride.os:
				continue

			# skip overrides where isSteam doesn't match (NOTE: 'steam' can be null, which means that any type is acceptable
			if fileOverride.steam is not None and fileOverride.steam != self.isSteam:
				continue

			if fileOverride.unity is not None and fileOverride.unity != unityVersion:
				continue

			# for all other overrides, overwrite the value in the filesDict with a new ModFile
			currentModFile = filesDict[fileOverride.name]
			filesDict[fileOverride.name] = ModFile(currentModFile.name, fileOverride.url, currentModFile.priority)

		# Look for override-required files that weren't overridden
		for key, value in filesDict.items():
			if value.url is not None:
				continue
			candidates = [x for x in self.subModConfig.fileOverrides if x.name == key and common.Globals.OS_STRING in x.os]
			raise FailedFileOverrideException(key, candidates, unity=unityVersion, steam=self.isSteam)

		# Pre-sort by the file's native order, to ensure deterministic ordering for files with the same priority
		overriddenFiles = sorted(filesDict.values(), key=lambda x: x.nativeOrder)

		# sort the priority from Lowest to Highest (eg items with priority '0' will always be at start of the list)
		# this is because the low priority items should be extracted first, so the high priority items can overwrite them.
		return sorted(overriddenFiles, key=lambda x: x.priority)

# NOTE: the 'priority' indicates the order of extraction:
# Files are extracted in order 0,1,2,3 ...
# Therefore, the 'later extracted' files are higher priority, that is archives with priority 3 will overwrite priority 0,1,2 archives
class ModFile:
	modFileCounter = 0
	def __init__(self, name, url, priority):
		# type: (str, Optional[str], int) -> None
		self.name = name
		self.url = url
		self.priority = priority #consider renaming this "extractionOrder"?

		# This variable is used to provide ordering which roughly matches the ordering in the JSON file
		# to ensure files are downloaded and extracted in a deterministic manner
		self.nativeOrder = ModFile.modFileCounter
		ModFile.modFileCounter += 1

class ModFileOverride:
	def __init__(self, name, os, steam, unity, url):
		# type: (str, List[str], Optional[bool], Optional[str], str) -> None
		self.name = name # type: str
		self.os = os # type: List[str]
		"""This is an List, describing all operating systems where this override applies eg ["mac", "linux"]"""
		self.steam = steam	#type: Optional[bool]
		"""This can be 'None' if the override applies to both mac and steam"""
		self.unity = unity #type: Optional[str]
		self.url = url # type: str

class ModOption:
	def __init__(self, name, description, group, type, isRadio, data):
		self.id = group + ': ' + name # type: str # unique ID for each mod option, for example "SE Options-Old OST"
		self.name = name # type: str
		self.description = description # type: str
		"""A textual description of the mod option, only used for display"""
		self.group = group # type: str
		"""Defined at Group Level: This defines what named group the mod option is categorized under"""
		self.type = type # type: str
		"""Defined at Group Level: This is the type of mod option. It can be used instead of the (group, name) pair to filter out actions.
		For example, all mod options of type 'downloadAndExtract' type should contain a 'url' and 'relativeExtractionPath'
		field in their data dictionary, and thus can be processed in python the same way."""
		self.isRadio = isRadio # type: bool
		"""Defines whether the option is """
		self.data = data # type: dict
		"""This contains any data required to execute this mod option. It is deliberately an untyped dict to
		accommodate various kinds of fields/data required by various kinds of options. You must refer to the JSON to
		check what kinds of values it contains for a given type of mod option."""
		self.value = False # type: bool
		"""This represents whether the user has enabled or disabled this mod option"""

	def __repr__(self):
		return "Option ID: [{}] Value: [{}]".format(self.id, self.value)

class DownloadAndExtractOption:
	def __init__(self, name, description, url, relativeExtractionPath, priority):
		self.name = name # type: str
		self.description = description # type: str
		self.url = url # type: str
		self.relativeExtractionPath = relativeExtractionPath # type: str
		self.priority = priority # type: int

class ModOptionParser:
	def __init__(self, fullInstallConfiguration):
		self.config = fullInstallConfiguration # type: FullInstallConfiguration
		self.downloadAndExtractOptionsByPriority = [] # type: List[DownloadAndExtractOption]

		# Sort according to priority - higher priority items will be extracted later, overwriting lower priority items.
		print('MOD OPTIONS:\n')
		for modOption in self.config.subModConfig.modOptions:
			print('  - {}'.format(modOption))
			if modOption.value:
				if modOption.type == 'downloadAndExtract' and modOption.data is not None:
					self.downloadAndExtractOptionsByPriority.append(
						DownloadAndExtractOption(
							modOption.name,
							modOption.description,
							modOption.data['url'],
							modOption.data['relativeExtractionPath'],
							modOption.data['priority']
						)
					)

		# Make sure download and extraction options are sorted
		self.downloadAndExtractOptionsByPriority.sort(key=lambda opt: opt.priority)

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
		self.descriptionID = subMod['descriptionID'] # type: str
		"""This variable sets which description to display on the web GUI
		The actual description text is stored on the webpage, not in the JSON or python side."""
		self.downloadSize = subMod['downloadSize']

		self.files = [] # type: List[ModFile]
		for subModFile in subMod['files']:
			self.files.append(ModFile(name=subModFile['name'], url = subModFile.get('url'), priority=subModFile['priority']))

		self.fileOverrides = [] # type: List[ModFileOverride]
		for subModFileOverride in subMod['fileOverrides']:
			self.fileOverrides.append(ModFileOverride(
				name=subModFileOverride['name'],
				os=subModFileOverride['os'],
				steam=subModFileOverride.get('steam'),
				unity=subModFileOverride.get('unity'),
				url=subModFileOverride['url']
			))

		# If no mod options are specified in the JSON, the 'self.modOptions' field defaults to the empty list ([])
		self.modOptions = [] # type: List[ModOption]

		def jsonAddModOptionsFromList(jsonModOptionList, isRadio):
			for jsonModOption in jsonModOptionList:
				self.modOptions.append(ModOption(name=jsonModOption['name'],
				                                 description=jsonModOption['description'],
				                                 group=jsonModOptionGroup['name'],
				                                 type=jsonModOptionGroup['type'],
				                                 isRadio=isRadio,
				                                 data=jsonModOption.get('data', None)))

		for jsonModOptionGroup in mod.get('modOptionGroups', []):
			applicableSubMods = jsonModOptionGroup.get('submods')
			if applicableSubMods is None or self.subModName in applicableSubMods:
				jsonAddModOptionsFromList(jsonModOptionGroup.get('radio', []), isRadio=True)
				jsonAddModOptionsFromList(jsonModOptionGroup.get('checkBox', []), isRadio=False)

	def __repr__(self):
		return "Type: [{}] Game Name: [{}]".format(self.modName, self.subModName)

	# Submod lists may contain many entries with the same modName (eg a list may have [umi-question:voice, umi-question:full, umi-question:full])
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

	allSteamPaths = []
	try:
		registryKey = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam')
		defaultSteamPath, _regType = winreg.QueryValueEx(registryKey, 'SteamPath')
		allSteamPaths.append(defaultSteamPath)
		winreg.CloseKey(registryKey)
	except WindowsError:
		print("findPossibleGamePaths: Couldn't read Steam registry key - Steam not installed?")
		return []

	# now that we know the steam path, search the "Steam\config\config.vdf" file for extra install paths
	# this is a purely optional step, so it's OK if it fails
	try:
		import io
		baseInstallFolderRegex = re.compile(r'^\s*"BaseInstallFolder_\d+"\s*"([^"]+)"', re.MULTILINE)
		steamConfigVDFLocation = os.path.join(defaultSteamPath, r'config\config.vdf')
		with io.open(steamConfigVDFLocation, 'r', encoding='UTF-8') as configVDFFile:
			allSteamPaths += baseInstallFolderRegex.findall(configVDFFile.read())
	except Exception as e:
		traceback.print_exc()

	print("Will scan the following steam install locations: ", allSteamPaths)

	# normpath added so returned paths have consistent slash directions (registry key has forward slashes on Win...)
	try:
		allPossibleGamePaths = []

		for steamCommonPath in (os.path.join(steamPath, r'steamapps\common') for steamPath in allSteamPaths):
			for gameFolderName in os.listdir(steamCommonPath):
				allPossibleGamePaths.append(
					os.path.normpath(
						os.path.join(steamCommonPath, gameFolderName)
					)
				)

		return allPossibleGamePaths
	except:
		print("findPossibleGamePaths: Couldn't open registry key folder - Steam folder deleted?")
		return []

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
					.check_output(["mdfind", "kMDItemContentType == com.apple.application-bundle && ** == '*Higurashi*'"])
					.decode("utf-8")
					.split("\n") if x
			)
		elif gameName == "Umineko":
			for gamePath in subprocess.check_output(["mdfind", "kMDItemContentType == com.apple.application-bundle && ** == '*Umineko*'"]).decode("utf-8").split("\n"):
				# GOG installer makes a `.app` that contains the actual game at `/Contents/Resources/game`
				gogPath = os.path.join(gamePath, "Contents/Resources/game")
				if os.path.exists(gogPath):
					allPossibleGamePaths.append(gogPath)
		else:
			print("Warning: ran findPossibleGamePaths with an unknown game")

		# add all files in the default steam common folder for Mac
		try:
			steamCommonPath = "~/Library/Application Support/Steam/steamapps/common/"
			for gameFolderName in os.listdir(steamCommonPath):
				allPossibleGamePaths.append(
					os.path.normpath(
						os.path.join(steamCommonPath, gameFolderName)
					)
				)
		except:
			print("Warning: MacOS - failed to add default steam common folder paths")

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


def scanForFullInstallConfigs(subModConfigList, possiblePaths=None, scanExtraPaths=True):
	# type: (List[SubModConfig], [str], bool) -> [FullInstallConfiguration]
	"""
	This function has two purposes:
		- When given a specific game path ('possiblePaths' argument), it checks if any of the given SubModConfig
		  can be installed into that path. Each SubModConfig which can be installed into that path will be returned
		  as a FullInstallConfiguration object.

		- When not given a specific game path, it searches the computer for valid installations where the given
		  SubModConfig could be installed to. Each valid (installation + SubModConfig) combination will be returned
		  as a FullInstallConfiguration object.

	:param subModConfigList: A **list** of SubModConfig which are to be searched for on disk
	:param possiblePaths: (Optional) Specify folders to check if the given SubModConfig can be installed into that path.
	:return:    A list of FullInstallConfig, each representing a valid install path that the
				given SubModConfig(s) couldbe installed into.
	"""

	returnedFullConfigs = []
	pathsToBeScanned = possiblePaths

	if not pathsToBeScanned:
		pathsToBeScanned = getMaybeGamePaths()

	# Build a mapping from subModIdentifier -> List[subMod]
	# This tells us, for each identifier, which subMods are compatible with that identifier (can be installed)
	# In all our games, the identifiers are the same for each subMod (but different for each Mod),
	# but it is easier to work with in the installer if we work with subMods

	from collections import defaultdict
	subModConfigDictionary = defaultdict(list) #type: defaultdict[List[SubModConfig]]
	for subMod in subModConfigList:
		for identifier in subMod.identifiers:
			subModConfigDictionary[identifier].append(subMod)

	if scanExtraPaths:
		extraPaths = []
		for gamePath in pathsToBeScanned:
			# MacOS: Any subpath with '.app' is also checked in case the containing path was manually entered
			extraPaths.extend(glob.glob(os.path.join(gamePath, "*.app")))
			# GOG Linux: Higurashi might be inside a 'game' subfolder
			extraPaths.extend(glob.glob(os.path.join(gamePath, "game")))

		pathsToBeScanned += extraPaths

	print("Scanning:\n\t- " + "\n\t- ".join(pathsToBeScanned))

	for gamePath in pathsToBeScanned:
		possibleIdentifiers = getPossibleIdentifiersFromPath(gamePath)
		subModConfigsInThisGamePath = set()
		for possibleIdentifier in possibleIdentifiers:
			try:
				possibleSteamPaths = [
					os.path.join(gamePath, "steam_api.dll"),
					os.path.join(gamePath, "Contents/Plugins/CSteamworks.bundle"),
					os.path.join(gamePath, "libsteam_api.so")
				]

				isSteam = False
				for possibleSteamPath in possibleSteamPaths:
					if os.path.exists(possibleSteamPath):
						isSteam = True

				# Add each submod which is compatible with the found identifier, unless it has already been detected at this path.
				for subModConfig in subModConfigDictionary[possibleIdentifier]:
					if subModConfig not in subModConfigsInThisGamePath:
						subModConfigsInThisGamePath.add(subModConfig)
						returnedFullConfigs.append(FullInstallConfiguration(subModConfig, gamePath, isSteam))
						print("Successfully detected game using identifier [{}] in [{}]".format(possibleIdentifier, gamePath))

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
	:param gameExecutablePath: A path to the game executable, or to a folder containing the game.
	:return: A tuple - The first is an array of valid FullInstallConfigurations.
					 - The second is an error message (on success a 'success' message is generated)
	"""
	if gameExecutablePath:
		if os.path.isfile(gameExecutablePath):
			gameExecutablePath = os.path.dirname(gameExecutablePath)

		# Search upwards for the game path, in case user has selected a deep subfolder of the game path
		alreadyScanned = set()
		for scanAttempt in range(10):
			fullInstallConfigs = scanForFullInstallConfigs(subModConfigList=subModConfigList,
			                                               possiblePaths=[gameExecutablePath],
			                                               scanExtraPaths= scanAttempt==0)
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
