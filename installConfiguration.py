from __future__ import unicode_literals

import os
import hashlib
import common
from datetime import datetime

try:
	from typing import List, Optional, Dict, Set, Tuple
except:
	pass # Just needed for pycharm comments


def getSHA256(path):
	"""Gets the SHA256 Hex digest of a file at path as a string,
	e.g. '9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08'"""
	with open(path, "rb") as file:
		m = hashlib.sha256()
		m.update(file.read())
		return m.hexdigest()

def getUnityVersion(datadir, verbosePrinting=True):
	# type: (str, bool) -> str
	"""
	Given the datadir of a Higurashi game (like 'HigurashiEp0X_Data'), returns the unity version of the game
	Raises an exeption if:
	- The `HigurashiEp0X_Data/resources.assets` file is missing (raises MissingAssetsBundleException)
	- The `HigurashiEp0X_Data/resources.assets` bundle failed to open (raises error from open() call or read() call)
	- The Unity version was too old (raises OldUnityException)
	"""
	assetsbundlePath = os.path.join(datadir, "resources.assets")
	if not os.path.exists(assetsbundlePath):
		raise MissingAssetsBundleException(assetsbundlePath)

	with open(assetsbundlePath, "rb") as assetsBundle:
		unityVersion = assetsBundle.read(28)[20:].decode("utf-8").rstrip("\0")
		if verbosePrinting:
			print("Unity Version: Read [{}] from [{}]".format(unityVersion, assetsbundlePath))
		if int(unityVersion.split('.')[0]) < 5:
			raise OldUnityException(unityVersion)
		return unityVersion

def higurashiWindowsExecutableExists(dataName, installPath):
	# type: (str, str) -> bool
	windowsExeName = dataName.split('_')[0] + ".exe"
	windowsExePath = os.path.join(installPath, windowsExeName)
	isProtonOrWindows = os.path.exists(windowsExePath)

	print("Checking [{}] for Windows Executable".format(windowsExePath))

	return isProtonOrWindows

def checkChecksumListMatches(installPath, checksumList):
	#type: (str, List[(str, str)]) -> bool
	"""Returns true if any checksum in the checksum list matches"""
	for relativePath, checksum in checksumList:
		path = os.path.join(installPath, relativePath)
		if not os.path.exists(path):
			print("checkChecksumListMatches(): File at {} does not exist, skipping this file".format(path))
			continue

		actualChecksum = getSHA256(path)

		if actualChecksum.lower() == checksum.lower():
			print("checkChecksumListMatches(): File at {} has matching checksum {}".format(path, actualChecksum))
			return True
		else:
			print("checkChecksumListMatches(): File at {} has wrong checksum {} (expected {})".format(path, actualChecksum, checksum))
			continue

	return False

class FullInstallConfiguration:
	# contains all the install information required to install the game to a given path

	def __init__(self, subModConfig, path, isSteam):
		# type: (SubModConfig, str, bool) -> None
		self.subModConfig = subModConfig # type: SubModConfig
		self.installPath = path # type: str
		self.isSteam = isSteam # type: bool
		self.useIPV6 = False
		self.unityVersion = None

		if self.subModConfig.family == "higurashi" and common.Globals.IS_LINUX and higurashiWindowsExecutableExists(self.subModConfig.dataName, self.installPath):
			self.isWine = True
		else:
			self.isWine = False

	#applies the fileOverrides to the files to
	def buildFileListSorted(self, datadir="", verbosePrinting=True):
		# type: (Optional[str], Optional[bool]) -> List[ModFile]
		# convert the files list into a dict
		osString = common.Globals.OS_STRING
		if common.Globals.FORCE_ASSET_OS_STRING is not None:
			osString = common.Globals.FORCE_ASSET_OS_STRING
		elif self.isWine:
			osString = "windows"

		filesDict = {}
		for file in self.subModConfig.files:
			filesDict[file.name] = file

		if datadir:
			unityVersion = getUnityVersion(datadir, verbosePrinting)
		else:
			unityVersion = None
			if verbosePrinting:
				print("Unity Version: [{}/Not a Unity game]".format(unityVersion))

		for fileOverride in self.subModConfig.fileOverrides:
			if self.isWine and fileOverride.wine:
				if verbosePrinting:
					print("Forcing install of {} on {} because wine mode enabled".format(fileOverride.id, osString))
			else:
				# skip overrides where OS/wine doesn't match
				if osString not in fileOverride.os:
					continue

			# skip overrides where isSteam doesn't match (NOTE: 'steam' can be null, which means that any type is acceptable
			if fileOverride.steam is not None and fileOverride.steam != self.isSteam:
				continue

			if fileOverride.unity is not None and fileOverride.unity != unityVersion:
				continue

			# If the file has some checksum requirements, check whether the files exist/match the required checksums
			# If datadir is defined, use the datadir (Higurashi), otherwise use the install path (other games)
			if fileOverride.targetChecksums is not None:
				if not checkChecksumListMatches(datadir if datadir else self.installPath, fileOverride.targetChecksums):
					continue

			# for all other overrides, overwrite the value in the filesDict with a new ModFile
			currentModFile = filesDict[fileOverride.name]
			filesDict[fileOverride.name] = ModFile(currentModFile.name, fileOverride.url, currentModFile.priority, id=fileOverride.id, relativeExtractionPath=fileOverride.relativeExtractionPath, installOnRepair=currentModFile.installOnRepair, requirementsList=currentModFile.requirementsList)

		# Look for override-required files that weren't overridden
		for key, value in filesDict.items():
			if value.url is not None:
				continue
			candidates = [x for x in self.subModConfig.fileOverrides if x.name == key and osString in x.os]
			raise FailedFileOverrideException(key, candidates, unity=unityVersion, steam=self.isSteam)

		# Save the unity version for future use
		self.unityVersion = unityVersion

		# Pre-sort by the file's native order, to ensure deterministic ordering for files with the same priority
		overriddenFiles = sorted(filesDict.values(), key=lambda x: x.nativeOrder)

		# sort the priority from Lowest to Highest (eg items with priority '0' will always be at start of the list)
		# this is because the low priority items should be extracted first, so the high priority items can overwrite them.
		return sorted(overriddenFiles, key=lambda x: x.priority)


