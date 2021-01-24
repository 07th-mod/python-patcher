from __future__ import unicode_literals

import json
import re
import traceback

import commandLineParser
import common
import os, os.path as path, shutil, subprocess, glob, stat

########################################## Installer Functions  and Classes ############################################
import fileVersionManagement
import gameScanner
import installConfiguration
import logger
import steamGridExtractor

try:
	from typing import Optional
except:
	pass

def on_rm_error(func, path, exc_info):
	# path contains the path of the file that couldn't be removed
	# let's just assume that it's read-only and unlink it.
	os.chmod(path, stat.S_IWRITE)
	os.unlink(path)

# Remove a file, even if it's marked as readonly
def forceRemove(path):
	os.chmod(path, stat.S_IWRITE)
	os.remove(path)

def forceRemoveDir(path):
	os.chmod(path, stat.S_IWRITE)
	os.rmdir(path)

# Call shutil.rmtree, such that it even removes readonly files
def forceRmTree(path):
	shutil.rmtree(path, onerror=on_rm_error)

class Installer:
	def getDataDirectory(self, installPath):
		if common.Globals.IS_MAC:
			return path.join(installPath, "Contents/Resources/Data")
		else:
			return path.join(installPath, self.info.subModConfig.dataName)

	def __init__(self, fullInstallConfiguration, extractDirectlyToGameDirectory, modOptionParser, forcedExtractDirectory=None):
		# type: (installConfiguration.FullInstallConfiguration, bool, installConfiguration.ModOptionParser Optional[str]) -> None

		"""
		Installer Init

		:param str directory: The directory of the game
		:param dict info: The info dictionary from server JSON file for the requested target
		"""
		self.forcedExtractDirectory = forcedExtractDirectory
		self.info = fullInstallConfiguration
		self.directory = fullInstallConfiguration.installPath
		self.dataDirectory = self.getDataDirectory(self.directory)
		self.clearScripts = False  # If true, will clear CompiledUpdateScripts before extraction stage
		self.languagePatchIsEnabled = False  # True if at least one language patch will be installed

		logger.getGlobalLogger().trySetSecondaryLoggingPath(
			os.path.join(self.dataDirectory, common.Globals.LOG_BASENAME)
		)

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

		self.downloadDir = self.info.subModConfig.modName + " Downloads"
		self.extractDir = self.directory if extractDirectlyToGameDirectory else (self.info.subModConfig.modName + " Extraction")
		if forcedExtractDirectory is not None:
			self.extractDir = forcedExtractDirectory

		self.fileVersionManager = fileVersionManagement.VersionManager(
			subMod=self.info.subModConfig,
			modFileList=self.info.buildFileListSorted(datadir=self.dataDirectory),
			localVersionFolder=self.directory)

		modFileList = self.fileVersionManager.getFilesRequiringUpdate()

		for modFile in modFileList:
			if modFile.name == 'script':
				self.clearScripts = True

		self.info.subModConfig.printEnabledOptions()
		self.downloaderAndExtractor = common.DownloaderAndExtractor(modFileList=modFileList,
		                                                            downloadTempDir=self.downloadDir,
		                                                            extractionDir=self.extractDir)

		self.downloaderAndExtractor.buildDownloadAndExtractionList()

		self.optionParser = modOptionParser

		for opt in self.optionParser.downloadAndExtractOptionsByPriority:
			self.downloaderAndExtractor.addItemManually(
				url=opt.url,
				extractionDir=os.path.join(self.extractDir, opt.relativeExtractionPath),
			)
			if opt.group == 'Alternate Languages':
				self.clearScripts = True
				self.languagePatchIsEnabled = True

		self.downloaderAndExtractor.printPreview()

	def backupUI(self):
		"""
		Backs up the `sharedassets0.assets` file
		Try to do this in a transactional way so you can't get a half-copied .backup file.
		This is important since the .backup file is needed to determine which ui file to use on future updates

		The file is not moved directly in case the installer is halted before the new UI file can be placed, resulting
		in an install completely missing a sharedassets0.assets UI file.
		"""
		try:
			uiPath = path.join(self.dataDirectory, "sharedassets0.assets")

			# partialManualInstall is not really supported on MacOS, so just assume output folder is HigurashiEpX_Data
			if self.forcedExtractDirectory is not None:
				backupPath = path.join(self.forcedExtractDirectory, self.info.subModConfig.dataName, "sharedassets0.assets.backup")
			else:
				backupPath = path.join(self.dataDirectory, "sharedassets0.assets.backup")

			if path.exists(uiPath) and not path.exists(backupPath):
				shutil.copy(uiPath, backupPath + '.temp')
				os.rename(backupPath + '.temp', backupPath)
		except Exception as e:
			print('Error: Failed to backup sharedassets0.assets file: {} (need backup for future installs!)'.format(e))
			raise e

	def clearCompiledScripts(self):
		compiledScriptsPattern = path.join(self.assetsDir, "CompiledUpdateScripts/*.mg")

		print("Attempting to clear compiled scripts")
		try:
			for mg in glob.glob(compiledScriptsPattern):
				forceRemove(mg)
		except Exception:
			print('WARNING: Failed to clean up the [{}] compiledScripts'.format(compiledScriptsPattern))
			traceback.print_exc()

	def cleanOld(self):
		"""
		Removes folders that shouldn't persist through the install
		(CompiledUpdateScripts, CG, and CGAlt)
		"""
		oldCG = path.join(self.assetsDir, "CG")
		oldCGAlt = path.join(self.assetsDir, "CGAlt")

		if self.clearScripts:
			self.clearCompiledScripts()

		# Only delete the oldCG and oldCGAlt folders on a full update, as the CG pack won't always be extracted
		if self.fileVersionManager.fullUpdateRequired():
			print("Full Update Detected: Deleting old CG and CGAlt folders")
			try:
				if path.isdir(oldCG):
					forceRmTree(oldCG)
			except Exception:
				print('WARNING: Failed to clean up the [{}] directory'.format(oldCG))
				traceback.print_exc()

			try:
				if path.isdir(oldCGAlt):
					forceRmTree(oldCGAlt)
			except Exception:
				print('WARNING: Failed to clean up the [{}] directory'.format(oldCGAlt))
				traceback.print_exc()
		else:
			print("Not cleaning oldCG/oldCGAlt as performing Partial Update")

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
			exePath = self.info.subModConfig.dataName[:-5] + ".exe"
			self._moveFileIntoPlace(
				fromPath = os.path.join(self.extractDir, exePath),
				toPath = os.path.join(self.directory, exePath),
			)
		elif common.Globals.IS_MAC:
			self._moveFileIntoPlace(
				fromPath = os.path.join(self.extractDir, "Contents/Resources/PlayerIcon.icns"),
				toPath = os.path.join(self.directory, "Contents/Resources/PlayerIcon.icns")
			)

	def _applyLanguageSpecificSharedAssets(self, folderToApply):
		"""Helper function which applies language specific assets.
		Returns False if there was an error during the proccess.
		If no asset file was found to apply, this is not considered an error
		(it's assumed the existing sharedassets0.assets is the correct one)"""
		# If don't know own unity version, don't attempt to apply any UI
		if self.info.unityVersion is None:
			print("ERROR: can't apply UI file as don't know own unity version!")
			return False

		# Use the sharedassets file with matching os/unityversion if provided by the language patch
		versionString = self.info.unityVersion
		osString = common.Globals.OS_STRING

		for altUIFilename in os.listdir(folderToApply):
			altUIPath = os.path.join(folderToApply, altUIFilename)
			_, ext = os.path.splitext(altUIFilename)
			if ext.lower() == '.assets' or ext.lower() == '.languagespecificassets':
				if os.path.isfile(altUIPath) and versionString in altUIFilename.lower() and osString in altUIFilename.lower():
					uiPath = path.join(folderToApply, "sharedassets0.assets")
					print("Language Patch UI: Will copy UI File {} -> {}".format(altUIPath, uiPath))
					shutil.copy(altUIPath, uiPath)
					return True

		print("Language Patch UI: No UI/sharedassets0 found for ({},{}) - using default sharedassets0.assets".format(osString, versionString))
		return True

	def applyLanguagePatchFixesIfNecessary(self):
		folderToApply = self.dataDirectory
		if self.forcedExtractDirectory is not None:
			folderToApply = self.getDataDirectory(self.forcedExtractDirectory)

		# Don't need to apply any special UI if no language patch
		if not self.languagePatchIsEnabled:
			return

		# For now, assume language patches don't provide CompiledUpdateScripts folder, so clear any existing compiled
		# scripts which may come with the main patch
		self.clearCompiledScripts()

		# Don't clean up if sharedassets application failed - user may want to apply UI manually
		if not self._applyLanguageSpecificSharedAssets(folderToApply):
			return

		# Clean up unused asset files
		for altUIFilename in os.listdir(folderToApply):
			root, ext = os.path.splitext(altUIFilename)
			altUIPath = os.path.join(folderToApply, altUIFilename)
			try:
				if os.path.isfile(altUIPath) and ext.lower() == '.languagespecificassets' and re.match(r"^(((LinuxMac)|(Windows))-)+(((GOG)|(Steam)|(MG))-)+[\d\w.]+$", root):
					print("Removing unused UI file {}".format(altUIPath))
					os.remove(altUIPath)
			except Exception as e:
				print("Failed to remove unused language specific asset [{}] due to {}".format(altUIPath, e))

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
					forceRemove(target)
				shutil.move(src, target)
		forceRemoveDir(fromDir)

	def _moveFileIntoPlace(self, fromPath, toPath):
		# type: (str, str) -> None
		"""
		Moves a single file from `fromPath` to `toPath`
		"""
		if path.exists(fromPath):
			if path.exists(toPath):
				forceRemove(toPath)
			shutil.move(fromPath, toPath)

	def cleanup(self, cleanExtractionDirectory):
		"""
		General cleanup and other post-install things

		Removes downloaded 7z files
		On mac, modifies the application Info.plist with new values if available
		"""
		try:
			forceRmTree(self.downloadDir)
			if cleanExtractionDirectory:
				forceRmTree(self.extractDir)
		except OSError:
			pass

		if common.Globals.IS_MAC:
			# Allows fixing up application Info.plist file so that the titlebar doesn't show `Higurashi01` as the name of the application
			# Can also add a custom CFBundleIdentifier to change the save directory (e.g. for Console Arcs)
			infoPlist = path.join(self.directory, "Contents/Info.plist")
			infoPlistJSON = subprocess.check_output(["plutil", "-convert", "json", "-o", "-", infoPlist])
			parsed = json.loads(common.ensureUnicodeOrStr(infoPlistJSON))

			configCFBundleName = self.info.subModConfig.CFBundleName
			if configCFBundleName and parsed["CFBundleName"] != configCFBundleName:
				subprocess.call(["plutil", "-replace", "CFBundleName", "-string", configCFBundleName, infoPlist])

			configCFBundleIdentifier = self.info.subModConfig.CFBundleIdentifier
			if configCFBundleIdentifier and parsed["CFBundleIdentifier"] != configCFBundleIdentifier:
				subprocess.call(["plutil", "-replace", "CFBundleIdentifier", "-string", configCFBundleIdentifier, infoPlist])

			# Removes the quarantine attribute from the game (which could cause it to get launched read-only, breaking the script compiler)
			subprocess.call(["xattr", "-d", "com.apple.quarantine", self.directory])

	def saveFileVersionInfoStarted(self):
		self.fileVersionManager.saveVersionInstallStarted()

	def saveFileVersionInfoFinished(self, forcedSaveFolder=None):
		self.fileVersionManager.saveVersionInstallFinished(forcedSaveFolder)

