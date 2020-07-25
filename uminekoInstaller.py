from __future__ import unicode_literals

import commandLineParser
import common
import os, shutil, subprocess, hashlib

import fileVersionManagement
import gameScanner
import installConfiguration
import logger
import steamGridExtractor

try:
	from typing import List
except:
	pass

def backupOrRemoveFiles(folderToBackup):
	"""
	Backs up files for both question and answer arcs
	If a backup already exists, the file is instead removed

	:param folderToBackup: Folder to scan for files. Backups will be placed in the same folder, with extension '.backup'
	:return:
	"""
	pathsToBackup = ['Umineko5to8.exe', 'Umineko5to8', 'Umineko5to8.app',
	                 'Umineko1to4.exe', 'Umineko1to4', 'Umineko1to4.app',
	                 '0.utf', '0.u']

	for pathToBackup in pathsToBackup:
		fullFilePath = os.path.join(folderToBackup, pathToBackup)
		backupPath = fullFilePath + '.backup'

		# Backup the file/folders if they exist
		if os.path.exists(fullFilePath):
			try:
				print("backupOrRemoveFiles: Backing up {} to {}".format(fullFilePath, backupPath))
				if os.path.isfile(fullFilePath):
					shutil.copy(fullFilePath, backupPath)
				else:
					shutil.copytree(fullFilePath, backupPath)
			except Exception as e:
				print("backupOrRemoveFiles: Failed to backup {}: {}".format(fullFilePath, e))

def deleteExtractablesFromFolder(folderContainingItems, extractableItemList):
	#type: (str, List[common.DownloaderAndExtractor.ExtractableItem]) -> None
	for extractableItem in extractableItemList:
		extractableItemPath = os.path.join(folderContainingItems, extractableItem.filename)
		dateModifiedPath = "{}.dateModified".format(extractableItemPath)

		if os.path.exists(extractableItemPath):
			print("Removing: [{}]".format(extractableItemPath))
			os.remove(extractableItemPath)

		if os.path.exists(dateModifiedPath):
			print("Removing dateModified file: [{}]".format(dateModifiedPath))
			os.remove(dateModifiedPath)

