from common import *
import os, shutil, subprocess
from gameScanner import FullInstallConfiguration
from gameScanner import SubModConfig

umi_debug_mode = False

def uminekoDownload(downloadTempDir, url_list):
	makeDirsExistOK(downloadTempDir)

	for url in url_list:
		print("Downloading [{}] -> [{}]".format(url, downloadTempDir))
		if not umi_debug_mode:
			if aria(downloadTempDir, url=url, followMetaLink=True) != 0:
				print("ERROR - could not download [{}]. Installation Stopped".format(url))
				exitWithError()


def extractOrCopyFile(filename, sourceFolder, destinationFolder):
	makeDirsExistOK(destinationFolder)
	sourcePath = os.path.join(sourceFolder, filename)
	if umi_debug_mode:
		print("Copying or Extracting [{}] into [{}]".format(sourcePath, destinationFolder))
		return

	if '.7z' in filename.lower() or '.zip' in filename.lower():
		if sevenZipExtract(sourcePath, outputDir=destinationFolder) != 0:
			print("ERROR - could not extract [{}]. Installation Stopped".format(sourcePath))
			exitWithError()
	else:
		shutil.copy(sourcePath, os.path.join(destinationFolder, filename))


def deleteAllInPathExceptSpecified(paths, extensions, searchStrings):
	"""
	Deletes all files in the specified paths, unless they have both a desired extension and a desired search string.
	NOTE: if file has multiple extensions, all will be matched. Eg. .zip.001 will match the extension 'zip' and '001'

	:param paths: A list[] of paths which will have its files deleted according to the below critera
	:param extensions: files to keep must have one of the extensions in this list[] (without the '.', such as 'zip')
	:param searchStrings: files to keep must contain these search strings.
	:return:
	"""
	for path in paths:
		if not os.path.isdir(path):
			print("removeFilesWithExtensions: {} is not a dir or doesn't exist - skipping".format(path))
			continue

		for fileAnyCase in os.listdir(path):
			splitFileName = fileAnyCase.lower().split('.')

			hasCorrectExtension = False
			for extension in splitFileName[1:]:
				if extension in extensions:
					hasCorrectExtension = True

			hasCorrectSearchString = False
			if not searchStrings:
				hasCorrectSearchString = True
			else:
				for searchString in searchStrings:
					if searchString in splitFileName[0]:
						hasCorrectSearchString = True

			# Keep the file if it has both the correct extension and search string. Otherwise, delete it
			fullDeletePath = os.path.join(path, fileAnyCase)
			if hasCorrectExtension and hasCorrectSearchString:
				print("Keeping file:", fullDeletePath)
			else:
				print("Deleting file:", fullDeletePath)
				if not umi_debug_mode:
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


def getMetalinkFilenames(url, downloadDir):
	import xml.etree.ElementTree as ET

	metalinkFileName = os.path.basename(url)
	metalinkFileFullPath = os.path.join(downloadDir, metalinkFileName)

	aria(downloadDir, url=url)

	tree = ET.parse(metalinkFileFullPath)
	root = tree.getroot()

	# return the 'name' attribute of each 'file' node.
	# ignore namespaces by removing the {stuff} part of the tag
	filenames = []
	for fileNode in root.iter():
		tagNoNamespace = fileNode.tag.split('}')[-1]
		if tagNoNamespace == 'file':
			filenames.append(fileNode.attrib['name'])

	return filenames

