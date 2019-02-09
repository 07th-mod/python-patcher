import json

from common import *
import os, os.path as path, shutil, subprocess, glob

########################################## Installer Functions  and Classes ############################################
from gameScanner import FullInstallConfiguration
from gui import InstallStatusWidget


class Installer:
	def __init__(self, fullInstallConfiguration, installStatusWidget):
		# type: (FullInstallConfiguration, InstallStatusWidget) -> None

		"""
		Installer Init

		:param str directory: The directory of the game
		:param dict info: The info dictionary from server JSON file for the requested target
		"""
		self.info = fullInstallConfiguration
		self.directory = fullInstallConfiguration.installPath

		if IS_MAC:
			self.dataDirectory = path.join(self.directory, "Contents/Resources/Data")
		else:
			self.dataDirectory = path.join(self.directory, self.info.subModConfig.dataName)

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

		#TODO: DROJF - Not sure if should use 'name' or 'target'. I have set the json such that 'name' is the descriptive name, 'target' is the target game to install to
		self.downloadDir = self.info.subModConfig.name + "Download"

		self.downloaderAndExtractor = DownloaderAndExtractor(self.info.buildFileListSorted(), self.downloadDir, self.downloadDir)

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
		self.downloaderAndExtractor.download()

	def extractFiles(self):
		self.downloaderAndExtractor.extract()

	def moveFilesIntoPlace(self, fromDir=None, toDir=None):
		"""
		Moves files from the directory they were extracted to
		to the game data folder

		fromDir and toDir are for recursion, leave them at their defaults to start the process
		"""
		if fromDir is None: fromDir = self.info.subModConfig.dataName
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
			configCFBundleName = self.info.subModConfig.CFBundleName
			configCFBundleIdentifier = self.info.subModConfig.CFBundleIdentifier
			# Allows fixing up application Info.plist file so that the titlebar doesn't show `Higurashi01` as the name of the application
			# Can also add a custom CFBundleIdentifier to change the save directory (e.g. for Console Arcs)
			infoPlist = path.join(self.directory, "Contents/Info.plist")
			infoPlistJSON = subprocess.check_output(["plutil", "-convert", "json", "-o", "-", infoPlist])
			parsed = json.loads(infoPlistJSON)
			if "CFBundleName" in self.info and parsed["CFBundleName"] != configCFBundleName:
				subprocess.call(["plutil", "-replace", "CFBundleName", "-string", configCFBundleName, infoPlist])
			if "CFBundleIdentifier" in self.info and parsed["CFBundleIdentifier"] != configCFBundleIdentifier:
				subprocess.call(["plutil", "-replace", "CFBundleIdentifier", "-string", configCFBundleIdentifier, infoPlist])

def main(rootWindow):
	# print("Getting latest mod info...")
	# modList = getModList("https://raw.githubusercontent.com/07th-mod/resources/master/higurashiInstallData.json")
	# foundGames = [path for path in findPossibleGamePaths("Higurashi") if getGameNameFromGamePath(path, modList) is not None]
	#
	# #gameToUse is the path to the game install directory, for example "C:\games\Steam\steamapps\common\Higurashi 02 - Watanagashi"
	# gameToUse = promptChoice(
	# 	rootGUIWindow = rootWindow,
	# 	choiceList=foundGames,
	# 	guiPrompt="Please choose a game to mod",
	# 	canOther=True
	# )
	#
	# #target name, for example 'Watanagashi', that the user has selected
	# targetName = getGameNameFromGamePath(gameToUse, modList)
	# if not targetName:
	# 	print(gameToUse + " does not appear to be a supported higurashi game.")
	# 	printSupportedGames(modList)
	# 	exitWithError()
	#
	# print("targetName", targetName)
	#
	# # Using the targetName (eg. 'Watanagashi'), check which mods have a matching name
	# # Multiple mods may be returned (eg the 'full' patch and 'voice only' patch may have the same 'target' name
	# possibleMods = [x for x in modList if x["target"] == targetName]
	# if len(possibleMods) > 1:
	# 	modName = promptChoice(
	# 		rootGUIWindow = rootWindow,
	# 		choiceList=[x["name"] for x in possibleMods],
	# 		guiPrompt="Please choose a mod to install")
	# 	mod = [x for x in possibleMods if x["name"] == modName][0]
	# else:
	# 	mod = possibleMods[0]

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
