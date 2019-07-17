import os

import common

try:
	from typing import List, Optional, Dict, Set
except:
	pass # Just needed for pycharm comments


class FullInstallConfiguration:
	# contains all the install information required to install the game to a given path

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
			filesDict[fileOverride.name] = ModFile(currentModFile.name, fileOverride.url, currentModFile.priority, id=fileOverride.id)

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


class ModFile:
	modFileCounter = 0
	def __init__(self, name, url, priority, id=None):
		# type: (str, Optional[str], int, str) -> None
		self.name = name
		self.url = url

		self.id = self.name if id is None else id

		# NOTE: the 'priority' indicates the order of extraction:
		# Files are extracted in order 0,1,2,3 ...
		# Therefore, the 'later extracted' files are higher priority, that is archives with priority 3 will overwrite priority 0,1,2 archives
		self.priority = priority #consider renaming this "extractionOrder"?

		# This variable is used to provide ordering which roughly matches the ordering in the JSON file
		# to ensure files are downloaded and extracted in a deterministic manner
		self.nativeOrder = ModFile.modFileCounter
		ModFile.modFileCounter += 1


class ModFileOverride:
	def __init__(self, name, id, os, steam, unity, url):
		# type: (str, str, List[str], Optional[bool], Optional[str], str) -> None
		self.name = name # type: str
		self.id = id
		"""A unique identifier among all files and modfiles for this submod. Set manually as 'movie-unix' for example"""
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


class SubModConfig:
	# directly represents a single submod from the json file

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
				url=subModFileOverride['url'],
				id=subModFileOverride['id']
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

		self.modVersionURL = subMod['modVersionURL']

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
