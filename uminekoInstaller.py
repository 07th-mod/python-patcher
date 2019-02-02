from common import *
import os, shutil, subprocess

################################################## UMINEKO INSTALL #####################################################

UMINEKO_ANSWER_MODS = ["mod_voice_only", "mod_full_patch", "mod_adv_mode"]
UMINEKO_QUESTION_MODS = ["mod_voice_only", "mod_full_patch", "mod_1080p"]
umi_debug_mode = False

def uminekoDownload(downloadTempDir, url_list):
	print("Downloading:{} to {}".format(url_list, downloadTempDir))
	makeDirsExistOK(downloadTempDir)

	for url in url_list:
		print("will try to download {} into {} ".format(url, downloadTempDir))
		if not umi_debug_mode:
			if aria(downloadTempDir, url=url) != 0:
				print("ERROR - could not download [{}]. Installation Stopped".format(url))
				exitWithError()


def uminekoExtractAndCopyFiles(fromDir, toDir):
	"""
	This function extracts all archives from the "fromDir" to the "toDir". It also will copy any files in the "fromDir"
	to the "toDir". Finally, if there are any *.utf files in the fromDir, they will be renamed to 0.u in the "toDir"
	depending on the operating system.

	NOTE: this function makes some assumptions about the archive files:
	- all archive files have either the extension .7z, .zip (or both)
	- the archives are intended to be extracted in the order: 'graphics' 'voices' 'update', then any other type of archive

	:param fromDir: source directory to copy/extract files from
	:param toDir: destination directory to place copied/extracted files
	:return: None
	"""
	def sortingFunction(filenameAnyCase):
		filename = filenameAnyCase.lower()
		if 'graphics' in filename:
			return 0
		elif 'voices' in filename:
			return 1
		elif 'update' in filename:
			return 2
		else:
			return 3

	print("extracting from {} to {}".format(fromDir, toDir))

	archives = []
	otherFiles = []

	for filename in os.listdir(fromDir):
		if '.7z' in filename.lower() or '.zip' in filename.lower():
			archives.append(filename)
		else:
			otherFiles.append(filename)

	#sort the archive files so they are extracted in the correct order
	archives.sort(key=sortingFunction)

	for archive_name in archives:
		archive_path = os.path.join(fromDir, archive_name)
		print("Trying to extract file {} to {}".format(archive_path, toDir))
		if not umi_debug_mode:
			if sevenZipExtract(archive_path, outputDir=toDir) != 0:
				print("ERROR - could not extract [{}]. Installation Stopped".format(archive_path))
				exitWithError()

	#copy all non-archive files to the game folder. If a .utf file is found, rename it depending on the OS
	for sourceFilename in otherFiles:
		fileNameNoExt, extension = os.path.splitext(sourceFilename)

		destFilename = sourceFilename

		#on any OS besides MAC, rename 0.utf files to 0.u files. On mac, leave filenames unchanged.
		if not IS_MAC and extension.lower() == '.utf':
			destFilename = fileNameNoExt + '.u'

		sourceFullPath = os.path.join(fromDir, sourceFilename)
		destFullPath = os.path.join(toDir, destFilename)

		print("Trying to copy", sourceFullPath, "to", destFullPath)
		shutil.copy(sourceFullPath, destFullPath)

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