#do install given a installer config object
def mainUmineko(conf):
	# type: (installConfiguration.FullInstallConfiguration) -> None
	logger.getGlobalLogger().trySetSecondaryLoggingPath(
		os.path.join(conf.installPath, common.Globals.LOG_BASENAME)
	)

	isQuestionArcs = 'question' in conf.subModConfig.modName.lower()

	print("CONFIGURATION:")
	print("Install path", conf.installPath)
	print("Mod Option", conf.subModConfig.modName)
	print("Sub Option", conf.subModConfig.subModName)
	print("Is Question Arcs", isQuestionArcs)
	print("Is Windows", common.Globals.IS_WINDOWS)
	print("Is Linux", common.Globals.IS_LINUX)
	print("Is Mac", common.Globals.IS_MAC)

	####################################### VALIDATE AND PREPARE FOLDERS ###############################################
	# do a quick verification that the directory is correct before starting installer
	if not os.path.isfile(os.path.join(conf.installPath, "arc.nsa")):
		raise Exception("ERROR - wrong game path. Installation Stopped.\n"
		                "There is no 'arc.nsa' in the game folder. Are you sure the correct game folder was selected?")

	for filename in os.listdir(conf.installPath):
		# Stop the user installing the mod on pirated versions of the game.
		# Use SHA256 hash of the lowercase filename to avoid listing the website names in our source code.
		if hashlib.sha256(filename.lower().encode('utf-8')).hexdigest() in [
			'2c02ec6f6de9281a68975257a477e8f994affe4eeaaf18b0b56b4047885461e0',
			'4fae41c555fe50034065e59ce33a643c1d93ee846221ecc5756f00e039035076',
		]:
			raise Exception("\nInstall Failed - The {} mod is not compatible with the pirated version of the game\n"
			                "(Detected file [{}]) Please install the latest Steam or Mangagamer release."
			                .format(conf.subModConfig.modName, filename))

		# Stop the user installing the mod on the old/original Japanese game.
		# This probably means the user placed a fake identifier (eg the game exe) in the old game's folder.
		if filename == 'snow.dll':
			raise Exception("\nInstall Failed - The {} mod is not compatible with the old/original Japanese game.\n"
			                "(Detected [{}]) Please install the latest Steam or Mangagamer release."
			                .format(conf.subModConfig.modName, filename))

	# Create aliases for the temp directories, and ensure they exist beforehand
	downloadTempDir = conf.subModConfig.modName + " Downloads"

	if os.path.isdir(downloadTempDir):
		print("Information: Temp directories already exist - continued or overwritten install")

	common.makeDirsExistOK(downloadTempDir)

	######################################## Query and Download Files ##################################################
	fileVersionManager = fileVersionManagement.VersionManager(
		subMod=conf.subModConfig,
		modFileList=conf.buildFileListSorted(),
		localVersionFolder=conf.installPath)

	filesRequiringUpdate = fileVersionManager.getFilesRequiringUpdate()
	print("Perform Full Install: {}".format(fileVersionManager.fullUpdateRequired()))
	downloaderAndExtractor = common.DownloaderAndExtractor(filesRequiringUpdate, downloadTempDir, conf.installPath, downloadProgressAmount=45, extractionProgressAmount=45)
	downloaderAndExtractor.buildDownloadAndExtractionList()

	parser = installConfiguration.ModOptionParser(conf)

	for opt in parser.downloadAndExtractOptionsByPriority:
		downloaderAndExtractor.addItemManually(
			url=opt.url,
			extractionDir=os.path.join(conf.installPath, opt.relativeExtractionPath),
		)

	downloaderAndExtractor.printPreview()

	# Delete all non-checksummed files from the download folder, if they exist
	print("Removing non-checksummed downloads:")
	deleteExtractablesFromFolder(downloadTempDir, [x for x in downloaderAndExtractor.extractList if not x.fromMetaLink])

	downloaderAndExtractor.download()

	# Treat the install as "started" once the "download" stage is complete
	fileVersionManager.saveVersionInstallStarted()

	###################### Backup/clear the .exe and script files, and old graphics ####################################
	backupOrRemoveFiles(conf.installPath)

	if fileVersionManager.fullUpdateRequired():
		# Remove old graphics from a previous installation, as they can conflict with the voice-only patch
		graphicsPathsToDelete = [os.path.join(conf.installPath, x) for x in ['big', 'bmp', 'en']]

		for folderPath in graphicsPathsToDelete:
			if os.path.exists(folderPath):
				print("Deleting {}".format(folderPath))
				try:
					shutil.rmtree(folderPath)
				except:
					print("WARNING: failed to remove folder {}".format(folderPath))

	######################################## Extract Archives ##########################################################
	def remapPaths(originalFolder, originalFilename):
		fileNameNoExt, extension = os.path.splitext(originalFilename)
		if '.utf' in extension:
			return originalFolder, (fileNameNoExt + '.u')
		else:
			return originalFolder, originalFilename

	downloaderAndExtractor.extract(remapPaths)

	############################################# FIX .ARC FILE NAMING #################################################
	# Steam release has arc files labeled arc.nsa, arc1.nsa, arc2.nsa, arc3.nsa.
	# Mangagamer release has only one arc file labeled arc.nsa
	# Generate dummy arc1-arc3 nsa files if they don't already exist, so the game can find the arc4.nsa that we provide
	for i in range(1,4):
		nsaPath = os.path.join(conf.installPath, 'arc{}.nsa'.format(i))
		if not os.path.exists(nsaPath):
			print(".nsa archive check: Generating dummy [{}] as it does not already exist (Mangagamer)".format(nsaPath))
			with open(nsaPath, 'wb') as dummyNSAFile:
				dummyNSAFile.write(bytes([0, 0, 0, 0, 0, 6]))
		else:
			print(".nsa archive check: [{}] already exists (Steam)".format(nsaPath))

	#################################### MAKE EXECUTABLE, WRITE HELPER SCRIPTS #########################################
	gameBaseName = "Umineko5to8"
	if isQuestionArcs:
		gameBaseName = "Umineko1to4"

	if common.Globals.IS_MAC:
		print("Un-quarantining game executable")
		subprocess.call(["xattr", "-d", "com.apple.quarantine", os.path.join(conf.installPath, gameBaseName + ".app")])

	print("Creating debug mode batch files")
	# write batch file to let users launch game in debug mode
	with open(os.path.join(conf.installPath, gameBaseName + "_DebugMode.bat"), 'w') as f:
		f.writelines([gameBaseName + ".exe --debug\n", "pause"])

	#make the following files executable, if they exist
	makeExecutableList = [
		os.path.join(conf.installPath, "Umineko1to4"),
		os.path.join(conf.installPath, "Umineko1to4.app/Contents/MacOS/umineko4"),
		os.path.join(conf.installPath, "Umineko5to8"),
		os.path.join(conf.installPath, "Umineko5to8.app/Contents/MacOS/umineko8")
	]

	print("Making executables ... executable")
	for exePath in makeExecutableList:
		if os.path.exists(exePath):
			common.makeExecutable(exePath)

	# Patched game uses mysav folder, which Steam can't see so can't get incompatible saves by accident.
	# Add batch file which reverses this behaviour by making a linked folder from (saves->mysav)
	print("Creating EnableSteamSync.bat")
	with open(os.path.join(conf.installPath, "EnableSteamSync.bat"), 'w') as f:
		f.write("""
if exist saves (
    ren saves backup-saves
    mklink /J saves mysav
) else (
    mklink /J saves mysav
)
pause
""")

	# For now, don't copy save data
	if conf.installSteamGrid:
		steamGridExtractor.extractSteamGrid(downloadTempDir)
	fileVersionManager.saveVersionInstallFinished()

	if not parser.keepDownloads:
		print("Removing temporary downloads:")
		deleteExtractablesFromFolder(downloadTempDir, downloaderAndExtractor.extractList)

	commandLineParser.printSeventhModStatusUpdate(100, "Umineko install script completed!")