#do install given a installer config object
def mainUmineko(progressNotifier, conf):
	# type: (ProgressNotifier, FullInstallConfiguration) -> None

	isQuestionArcs = 'question' in conf.subModConfig.modname.lower()

	print("CONFIGURATION:")
	print("Install path", conf.installPath)
	print("Mod Option", conf.subModConfig.modname)
	print("Sub Option", conf.subModConfig.submodname)
	print("Is Question Arcs", isQuestionArcs)
	print("Is Windows", IS_WINDOWS)
	print("Is Linux", IS_LINUX)
	print("Is Mac", IS_MAC)

	####################################### VALIDATE AND PREPARE FOLDERS ###############################################
	# do a quick verification that the directory is correct before starting installer
	if not os.path.isfile(os.path.join(conf.installPath, "arc.nsa")):
		print("There is no 'arc.nsa' in the game folder. Are you sure the correct game folder was selected?")
		print("ERROR - wrong game path. Installation Stopped.")
		exitWithError()

	# Create aliases for the temp directories, and ensure they exist beforehand
	downloadTempDir = os.path.join(conf.installPath, "temp")

	if os.path.isdir(downloadTempDir):
		print("Information: Temp directories already exist - continued or overwritten install")


	makeDirsExistOK(downloadTempDir)

	# Wipe non-checksummed install files in the temp folder. Print if not a fresh install.
	deleteAllInPathExceptSpecified([downloadTempDir],
	                               extensions=['7z', 'zip'],
	                               searchStrings=['graphic', 'voice'])

	# Backup/clear the .exe and script files
	backupOrRemoveFiles(conf.installPath)

	##################################### BUILD FILE LIST, DOWNLOAD, EXTRACT ###########################################
	# build file list
	downloadList = []
	extractList = []

	print("\n Retrieving metalinks:")
	for i, file in enumerate(conf.buildFileListSorted()):
		name, ext = os.path.splitext(file.url)

		# For metafiles, we need to look for filenames within each metafile to know what to extract
		# Other files can be left as-is
		# The order of the download and extraction is maintained through the list ordering.
		if ext == '.meta4' or ext == '.metalink':
			metalinkFilenames = getMetalinkFilenames(file.url, downloadTempDir)
			print("metalink contains: ", metalinkFilenames)
			downloadList.append(file.url)
			extractList.extend(metalinkFilenames)
		else:
			downloadList.append(file.url)
			extractList.append(os.path.basename(file.url))


	print("\nFirst these files will be downloaded:")
	print('\n - '.join([''] + downloadList))
	print("\nThen these files will be extracted or copied:")
	print('\n - '.join([''] + extractList))
	print()

	#download all urls to the download temp folder
	uminekoDownload(downloadTempDir, downloadList)

	#extract all files
	for file in extractList:
		extractOrCopyFile(file, downloadTempDir, conf.installPath)

	#################################### MAKE EXECUTABLE, WRITE HELPER SCRIPTS #########################################
	gameBaseName = "Umineko5to8"
	if isQuestionArcs:
		gameBaseName = "Umineko1to4"

	if IS_MAC:
		subprocess.call(["xattr", "-d", "com.apple.quarantine", os.path.join(conf.installPath, gameBaseName + ".app")])

	# write batch file to let users launch game in debug mode
	with open(os.path.join(conf.installPath, gameBaseName + "_DebugMode.bat"), 'w') as f:
		f.writelines([gameBaseName + ".exe --debug", "pause"])

	#make the following files executable, if they exist
	makeExecutableList = [
		os.path.join(conf.installPath, "Umineko1to4"),
		os.path.join(conf.installPath, "Umineko1to4.app/Contents/MacOS/umineko4"),
		os.path.join(conf.installPath, "Umineko5to8"),
		os.path.join(conf.installPath, "Umineko5to8.app/Contents/MacOS/umineko8")
	]

	for exePath in makeExecutableList:
		if os.path.exists(exePath):
			makeExecutable(exePath)

	# Patched game uses mysav folder, which Steam can't see so can't get incompatible saves by accident.
	# Add batch file which reverses this behaviour by making a linked folder from (saves->mysav)
	with open(os.path.join(conf.installPath, "EnableSteamSync.bat"), 'w') as f:
		f.writelines(["mklink saves mysav /J", "pause"])

	# For now, don't copy save data

	# Open the temp folder so users can delete/backup any temp install files
	if IS_WINDOWS:
		tryShowFolder(downloadTempDir)






# gameTypes = set(x.gameType for x in gameInstallConfigs)
#
# print("Game types: ", gameTypes)
#
# # for config in gameInstallConfigs:
# # 	print("Mod types: ", config.gameConfig["modTypes"])
#
# for config in gameInstallConfigs:
# 	print("Options for ", config.gameConfig["name"], "at", config.gamePath)
# 	for optionName, optionDetails in config.gameConfig["files"].items():
# 		print("\t- {}: Supports {}".format(optionName, optionDetails["os"]))

# print("Getting latest mod info (Umineko)...")
# modList = getModList("https://raw.githubusercontent.com/07th-mod/resources/master/uminekoInstallData.json")
#
# gamePathList = [gamePath for gamePath in findPossibleGamePaths("Umineko") if getUminekoGameInformationFromGamePath(modList, gamePath) is not None]
# print("Detected {} game folders: {}".format(len(gamePathList), gamePathList))
#
# userSelectedGamePath = promptChoice(
# 	rootGUIWindow=rootWindow,
# 	choiceList= gamePathList,
# 	guiPrompt="Please choose a game to mod",
# 	canOther=True
# )
#
# print("Selected game folder: [{}]".format(userSelectedGamePath))
# gameInfo = getUminekoGameInformationFromGamePath(modList, userSelectedGamePath)
# print("Selected Game Information:")
# pp.pprint(gameInfo)

# userSl
# gameInfo = gameInstallConfig.gameConfig

# isQuestionArcs = None
# modNames = None
# if gameInfo['name'] == 'UminekoAnswer':
# 	modNames = UMINEKO_ANSWER_MODS
# 	isQuestionArcs = False
# elif gameInfo['name'] == 'UminekoQuestion':
# 	modNames = UMINEKO_QUESTION_MODS
# 	isQuestionArcs = True
# else:
# 	print("Unknown Umineko game [{}]".format(gameInfo['name']))
# 	exitWithError()
#
# # ask user which mod they want to apply to their game
# userSelectedMod = promptChoice(
# 	rootGUIWindow=rootWindow,
# 	choiceList=modNames,
# 	guiPrompt="Please choose which mod to install for " + gameInfo['displayName'],
# 	canOther=False
# )
#
# installUmineko(gameInfo, userSelectedMod, pathToInstall, isQuestionArcs)
