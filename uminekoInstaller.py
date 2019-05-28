import commandLineParser
import common
import os, shutil, subprocess
import gameScanner
import logger


def deleteAllInPathExceptSpecified(paths, extensions, searchStrings, alwaysDeleteStrings):
	"""
	Deletes all files in the specified paths, unless they have both a desired extension and a desired search string.
	NOTE: if file has multiple extensions, only the last will be matched. This means multi part archives like a.zip.001
	won't work correctly!

	:param paths: A list[] of paths which will have its files deleted according to the below critera
	:param extensions: files to keep must have one of the extensions in this list[] (lowercase with the '.', such as '.zip')
	:param searchStrings: files to keep must contain these search strings.
	:return:
	"""
	for path in paths:
		if not os.path.isdir(path):
			print("removeFilesWithExtensions: {} is not a dir or doesn't exist - skipping".format(path))
			continue

		for fileAnyCase in os.listdir(path):
			fullDeletePath = os.path.join(path, fileAnyCase)

			if os.path.isdir(fullDeletePath):
				print("removeFilesWithExtensions: Skipping folder [{}]".format(fullDeletePath))
				continue

			fileNameNoExt, extension = os.path.splitext(fileAnyCase.lower())

			hasCorrectExtension = extension in extensions

			hasCorrectSearchString = False
			if not searchStrings:
				hasCorrectSearchString = True
			else:
				for searchString in searchStrings:
					if searchString in fileNameNoExt:
						hasCorrectSearchString = True

			hasAlwaysDeleteString = False
			if alwaysDeleteStrings:
				for alwaysDeleteString in alwaysDeleteStrings:
					if alwaysDeleteString in fileNameNoExt:
						hasAlwaysDeleteString = True

			# Keep the file if it has both the correct extension and search string. Otherwise, delete it
			if hasCorrectExtension and hasCorrectSearchString and not hasAlwaysDeleteString:
				print("Keeping file:", fullDeletePath)
			else:
				print("Deleting file:", fullDeletePath)
				os.remove(fullDeletePath)

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
	# type: (gameScanner.FullInstallConfiguration) -> None
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

	# Wipe non-checksummed install files in the temp folder. Print if not a fresh install.
	deleteAllInPathExceptSpecified([downloadTempDir],
	                               extensions=['.7z', '.zip'],
	                               searchStrings=['graphic', 'voice'],
	                               alwaysDeleteStrings=['script'])

	######################################## DOWNLOAD, BACKUP, THEN EXTRACT ############################################
	downloaderAndExtractor = common.DownloaderAndExtractor(conf.buildFileListSorted(), downloadTempDir, conf.installPath, downloadProgressAmount=45, extractionProgressAmount=45)
	downloaderAndExtractor.buildDownloadAndExtractionList()

	parser = gameScanner.ModOptionParser(conf)

	for opt in parser.downloadAndExtractOptionsByPriority:
		downloaderAndExtractor.addItemManually(
			url=opt.url,
			extractionDir=os.path.join(conf.installPath, opt.relativeExtractionPath),
		)

	downloaderAndExtractor.printPreview()
	downloaderAndExtractor.download()

	# Backup/clear the .exe and script files
	backupOrRemoveFiles(conf.installPath)

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

	# Open the temp folder so users can delete/backup any temp install files
	if common.Globals.IS_WINDOWS:
		print("Showing download folder for user to delete temp files")
		common.trySystemOpen(downloadTempDir, normalizePath=True)

	commandLineParser.printSeventhModStatusUpdate(100, "Umineko install script completed!")
