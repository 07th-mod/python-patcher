from __future__ import unicode_literals

import commandLineParser
import common
import os

import fileVersionManagement
import gameScanner
import installConfiguration
import logger

#do install given a installer config object
def main(conf):
	# type: (installConfiguration.FullInstallConfiguration) -> None
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

	if not common.Globals.IS_WINDOWS:
		raise Exception("Error: Umineko Hane Mod (onscripter version) is not supported on Mac or Linux!")

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

	######################################## DOWNLOAD, BACKUP, THEN EXTRACT ############################################
	fileVersionManager = fileVersionManagement.VersionManager(
		subMod=conf.subModConfig,
		modFileList=conf.buildFileListSorted(),
		localVersionFolder=conf.installPath)

	filesRequiringUpdate = fileVersionManager.getFilesRequiringUpdate()

	downloaderAndExtractor = common.DownloaderAndExtractor(filesRequiringUpdate, downloadTempDir, conf.installPath, downloadProgressAmount=45, extractionProgressAmount=45)
	downloaderAndExtractor.buildDownloadAndExtractionList()

	parser = installConfiguration.ModOptionParser(conf)

	for opt in parser.downloadAndExtractOptionsByPriority:
		downloaderAndExtractor.addItemManually(
			url=opt.url,
			extractionDir=os.path.join(conf.installPath, opt.relativeExtractionPath),
		)

	downloaderAndExtractor.printPreview()
	downloaderAndExtractor.download()

	# Extract files
	fileVersionManager.saveVersionInstallStarted()
	downloaderAndExtractor.extract()

	fileVersionManager.saveVersionInstallFinished()
	commandLineParser.printSeventhModStatusUpdate(100, "Umineko Hane install script completed!")
