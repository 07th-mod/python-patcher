from common import *

class GameInstallConfig:
	#modOption: each game may have more than one mod option, specifying which files to use.
	# def __init__(self, gamePath, gameConfig, modOption):
	# 	self.type = gameConfig['type'] #high level game type, eg Higurashi or Umineko
	# 	self.name = gameConfig['name'] #the name of the game, which should match the name in the JSON file
	# 	self.path = gamePath #the path to the game
	# 	self.CFBundleName = gameConfig['CFBundleName']
	# 	self.dataname = gameConfig['dataname']
	# 	self.target = gameConfig['target']

	#object initialized in factory func
	def __init__(self):
		#these are only for type hinting
		self.type = None
		self.name = None
		self.path = None
		self.CFBundleName = None
		self.dataname = None
		self.target = None
		self.files = None
		self.os = None
		self.type = None

	def generateConfigs(gamePath, gameConfig):
		retModOptions = []

		for modOptionName, modOptionData in gameConfig['files'].items(): #'files' at this level is really mod options
			installConfig = GameInstallConfig()

			#this part is the same for each mod option
			installConfig.type = gameConfig['type'] #high level game type, eg Higurashi or Umineko
			installConfig.name = gameConfig['name'] #the name of the game, which should match the name in the JSON file
			installConfig.path = gamePath #the path to the game
			installConfig.CFBundleName = gameConfig['CFBundleName']
			installConfig.dataname = gameConfig['dataname']
			installConfig.target = gameConfig['target']

			#this part is different for each mod option
			installConfig.optionName = modOptionName
			installConfig.files = modOptionData['files']
			installConfig.os = modOptionData['os']
			installConfig.supportedVariants = modOptionData['supportedVariants']

			retModOptions.append(installConfig)

		return retModOptions

	def __repr__(self):
		return "Type: [{}] Game Name: [{}] Path: [{}]".format(self.type, self.name, self.path)

class GameScanner:
	def __init__(self, uminekoModList):
		self.uminekoModList = uminekoModList

	def scan(self):
		configList = []
		for gamePath in self.getAllPossibleGames():
			gameInstallConfig = self.getGameInstallConfigFromPath(gamePath)
			if gameInstallConfig is not None:
				configList.extend(gameInstallConfig)

		# print out all configurations, Not sure how to generate/remove valid configurations without having another class which holds the return values.
		debugPathToPrint = None
		for config in configList:
			if config.path != debugPathToPrint:
				print("Options for Path", config.path)
				debugPathToPrint = config.path

			option_valid = False
			if IS_WINDOWS and "win" in config.os or IS_LINUX and "linux" in config.os or IS_MAC and "mac" in config.os:
				option_valid = True

			valid_symbol = " "
			if option_valid:
				valid_symbol = "X"
			print("\t- [{}] {}: Supports {}".format(valid_symbol, config.optionName, config.os))

		return configList

	def getGameInstallConfigFromPath(self, path):
		# Given a game path, returns the corresponding game install information for that path
		# In the JSON, this is one of the elements of the top level array
		# It will return 'None' if the game path is invalid (not an Umineko game). Use this feature to scan for valid game paths.
		def getUminekoGameInformationFromGamePath(gamePath, modList):
			for uminekoGameInfo in modList:
				try:
					for filename in os.listdir(gamePath):
						if uminekoGameInfo['dataname'].lower() in filename.lower():
							return GameInstallConfig.generateConfigs(gamePath, uminekoGameInfo)
				except:
					print("getGameNameFromGamePath failed on path [{}]".format(gamePath))

			return None

		def getGameNameFromGamePathHigurashi(gamePath, modList):
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
					info = subprocess.check_output(
						["plutil", "-convert", "json", "-o", "-", path.join(gamePath, "Contents/Info.plist")])
					parsed = json.loads(info)
					name = parsed["CFBundleExecutable"] + "_Data"
				except (OSError, KeyError):
					return None
			else:
				# create a set data structure, containing all the mod data folder names
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
					return GameInstallConfig.generateConfigs(gamePath, mod)
			return None

		uminekoConfig = getUminekoGameInformationFromGamePath(path, self.uminekoModList)
		if uminekoConfig:
			return uminekoConfig

		higurashiConfig = getGameNameFromGamePathHigurashi(path, self.uminekoModList)
		if higurashiConfig:
			return higurashiConfig


		return None

	def getAllPossibleGames(self):
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