class ModFile:
	modFileCounter = 0
	def __init__(self, name, url, priority, id=None, relativeExtractionPath=None, skipIfModNewerThan=None, installOnRepair=False, requirementsList=None):
		# type: (str, Optional[str], int, str, Optional[str], Optional[str], Optional[bool], Optional[List[str]]) -> None
		self.name = name
		self.url = url

		self.id = self.name if id is None else id

		# NOTE: the 'priority' indicates the order of extraction:
		# Files are extracted in order 0,1,2,3 ...
		# Therefore, the 'later extracted' files are higher priority, that is archives with priority 3 will overwrite priority 0,1,2 archives
		self.priority = priority #consider renaming this "extractionOrder"?

		# A path relative to the *top-level game directory* (should contain HigurashiEp##_data for a higurashi game's data folder)
		self.relativeExtractionPath = relativeExtractionPath # type: str

		# Do not apply this file if the last mod installation was newer than this date
		# Once Python 2 support is removed, we should use datetime.fromisoformat() instead of datetime.strptime()
		if skipIfModNewerThan is None:
			self.skipIfModNewerThan = None
		else:
			self.skipIfModNewerThan = datetime.strptime(skipIfModNewerThan, '%Y-%m-%d')

		# This variable is used to provide ordering which roughly matches the ordering in the JSON file
		# to ensure files are downloaded and extracted in a deterministic manner
		self.nativeOrder = ModFile.modFileCounter
		ModFile.modFileCounter += 1

		# Files where this is set to True will always be installed when installer is run in 'repair' mode
		# These are generally small files which might be overwritten by Steam an other game manager
		self.installOnRepair = installOnRepair

		self.requirementsList = requirementsList # type: Optional[List[str]]
		"""A list of various requirements determining whether the file will be installed"""

class ModFileOverride:
	def __init__(self, name, id, os, steam, unity, url, targetChecksums, relativeExtractionPath=None, wine=None):
		# type: (str, str, List[str], Optional[bool], Optional[str], str, List[Tuple[str, str]], Optional[str], Optional[bool]) -> None
		self.name = name # type: str
		self.id = id
		"""A unique identifier among all files and modfiles for this submod. Set manually as 'movie-unix' for example"""
		self.os = os # type: List[str]
		"""This is an List, describing all operating systems where this override applies eg ["mac", "linux"]"""
		self.steam = steam	#type: Optional[bool]
		"""This can be 'None' if the override applies to both mac and steam"""
		self.unity = unity #type: Optional[str]
		self.url = url # type: str
		self.targetChecksums = targetChecksums # type: List[Tuple[str, str]]
		"""This field can be None for no checksum checking.
		This field consists of a list of tuples. Each tuple is a pair of (PATH, CHECKSUM).
		If a file exists at PATH and matches CHECKSUM then this override will be accepted"""
		self.relativeExtractionPath = relativeExtractionPath  #type: Optional[str]
		"""A path relative to the *top-level game directory*
		(should contain HigurashiEp##_data for a higurashi game's data folder)"""
		self.wine = False if wine is None else wine #type: bool
		"""If set to True, this file override should be installed if the target install is using Wine or Proton
		even if the OS does not match"""

