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


def languageSpecificUIFileValid(filename):
	# type: (str) -> bool
	valid = True

	# Check that the UI filename contains at least one operating system
	detectedOS = []
	for osName in ['windows', 'linux', 'mac']:
		if osName in filename.lower():
			detectedOS.append(osName)
	if not detectedOS:
		print("LanguageSpecificAsset:   > Error - '{}' is missing an OS name (should be windows, linux, or mac)".format(filename))
		valid = False

	# Check the UI filename contains a Unity Version
	detectedUnityVersion = None
	match = re.search(r'((\d\.\d\.\d\w\d)|(\d\d\d\d\.\d\.\d))', filename, re.IGNORECASE)
	if match:
		detectedUnityVersion = match.groups()[0]
	if detectedUnityVersion is None:
		print("LanguageSpecificAsset:   > Error - '{}' is missing unity version (like 5.5.3p3 or 2017.2.5)".format(filename))
		valid = False

	print(
		"LanguageSpecificAsset: Detected '{}-{}' from file '{}'".format(detectedOS, detectedUnityVersion, filename))

	return valid

def listInvalidUIFiles(folder):
	#type: (str) -> [str]
	"""
	This function validates language specific ui files (*.assets and *.languagespecificassets in the given folder).
	Please note the behavior is different for .assets and .languagespecificassets extension:
		- .assets will not raise an exception, and will just print errors to console. This is in case there is some
		  unknown .assets file in the game folder which would be treated as invalid, causing the install to fail
		- .languagespecificassets will raise an exception on error (after all files are checked)
	"""
	invalidUIFileList = []
	for altUIFilename in os.listdir(folder):
		if altUIFilename in ['globalgamemanagers.assets', 'resources.assets', 'sharedassets0.assets']:
			continue

		_, ext = os.path.splitext(altUIFilename)
		if ext.lower() == '.assets':
			languageSpecificUIFileValid(altUIFilename)
		elif ext.lower() == '.languagespecificassets':
			if not languageSpecificUIFileValid(altUIFilename):
				invalidUIFileList.append(altUIFilename)

	return invalidUIFileList

def backupFileIfNotExist(sourcePath, backupPath):
	#type: (str, str) -> None
	"""
	Try to backup a file in a transactional way so you can't get a half-copied file.
	If the file already is backed up to the backupPath, it won't be overwritten
	"""
	if path.exists(sourcePath) and not path.exists(backupPath):
		shutil.copy(sourcePath, backupPath + '.temp')
		os.rename(backupPath + '.temp', backupPath)