def installUmineko(gameInfo, modToInstall, gamePath, isQuestionArcs):
	print("User wants to install", modToInstall)
	print("game info:", gameInfo)
	print("game path:", gamePath)

	# do a quick verification that the directory is correct before starting installer
	if not os.path.isfile(os.path.join(gamePath, "arc.nsa")):
		print("There is no 'arc.nsa' in the game folder. Are you sure the correct game folder was selected?")
		print("ERROR - wrong game path. Installation Stopped.")
		exitWithError()

	# Create aliases for the temp directories, and ensure they exist beforehand
	downloadTempDir = os.path.join(gamePath, "temp")

	if os.path.isdir(downloadTempDir):
		print("Information: Temp directories already exist - continued or overwritten install")

		# TODO: move this voice only warning into GUI instead, or handle in some other way
		if "voice_only" in modToInstall:
			continueInstallation = messagebox.askyesno("Voice Only Warning",
			                       "We have detected you have run the 'Voice Only' installer before.\n\n" +
			                       "If you switching from 'full patch' to 'voice only', please quit the " +
			                       "installer and completely delete the game directory, then re-install the game\n\n" +
			                       "If you are just upgrading or continuing your voice only install, you can continue the installlation.\n\n" +
			                       "Continue the installation?")

			if not continueInstallation:
				print("User cancelled install (Voice Only)")
				exitWithError()

	makeDirsExistOK(downloadTempDir)

	# Wipe non-checksummed install files in the temp folder. Print if not a fresh install.
	deleteAllInPathExceptSpecified([downloadTempDir],
	                               extensions=['7z', 'zip'],
	                               searchStrings=['graphic', 'voice'])

	# Backup/clear the .exe and script files
	backupOrRemoveFiles(gamePath)

	def makeExecutable(executablePath):
		current = os.stat(executablePath)
		os.chmod(executablePath, current.st_mode | 0o111)

	# Download and extract files for Question/Answer Arcs
	uminekoDownload(downloadTempDir, url_list=gameInfo["files"][modToInstall]["files"])
	uminekoExtractAndCopyFiles(fromDir=downloadTempDir, toDir=gamePath)

	# Apply some fixes and add utility tools
	if isQuestionArcs:
		# need to un-quarantine .app file on MAC
		if IS_MAC:
			subprocess.call(["xattr", "-d", "com.apple.quarantine", os.path.join(gamePath, "Umineko1to4.app")])

		makeExecutable(os.path.join(gamePath, "Umineko1to4"))
		makeExecutable(os.path.join(gamePath, "Umineko1to4.app/Contents/MacOS/umineko4"))

		# write batch file to let users launch game in debug mode
		with open(os.path.join(gamePath, "Umineko1to4_DebugMode.bat"), 'w') as f:
			f.writelines(["Umineko1to4.exe --debug", "pause"])
	else:
		# need to un-quarantine .app file on MAC
		if IS_MAC:
			subprocess.call(["xattr", "-d", "com.apple.quarantine", os.path.join(gamePath, "Umineko5to8.app")])

		makeExecutable(os.path.join(gamePath, "Umineko5to8"))
		makeExecutable(os.path.join(gamePath, "Umineko5to8.app/Contents/MacOS/umineko8"))

		with open(os.path.join(gamePath, "Umineko5to8_DebugMode.bat"), 'w') as f:
			f.writelines(["Umineko5to8.exe --debug", "pause"])

	# Patched game uses mysav folder, which Steam can't see so can't get incompatible saves by accident.
	# Add batch file which reverses this behaviour by making a linked folder from (saves->mysav)
	with open(os.path.join(gamePath, "EnableSteamSync.bat"), 'w') as f:
		f.writelines(["mklink saves mysav /J", "pause"])

	# For now, don't copy save data

	# Open the temp folder so users can delete/backup any temp install files
	if IS_WINDOWS:
		tryShowFolder(downloadTempDir)

#do install given a installer config object
def mainUmineko(rootWindow, gameInstallConfigs):
	print("Installer got: ", gameInstallConfigs)

	gameTypes = set(x.gameType for x in gameInstallConfigs)

	print("Game types: ", gameTypes)

	# for config in gameInstallConfigs:
	# 	print("Mod types: ", config.gameConfig["modTypes"])

	for config in gameInstallConfigs:
		print("Options for ", config.gameConfig["name"], "at", config.gamePath)
		for optionName, optionDetails in config.gameConfig["files"].items():
			print("\t- {}: Supports {}".format(optionName, optionDetails["os"]))

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
