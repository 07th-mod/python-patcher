import json

import commandLineParser
import common
import os, os.path as path, shutil, subprocess, glob

########################################## Installer Functions  and Classes ############################################
import gui
import gameScanner


class Installer:
	def __init__(self, fullInstallConfiguration):
		# type: (gameScanner.FullInstallConfiguration) -> None

		"""
		Installer Init

		:param str directory: The directory of the game
		:param dict info: The info dictionary from server JSON file for the requested target
		"""
		self.info = fullInstallConfiguration
		self.directory = fullInstallConfiguration.installPath

		if common.Globals.IS_MAC:
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
		self.downloadDir = self.info.subModConfig.modName + " Downloads"
		self.extractDir = self.info.subModConfig.modName + " Extraction"

		self.downloaderAndExtractor = common.DownloaderAndExtractor(modFileList=self.info.buildFileListSorted(datadir=self.dataDirectory),
		                                                            downloadTempDir=self.downloadDir,
		                                                            extractionDir=self.extractDir)

		self.downloaderAndExtractor.buildDownloadAndExtractionList()

		parser = gameScanner.ModOptionParser(self.info)

		for opt in parser.downloadAndExtractOptionsByPriority:
			self.downloaderAndExtractor.addItemManually(
				url=opt.url,
				extractionDir=os.path.join(self.extractDir, opt.relativeExtractionPath),
			)

		self.downloaderAndExtractor.printPreview()

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

	def moveFilesIntoPlace(self):
		"""
		Moves files from the directory they were extracted to
		to the game data folder
		"""
		self._moveDirectoryIntoPlace(
			fromDir = os.path.join(self.extractDir, self.info.subModConfig.dataName),
			toDir = self.dataDirectory
		)
		if common.Globals.IS_WINDOWS:
			self._moveFileIntoPlace(
				fromPath = os.path.join(self.extractDir, self.info.subModConfig.dataName[:-5] + ".exe"),
				toPath = self.directory
			)
		elif common.Globals.IS_MAC:
			self._moveFileIntoPlace(
				fromPath = os.path.join(self.extractDir, "Contents/Resources/PlayerIcon.icns"),
				toPath = os.path.join(self.directory, "Contents/Resources/PlayerIcon.icns")
			)


	def _moveDirectoryIntoPlace(self, fromDir, toDir):
		# type: (str, str) -> None
		"""
		Recursive function that does the actual moving for `moveFilesIntoPlace`
		"""
		for file in os.listdir(fromDir):
			src = path.join(fromDir, file)
			target = path.join(toDir, file)
			if path.isdir(src):
				if not path.exists(target):
					os.mkdir(target)
				self._moveDirectoryIntoPlace(fromDir=src, toDir=target)
			else:
				if path.exists(target):
					os.remove(target)
				shutil.move(src, target)
		os.rmdir(fromDir)

	def _moveFileIntoPlace(self, fromPath, toPath):
		# type: (str, str) -> None
		"""
		Moves a single file from `fromPath` to `toPath`
		"""
		if path.exists(fromPath):
			if path.exists(toPath):
				os.remove(toPath)
			shutil.move(fromPath, toPath)

	def cleanup(self):
		"""
		General cleanup and other post-install things

		Removes downloaded 7z files
		On mac, modifies the application Info.plist with new values if available
		"""
		try:
			shutil.rmtree(self.downloadDir)
			shutil.rmtree(self.extractDir)
		except OSError:
			pass

		if common.Globals.IS_MAC:
			# Allows fixing up application Info.plist file so that the titlebar doesn't show `Higurashi01` as the name of the application
			# Can also add a custom CFBundleIdentifier to change the save directory (e.g. for Console Arcs)
			infoPlist = path.join(self.directory, "Contents/Info.plist")
			infoPlistJSON = subprocess.check_output(["plutil", "-convert", "json", "-o", "-", infoPlist])
			parsed = json.loads(infoPlistJSON)

			configCFBundleName = self.info.subModConfig.CFBundleName
			if configCFBundleName and parsed["CFBundleName"] != configCFBundleName:
				subprocess.call(["plutil", "-replace", "CFBundleName", "-string", configCFBundleName, infoPlist])

			configCFBundleIdentifier = self.info.subModConfig.CFBundleIdentifier
			if configCFBundleIdentifier and parsed["CFBundleIdentifier"] != configCFBundleIdentifier:
				subprocess.call(["plutil", "-replace", "CFBundleIdentifier", "-string", configCFBundleIdentifier, infoPlist])

def main(fullInstallConfiguration):
	# type: (gameScanner.FullInstallConfiguration) -> None
	installer = Installer(fullInstallConfiguration)
	print("Downloading...")
	installer.download()
	print("Extracting...")
	installer.extractFiles()
	commandLineParser.printSeventhModStatusUpdate(85, "Moving files into place...")
	installer.backupUI()
	installer.cleanOld()
	installer.moveFilesIntoPlace()
	commandLineParser.printSeventhModStatusUpdate(97, "Cleaning up...")
	installer.cleanup()
	commandLineParser.printSeventhModStatusUpdate(100, "Install Completed!")
