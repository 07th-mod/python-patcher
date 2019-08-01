from __future__ import unicode_literals

import commandLineParser
import common
import os, shutil, subprocess

import fileVersionManagement
import gameScanner
import installConfiguration
import logger

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

		#only process the file if it exists on disk
		if not os.path.isfile(fullFilePath) and not os.path.isdir(fullFilePath):
			continue

		# backup the file/folder if no backup has been performed previously - otherwise delete the file
		if os.path.isfile(backupPath) or os.path.isdir(backupPath):
			print("backupOrRemoveFiles: removing", fullFilePath, "as backup already exists")
			if os.path.isfile(backupPath):
				os.remove(fullFilePath)
			else:
				shutil.rmtree(fullFilePath)
		else:
			print("backupOrRemoveFiles: backing up", fullFilePath)
			shutil.move(fullFilePath, backupPath)

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
	for extractableItem in downloaderAndExtractor.extractList:
		extractableItemPath = os.path.join(downloadTempDir, extractableItem.filename)
		if not extractableItem.fromMetaLink and os.path.exists(extractableItemPath):
			print("Removing existing non-checksummed download: [{}]".format(extractableItemPath))
			os.remove(extractableItemPath)

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
	downloaderAndExtractor.extract()

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
		f.writelines(["mklink saves mysav /J\n", "pause"])

	# For now, don't copy save data

	fileVersionManager.saveVersionInstallFinished()

	commandLineParser.printSeventhModStatusUpdate(100, "Umineko install script completed!")
