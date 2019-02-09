from common import *

#contains all the install information required to install the game to a given path
class FullInstallConfiguration:
	def __init__(self, subModConfig, path, isSteam):
		# type: (SubModConfig, str, bool) -> FullInstallConfiguration
		self.subModConfig = subModConfig
		self.installPath = path
		self.isSteam = isSteam
		self.useIPV6 = False

	#applies the fileOverrides to the files to
	def buildFileListSorted(self):
		#convert the files list into a dict
		filesDict = {}
		for file in self.subModConfig.files:
			filesDict[file.name] = file

		for fileOverride in self.subModConfig.fileOverrides:
			#skip overrides where OS doesn't match
			if OS_STRING not in fileOverride.os:
				continue

			#skip overrides where isSteam doesn't match (NOTE: 'steam' can be null, which means that any type is acceptable
			if fileOverride.steam and fileOverride.steam != self.isSteam:
				continue

			#for all other overrides, overwrite the value in the filesDict with a new ModFile
			currentModFile = filesDict[fileOverride.name]
			filesDict[fileOverride.name] = ModFile(currentModFile.name, fileOverride.url, currentModFile.priority)

		#sort the priority from Lowest to Highest (eg items with priority '0' will always be at start of the list)
		#this is because the low priority items should be extracted first, so the high priority items can overwrite them.
		return sorted(filesDict.values(), key=lambda x: x.priority)

# NOTE: the 'priority' indicates the order of extraction:
# Files are extracted in order 0,1,2,3 ...
# Therefore, the 'later extracted' files are higher priority, that is archives with priority 3 will overwrite priority 0,1,2 archives
class ModFile:
	def __init__(self, name, url, priority):
		self.name = name
		self.url = url
		self.priority = priority #consider renaming this "extractionOrder"?

class ModFileOverride:
	def __init__(self, name, os, steam, url):
		# type: (str, [], Optional[bool], str) -> None
		self.name = name
		self.os = os #note: this is an ARRAY, eg ["mac", "linux"]
		self.steam = steam	#this can be 'none' if the override applies to both mac and steam
		self.url = url

#directly represents a single submod from the json file
class SubModConfig:
	#object initialized in factory func
	def __init__(self, mod, submod):
		self.family = mod['family']
		self.modName = mod['name']
		self.target = mod['target']
		self.CFBundleName = mod['CFBundleName']
		self.CFBundleIdentifier = mod['CFBundleIdentifier']
		self.dataName = mod['dataname']
		self.identifiers = mod['identifiers']
		self.subModName = submod['name']

		self.files = []
		for subModFile in submod['files']:
			self.files.append(ModFile(name=subModFile['name'], url = subModFile['url'], priority=subModFile['priority']))

		self.fileOverrides = []
		for subModFileOverride in submod['fileOverrides']:
			self.fileOverrides.append(ModFileOverride(name=subModFileOverride['name'], os=subModFileOverride['os'], steam=subModFileOverride['steam'], url=subModFileOverride['url']))

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

	if IS_WINDOWS:
		allPossibleGamePaths.extend(findPossibleGamePathsWindows())

	if IS_MAC:
		# mdfind is kind of slow, don't run it more than we have to
		allPossibleGamePaths.extend(
			x for x in subprocess
				.check_output(["mdfind", "kind:Application", "Higurashi"])
				.decode("utf-8")
				.split("\n") if x
		)

		for gamePath in subprocess.check_output(["mdfind", "kind:Application", "Umineko"]).decode("utf-8").split(
					"\n"):
				# GOG installer makes a `.app` that contains the actual game at `/Contents/Resources/game`
				gogPath = path.join(gamePath, "Contents/Resources/game")
				if path.exists(gogPath):
					allPossibleGamePaths.append(gogPath)

	# if all methods fail, return empty list
	return sorted(allPossibleGamePaths)

# Returns a full install config if the given sub mod can be installed to the given path
# otherwise returns None if the sub mod is incompatible
# The "gamePathContentsSet" argument is a set containing the
def subModCompatibleWithPath(subModConfig, gamePath, gamePathContentsSet):
	# type: (SubModConfig, str, set) -> bool

	# Higurashi Mac
	if IS_MAC and subModConfig.family == 'higurashi':
		try:
			info = subprocess.check_output(
				["plutil", "-convert", "json", "-o", "-", path.join(gamePath, "Contents/Info.plist")])
			parsed = json.loads(info)
			name = parsed["CFBundleExecutable"] + "_Data"
			if name in subModConfig.identifiers:
				return True
		except (OSError, KeyError):
			return False
	else:
		# All other configurations
		for identifier in subModConfig.identifiers:
			if identifier in gamePathContentsSet:
				return True

	return False


# Returns a list of all possible submods that can be installed on the system.
def scanForFullInstallConfigs(subModConfigList, possiblePaths=None):
	# type: ([], [str]) -> []
	returnedFullConfigs = []
	if not possiblePaths:
		possiblePaths = getMaybeGamePaths()

	for gamePath in possiblePaths:
		# the contents of each game path is cached for better performance
		gamePathContentsSet = set(os.listdir(gamePath))

		for subModConfig in subModConfigList:
			if subModCompatibleWithPath(subModConfig, gamePath, gamePathContentsSet):
				# check whether path is steam or mangagamer type
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

	return returnedFullConfigs