def main(fullInstallConfiguration):
	# type: (installConfiguration.FullInstallConfiguration) -> None

	isVoiceOnly = fullInstallConfiguration.subModConfig.subModName == 'voice-only'
	if isVoiceOnly:
		print("Performing Voice-Only Install - backupUI() and cleanOld() will NOT be performed.")

	modOptionParser = installConfiguration.ModOptionParser(fullInstallConfiguration)

	# The Partial Manual Install option is mainly for Windows, so please don't assume it works properly on Linux/MacOS
	if modOptionParser.partialManualInstall:
		extractDir = fullInstallConfiguration.subModConfig.modName + " " + fullInstallConfiguration.subModConfig.subModName + " Extracted"
		installer = Installer(fullInstallConfiguration, extractDirectlyToGameDirectory=False, modOptionParser=modOptionParser, forcedExtractDirectory=extractDir)
		installer.download()
		installer.extractFiles()
		if installer.optionParser.installSteamGrid:
			steamGridExtractor.extractSteamGrid(installer.downloadDir)
		installer.applyLanguagePatchFixesIfNecessary()
		installer.saveFileVersionInfoFinished(forcedSaveFolder=extractDir)
		common.tryShowInFileBrowser(extractDir)
		common.tryShowInFileBrowser(fullInstallConfiguration.installPath)
	elif common.Globals.IS_WINDOWS:
		# On Windows, extract directly to the game directory to avoid path-length issues and speed up install
		installer = Installer(fullInstallConfiguration, extractDirectlyToGameDirectory=True, modOptionParser=modOptionParser)
		print("Downloading...")
		installer.download()
		installer.saveFileVersionInfoStarted()
		if not isVoiceOnly:
			installer.backupUI()
			installer.cleanOld()
		print("Extracting...")
		installer.extractFiles()
		commandLineParser.printSeventhModStatusUpdate(97, "Cleaning up...")
		if installer.optionParser.installSteamGrid:
			steamGridExtractor.extractSteamGrid(installer.downloadDir)
		installer.applyLanguagePatchFixesIfNecessary()
		installer.saveFileVersionInfoFinished()
		installer.cleanup(cleanExtractionDirectory=False)
	else:
		installer = Installer(fullInstallConfiguration, extractDirectlyToGameDirectory=False, modOptionParser=modOptionParser)
		print("Downloading...")
		installer.download()
		installer.saveFileVersionInfoStarted()
		print("Extracting...")
		installer.extractFiles()
		commandLineParser.printSeventhModStatusUpdate(85, "Moving files into place...")
		if not isVoiceOnly:
			installer.backupUI()
			installer.cleanOld()
		installer.moveFilesIntoPlace()
		commandLineParser.printSeventhModStatusUpdate(97, "Cleaning up...")
		installer.applyLanguagePatchFixesIfNecessary()
		installer.saveFileVersionInfoFinished()
		installer.cleanup(cleanExtractionDirectory=True)


	commandLineParser.printSeventhModStatusUpdate(100, "Install Completed!")