class ModOption:
	def __init__(self, name, description, group, type, isRadio, data, isGlobal=False, value=False):
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
		self.value = value # type: bool
		"""This represents whether the user has enabled or disabled this mod option"""
		self.isGlobal = isGlobal # type: bool
		"""Options which should be remembered/mirrored across different game families should be set as globalOptions
		For example, a 'download only' or 'french patch' option should be remembered across Umineko and Higurashi
		Options are considered 'the same' if they have the same id
		Note that options within the same family are automatically remembered/mirrored, regardless of this 'isGlobal' value
		"""
	def __repr__(self):
		return "Option ID: [{}] Value: [{}]".format(self.id, self.value)


class DownloadAndExtractOption:
	def __init__(self, name, description, url, relativeExtractionPath, priority, group):
		self.name = name # type: str
		self.description = description # type: str
		self.url = url # type: str
		self.relativeExtractionPath = relativeExtractionPath # type: str
		self.priority = priority # type: int
		self.group = group # type: str


class ModOptionParser:
	def __init__(self, fullInstallConfiguration):
		self.config = fullInstallConfiguration # type: FullInstallConfiguration
		self.downloadAndExtractOptionsByPriority = [] # type: List[DownloadAndExtractOption]
		self.keepDownloads = False
		self.installSteamGrid = False
		self.partialManualInstall = False
		self.repairMode = False
		self.downloadManually = False

		# Sort according to priority - higher priority items will be extracted later, overwriting lower priority items.
		for modOption in self.config.subModConfig.modOptions:
			if modOption.value:
				if modOption.type == 'downloadAndExtract' and modOption.data is not None:
					self.downloadAndExtractOptionsByPriority.append(
						DownloadAndExtractOption(
							modOption.name,
							modOption.description,
							modOption.data['url'],
							modOption.data['relativeExtractionPath'],
							modOption.data['priority'],
							modOption.group
						)
					)
				elif modOption.type == 'keepDownloads':
					self.keepDownloads = True
				elif modOption.type == 'installSteamGrid':
					self.installSteamGrid = True
				elif modOption.type == 'partialManualInstall':
					self.partialManualInstall = True
				elif modOption.type == 'repairMode':
					self.repairMode = True
				elif modOption.type == 'downloadManually':
					self.downloadManually = True

		# Make sure download and extraction options are sorted
		self.downloadAndExtractOptionsByPriority.sort(key=lambda opt: opt.priority)


