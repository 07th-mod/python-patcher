from __future__ import unicode_literals

import commandLineParser
import common
import os, shutil, subprocess
import gameScanner
import logger

#do install given a installer config object
def mainNscripter(conf):
	# type: (gameScanner.FullInstallConfiguration) -> None
	logger.getGlobalLogger().trySetSecondaryLoggingPath(
		os.path.join(conf.installPath, common.Globals.LOG_BASENAME)
	)

	print("CONFIGURATION:")
	print("Install path", conf.installPath)
	print("Mod Option", conf.subModConfig.modName)
	print("Sub Option", conf.subModConfig.subModName)
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
	for path in os.listdir(downloadTempDir):
		if 'script' in path:
			print("Deleting previous script download {}".format(path))
			os.remove(os.path.join(downloadTempDir, path))

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

	downloaderAndExtractor.extract()


	commandLineParser.printSeventhModStatusUpdate(100, "Umineko install script completed!")