class Installer:
	def getDataDirectory(self, installPath):
		if common.Globals.IS_MAC:
			return path.join(installPath, "Contents/Resources/Data")
		else:
			return path.join(installPath, self.info.subModConfig.dataName)

	def __init__(self, fullInstallConfiguration, extractDirectlyToGameDirectory, modOptionParser, forcedExtractDirectory=None, skipDownload=False):
		# type: (installConfiguration.FullInstallConfiguration, bool, installConfiguration.ModOptionParser, Optional[str], bool) -> None

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
		self.skipDownload = skipDownload
		self.isWine = fullInstallConfiguration.isWine

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
			fullInstallConfiguration=self.info,
			modFileList=self.info.buildFileListSorted(datadir=self.dataDirectory),
			localVersionFolder=self.directory,
			datadir=self.dataDirectory)

		modFileList = self.fileVersionManager.getFilesRequiringUpdate()

		for modFile in modFileList:
			if modFile.name == 'script':
				self.clearScripts = True

		self.info.subModConfig.printEnabledOptions()
		self.downloaderAndExtractor = common.DownloaderAndExtractor(modFileList=modFileList,
		                                                            downloadTempDir=self.downloadDir,
		                                                            extractionDir=self.extractDir,
		                                                            skipDownload=self.skipDownload)

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

	def getBackupPath(self, relativePath):
			# partialManualInstall is not really supported on MacOS, so just assume output folder is HigurashiEpX_Data
			if self.forcedExtractDirectory is not None:
				return path.join(self.forcedExtractDirectory, self.info.subModConfig.dataName, relativePath + '.backup')
			else:
				return path.join(self.dataDirectory, relativePath + '.backup')

	def tryBackupFile(self, relativePath):
		"""
		Tries to backup a file relative to the dataDirectory of the game, unless a backup already exists.
		"""
		try:
			sourcePath = path.join(self.dataDirectory, relativePath)
			backupPath = self.getBackupPath(relativePath)
			backupFileIfNotExist(sourcePath, backupPath)
		except Exception as e:
			print('Error: Failed to backup {} file: {}'.format(relativePath, e))
			raise e


	def backupFiles(self):
		"""
		Backs up various files necessary for the installer to operate
		Usually this is to prevent the installer having issues if it fails or is stopped half-way
		"""
		# Backs up the `sharedassets0.assets` file
		# Try to do this in a transactional way so you can't get a half-copied .backup file.
		# This is important since the .backup file is needed to determine which ui file to use on future updates
		# The file is not moved directly in case the installer is halted before the new UI file can be placed, resulting
		# in an install completely missing a sharedassets0.assets UI file.
		self.tryBackupFile('sharedassets0.assets')
		# Backs up the `resources.assets` file
		# The backup (resources.assets.backup) will be deleted on a successful install
		self.tryBackupFile('resources.assets')

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
		# In some cases, the folders to be moved may not exist yet, so create them in advance
		# This creates both the self.extractDir and the HigurashiEp0X subfolder
		fromDataDir = os.path.join(self.extractDir, self.info.subModConfig.dataName)
		try:
			os.makedirs(fromDataDir)
		except OSError:
			pass

		# On MacOS, the datadirectory has a different path than in the archive file:
		#
		# datadirectory in archive file : "Higurashi_Ep0X"
		# datadirectory on Linux/Windows: "Higurashi_Ep0X"
		#         datadirectory on Macos: "Contents/Resources/Data"
		#
		# To account for this, we rename the "Higurashi_Ep0X" folder to "Contents/Resources/Data" below
		# (self.dataDirectory should equal "Contents/Resources/Data" on MacOS)
		self._moveDirectoryIntoPlace(
			fromDir = fromDataDir,
			toDir = self.dataDirectory,
			log = True,
		)

		if common.Globals.IS_WINDOWS:
			exePath = self.info.subModConfig.dataName[:-5] + ".exe"
			self._moveFileIntoPlace(
				fromPath = os.path.join(self.extractDir, exePath),
				toPath = os.path.join(self.directory, exePath),
				log=True,
			)
		elif common.Globals.IS_MAC:
			self._moveFileIntoPlace(
				fromPath = os.path.join(self.extractDir, "Contents/Resources/PlayerIcon.icns"),
				toPath = os.path.join(self.directory, "Contents/Resources/PlayerIcon.icns"),
				log = True,
			)

		# If any files still remain, just move them directly into the game directory,
		# keeping the same folder structure as inside the archive
		self._moveDirectoryIntoPlace(
			fromDir = self.extractDir,
			toDir = self.directory,
			log = True,
		)

	def _applyLanguageSpecificSharedAssets(self, folderToApply):
		"""Helper function which applies language specific assets.
		Returns False if there was an error during the proccess.
		If no asset file was found to apply, this is not considered an error
		(it's assumed the existing sharedassets0.assets is the correct one)"""
		# Get the unity version (again) from the existing resources.assets file
		# We don't use the version stored in self.info.unityVersion because on certain configurations,
		# the mod itself updates the unity version, causing it to change mid-install.
		try:
			versionString = installConfiguration.getUnityVersion(self.dataDirectory)
		except Exception as e:
			# If don't know own unity version, don't attempt to apply any UI
			print("ERROR (_applyLanguageSpecificSharedAssets()): Failed to retrieve unity version from resources.assets as {}".format(e))
			print("ERROR: can't apply UI file as don't know own unity version!")
			return False

		# Use the sharedassets file with matching os/unityversion if provided by the language patch
		osString = common.Globals.OS_STRING
		if self.isWine:
			osString = "windows"
			print("Language Patch UI: Proton/Wine detected! Forcing install of Windows sharedassets0.assets.")

		# TODO: use the sharedassets0.assets.backup to determine store name?
		# For now, only differentiate steam/non-steam
		# Or if can prove that it's always steam+mangagamer and gog, then can leave as-is
		if self.isSteam:
			print("Language Patch UI: Assuming store is Steam/Mangagamer")
			storeName = 'steam'
		else:
			print("Language Patch UI: Assuming store is GOG")
			storeName = 'gog'

		bestAltUIPath = None
		for altUIFilename in os.listdir(folderToApply):
			altUIPath = os.path.join(folderToApply, altUIFilename)
			_, ext = os.path.splitext(altUIFilename)
			if ext.lower() == '.assets' or ext.lower() == '.languagespecificassets':
				if os.path.isfile(altUIPath) and versionString in altUIFilename.lower() and osString in altUIFilename.lower():
					if bestAltUIPath is None or storeName in altUIFilename.lower():
						bestAltUIPath = altUIPath

		if bestAltUIPath is not None:
			uiPath = path.join(folderToApply, "sharedassets0.assets")
			print("Language Patch UI: Will copy UI File {} -> {}".format(bestAltUIPath, uiPath))
			shutil.copy(bestAltUIPath, uiPath)
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

		invalidUIFileList = listInvalidUIFiles(folderToApply)

		assetsApplied = self._applyLanguageSpecificSharedAssets(folderToApply)

		# Don't clean up if sharedassets application failed - user may want to apply UI manually
		# However if invalid ui files were found, remove them, as this may cause problems later
		if invalidUIFileList or assetsApplied:
			# Clean up unused asset files
			for altUIFilename in os.listdir(folderToApply):
				root, ext = os.path.splitext(altUIFilename)
				altUIPath = os.path.join(folderToApply, altUIFilename)
				try:
					if os.path.isfile(altUIPath) and ext.lower() == '.languagespecificassets':
						print("Removing unused UI file {}".format(altUIPath))
						os.remove(altUIPath)
				except Exception as e:
					print("Failed to remove unused language specific asset [{}] due to {}".format(altUIPath, e))

		if invalidUIFileList:
			raise Exception('Please send the developers on our Discord server https://discord.gg/pf5VhF9 '
			                'this error so we can fix it:\n\n'
			                '"Invalid Language Specific Asset files found: {}"'.format(invalidUIFileList))

	def _moveDirectoryIntoPlace(self, fromDir, toDir, log=False):
		# type: (str, str, Optional[bool]) -> None
		"""
		Recursive function that does the actual moving for `moveFilesIntoPlace`
		"""
		if log:
			print("_moveDirectoryIntoPlace: '{}' -> '{}'".format(fromDir, toDir))

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

	def _moveFileIntoPlace(self, fromPath, toPath, log=False):
		# type: (str, str, Optional[bool]) -> None
		"""
		Moves a single file from `fromPath` to `toPath`
		"""
		if log:
			print("_moveFileIntoPlace: '{}' -> '{}'".format(fromPath, toPath))

		if path.exists(fromPath):
			if path.exists(toPath):
				forceRemove(toPath)
			shutil.move(fromPath, toPath)

	def cleanup(self, cleanExtractionDirectory, cleanDownloadDirectory=True):
		"""
		General cleanup and other post-install things

		Removes downloaded 7z files
		On mac, modifies the application Info.plist with new values if available
		"""
		try:
			if cleanDownloadDirectory:
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

		# Remove the resources.assets.backup file if install succeeds
		resourcesBackupPath = self.getBackupPath('resources.assets')
		try:
			if os.path.exists(resourcesBackupPath):
				forceRemove(resourcesBackupPath)
		except Exception as e:
			print("Warning: Failed to remove `{}`. Updating the mod may not work correctly unless this file is deleted.".format(resourcesBackupPath))

	def saveFileVersionInfoStarted(self):
		self.fileVersionManager.saveVersionInstallStarted()

	def saveFileVersionInfoFinished(self, forcedSaveFolder=None):
		self.fileVersionManager.saveVersionInstallFinished(forcedSaveFolder)