class SubModConfig:
	# directly represents a single submod from the json file

	subModUniqueIDCounter = 0

	#object initialized in factory func
	def __init__(self, mod, subMod):
		# type: (dict, dict) -> None
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
		self.autodetect = mod.get('autodetect', True)
		"""When True, installer will attempt to autodetect game path. Defaults to True if not set."""

		self.files = [] # type: List[ModFile]
		for subModFile in subMod['files']:
			self.files.append(ModFile(
				name=subModFile['name'],
				url=subModFile.get('url'),
				priority=subModFile['priority'],
				relativeExtractionPath=subModFile.get('relativeExtractionPath'),
				skipIfModNewerThan=subModFile.get('skipIfModNewerThan'),
				installOnRepair=subModFile.get('installOnRepair', False),
				requirementsList=subModFile.get('requirementsList')
			))

		self.fileOverrides = [] # type: List[ModFileOverride]
		for subModFileOverride in subMod['fileOverrides']:
			self.fileOverrides.append(ModFileOverride(
				name=subModFileOverride['name'],
				os=subModFileOverride['os'],
				steam=subModFileOverride.get('steam'),
				unity=subModFileOverride.get('unity'),
				url=subModFileOverride['url'],
				id=subModFileOverride['id'],
				targetChecksums=subModFileOverride.get('targetChecksums'),
				relativeExtractionPath=subModFileOverride.get('relativeExtractionPath'),
				wine=subModFileOverride.get('wine')
			))

		# If no mod options are specified in the JSON, the 'self.modOptions' field defaults to the empty list ([])
		self.modOptions = [] # type: List[ModOption]

		def jsonAddModOptionsFromList(jsonModOptionList, isRadio):
			for i, jsonModOption in enumerate(jsonModOptionList):
				self.modOptions.append(ModOption(name=jsonModOption['name'],
				                                 description=jsonModOption['description'],
				                                 group=jsonModOptionGroup['name'],
				                                 type=jsonModOptionGroup['type'],
				                                 isRadio=isRadio,
				                                 data=jsonModOption.get('data', None),
				                                 isGlobal=jsonModOption.get('isGlobal', False),
				                                 value=True if isRadio and i == 0 else False))

		for jsonModOptionGroup in mod.get('modOptionGroups', []):
			applicableSubMods = jsonModOptionGroup.get('submods')
			if applicableSubMods is None or self.subModName in applicableSubMods:
				jsonAddModOptionsFromList(jsonModOptionGroup.get('radio', []), isRadio=True)
				jsonAddModOptionsFromList(jsonModOptionGroup.get('checkBox', []), isRadio=False)

		# Mod options which don't come from the installData.json file are added here
		installSteamGridDescription = """
<p>This option updates the header and icon art in the Steam app to match the mod's art style. All Higurashi and Umineko games will have their icons updated, not just the game being patched.</p>
<strong>NOTE: A computer restart may be required to see the updated art!</strong>

<table class="umineko-image-table-content umineko-image-table-horizontal">
<tbody>
	<tr>
	<td>Original</td>
		<td><img src="img/steamgrid/header-original.jpg"></td>
	</tr>
	<tr>
		<td>Updated</td>
		<td><img src="img/steamgrid/header-updated.jpg"></td>
	</tr>
</tbody>
</table>
"""
		if 'voiceonly' not in self.descriptionID.lower():
			self.modOptions.append(ModOption(name="Update Steamgrid Icons",
			                                 description=installSteamGridDescription,
			                                 group="Common Options",
			                                 type="installSteamGrid",
			                                 isRadio=False,
			                                 data=None,
			                                 isGlobal=True))

		# Only show 'partial manual install' options for Higurashi for now (Umineko partial install is not implemented)
		if self.family == 'higurashi':
			self.modOptions.append(ModOption(name="Partial Manual Install",
		                                 description="""Users who get a 'Permission Denied' error should use this option to install the mod.

Please watch the instructions on using this option: [https://www.youtube.com/watch?v=Px4JWsSycQE](https://www.youtube.com/watch?v=Px4JWsSycQE)

This makes the installer download and extract the mod files to a temporary folder (shown at the end of the install). After this, **you** have to manually copy the mod files to the game directory.

You also need to manually delete the temporary installer files (see end of video).""",
		                                 group="Experimental Options",
		                                 type="partialManualInstall",
		                                 isRadio=False,
		                                 data=None,
		                                 isGlobal=True))

		if self.family == 'higurashi' or self.family == 'umineko':
			self.modOptions.append(ModOption(name="Quick Repair",
			                                 description="""This option repairs your install by re-installing critical mod files. This is useful if:

- Steam updated your install, which overwrote some important mod files
- Enabling or Disabling Proton on Linux has broken your install.
    - On Linux, changing your "Steam Play Compatability Tool" (disabling or enabling Proton) will cause Steam to overwrite your mod files, causing a black screen on startup. Enable this option to fix this problem.
- In some cases, this will fix crashing on startup, or getting a black screen on startup

Make sure to select the same mod options you chose previously before using this option (for example, "French Language Patch"), as this option may overwrite them.
""",
			                                 group="Common Options",
			                                 type="repairMode",
			                                 isRadio=False,
			                                 data=None,
			                                 isGlobal=True))

		self.modOptions.append(ModOption(name="Download Manually",
		                                 description="""This option requires you to manually download the files for the installation.

If you're having problems downloading via the installer, you can use this option to bypass the download stage.

Please scroll down the page to the download preview table below, which will tell you what to download and where to put the downloads.

The files you manually downloaded will not be deleted automatically at the end of the install (in case you want to back them up).
""",
		                                 group="Common Options",
		                                 type="downloadManually",
		                                 isRadio=False,
		                                 data=None,
		                                 isGlobal=True))

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

	def printEnabledOptions(self):
		print('\nEnabled Mod Options:')

		numberEnabled = 0
		for modOption in self.modOptions:
			if modOption.value:
				print('  - {}: {}'.format(modOption.group, modOption.name))
				numberEnabled += 1

		if numberEnabled == 0:
			print(' - No options were enabled.')

		print()

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
		if candidate.targetChecksums is not None:
			if len(out) > 1:
				out += ", "
			out += "checksums: " + str(candidate.targetChecksums)

		return out + ")"

	def __str__(self):
		if not self.candidates:
			return "Your current OS is not supported by the file {} in this mod".format(self.name)
		hasUnity = any(x.unity is not None for x in self.candidates)
		out = "Please check your game is up-to-date. If it is fully up-to-date, please send the game log to the developers on our discord server."
		out += "\n\nFailed to find a {} file to use, your game has the properties (steam: {}".format(self.name, self.steam)
		if hasUnity:
			out += ", unity: {}".format(self.unity)
		out += ") but the available versions had the requirements " + ", ".join(self.describe(candidate) for candidate in self.candidates)
		return out


class MissingAssetsBundleException(Exception):
	def __init__(self, assetsbundlePath):
		# type: (str) -> None
		self.assetsbundlePath = assetsbundlePath  # type: str

	def __str__(self):
		return "Can't determine Unity version - missing `resources.assets` file [{}].\n\n" \
		       "You probably need to re-install the game, or ask for help on our Discord.".format(self.assetsbundlePath)
