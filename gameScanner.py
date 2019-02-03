from common import *

#contains all the install information required to install the game to a given path
class FullInstallConfiguration:
	def __init__(self, subModConfig, path):
		self.path = path
		self.subModConfig = subModConfig

class ModFile:
	def __init__(self, name, url, priority):
		self.name = name
		self.url = url
		self.priority = priority

class ModFileOverride:
	def __init__(self, name, os, steam, url):
		self.name = name
		self.os = os
		self.steam = steam
		self.url = url

#directly represents a single submod from the json file
class SubModConfig:
	#object initialized in factory func
	def __init__(self, mod, submod):
		self.family = mod['family']
		self.modname = mod['name']
		self.target = mod['target']
		self.CFBundleName = mod['CFBundleName']
		self.dataname = mod['dataname']
		self.submodname = submod['name']

		self.files = []
		for submodFile in submod['files']:
			self.files.append(ModFile(name=submodFile['name'], url = submodFile['url'], priority=submodFile['priority']))

		self.fileOverrides = []
		for submodFileOverride in submod['fileOverrides']:
			self.fileOverrides.append(ModFileOverride(name=submodFileOverride['name'], os=submodFileOverride['os'], steam=submodFileOverride['steam'], url=submodFileOverride['url']))

	def __repr__(self):
		return "Type: [{}] Game Name: [{}]".format(self.modname, self.submodname)


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
def tryGetFullInstallConfigurationFromPath(subModConfig, gamePath, gamePathContentsSet):
	# type: (SubModConfig, str, set) -> Optional[FullInstallConfiguration]

	# Higurashi Mac
	if IS_MAC and subModConfig.family == 'higurashi':
		try:
			info = subprocess.check_output(
				["plutil", "-convert", "json", "-o", "-", path.join(gamePath, "Contents/Info.plist")])
			parsed = json.loads(info)
			name = parsed["CFBundleExecutable"] + "_Data"
			if name == subModConfig.dataname:
				return FullInstallConfiguration(subModConfig, gamePath)
		except (OSError, KeyError):
			return None

	# All other configurations
	if subModConfig.dataname in gamePathContentsSet:
		return FullInstallConfiguration(subModConfig, gamePath)
	else:
		return None

# Returns a list of all possible submods that can be installed on the system.
def scanForFullInstallConfigs(subModConfigList):
	# type: ([]) -> []
	returnedFullConfigs = []
	possiblePaths = getMaybeGamePaths()

	for path in possiblePaths:
		#the contents of each game path is cached for better performance
		gamePathContentsSet = set(os.listdir(path))

		for subModConfig in subModConfigList:
			fullInstallConfig = tryGetFullInstallConfigurationFromPath(subModConfig, path, gamePathContentsSet)
			if fullInstallConfig:
				returnedFullConfigs.append(fullInstallConfig)

	return returnedFullConfigs