def main(fullInstallConfiguration):
	# type: (installConfiguration.FullInstallConfiguration) -> None

	if common.Globals.IS_LINUX:
		print("Linux Compatibility Layer: {}".format("YES: Using Wine or Proton" if fullInstallConfiguration.isWine else "no: Using Native"))

	isVoiceOnly = fullInstallConfiguration.subModConfig.subModName == 'voice-only'
	if isVoiceOnly:
		print("Performing Voice-Only Install - backupFiles() and cleanOld() will NOT be performed.")

	modOptionParser = installConfiguration.ModOptionParser(fullInstallConfiguration)
	skipDownload = modOptionParser.downloadManually
	keepDownloads = modOptionParser.keepDownloads

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
		installer = Installer(fullInstallConfiguration, extractDirectlyToGameDirectory=True, modOptionParser=modOptionParser, skipDownload=skipDownload)
		print("Downloading...")
		installer.download()
		installer.saveFileVersionInfoStarted()
		if not isVoiceOnly:
			installer.backupFiles()
			installer.cleanOld()
		print("Extracting...")
		installer.extractFiles()
		commandLineParser.printSeventhModStatusUpdate(97, "Cleaning up...")
		if installer.optionParser.installSteamGrid:
			steamGridExtractor.extractSteamGrid(installer.downloadDir)
		installer.applyLanguagePatchFixesIfNecessary()
		installer.saveFileVersionInfoFinished()
		installer.cleanup(cleanExtractionDirectory=False, cleanDownloadDirectory=not skipDownload and not keepDownloads)
	else:
		installer = Installer(fullInstallConfiguration, extractDirectlyToGameDirectory=False, modOptionParser=modOptionParser, skipDownload=skipDownload)
		print("Downloading...")
		installer.download()
		installer.saveFileVersionInfoStarted()
		print("Extracting...")
		installer.extractFiles()
		commandLineParser.printSeventhModStatusUpdate(85, "Moving files into place...")
		if not isVoiceOnly:
			installer.backupFiles()
			installer.cleanOld()
		installer.moveFilesIntoPlace()
		commandLineParser.printSeventhModStatusUpdate(97, "Cleaning up...")
		if installer.optionParser.installSteamGrid:
			steamGridExtractor.extractSteamGrid(installer.downloadDir)
		installer.applyLanguagePatchFixesIfNecessary()
		installer.saveFileVersionInfoFinished()
		installer.cleanup(cleanExtractionDirectory=True, cleanDownloadDirectory=not skipDownload and not keepDownloads)


	commandLineParser.printSeventhModStatusUpdate(100, "Install Completed!")
