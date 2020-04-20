from __future__ import unicode_literals

import glob
import json
import re

import common
import os
import subprocess
import traceback

import installConfiguration
import logger

try:
	from typing import List, Optional
except ImportError:
	pass # Just needed for pycharm comments

def findPossibleGamePathsWindows():
	"""
	Blindly retrieve all game folders in the `Steam\steamappps\common` folder (no filtering is performed)
	TODO: scan other locations than just the steamapps folder
	:return: a list of absolute paths, which are the folders in the `Steam\steamappps\common` folder
	:rtype: list[str]
	"""
	try:
		import winreg
	except ImportError:
		import _winreg as winreg

	allSteamPaths = []
	try:
		try:
			registryKey = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam')
		except WindowsError:
			# I installed Steam on a Win 10 64-bit machine and it used this alternate registry key location. Not sure why.
			registryKey = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'Software\Wow6432Node\Valve\Steam')

		defaultSteamPath, _regType = winreg.QueryValueEx(registryKey, 'SteamPath')
		allSteamPaths.append(defaultSteamPath)
		winreg.CloseKey(registryKey)
	except WindowsError:
		print("findPossibleGamePaths: Couldn't read Steam registry key - Steam not installed?")
		return []

	# now that we know the steam path, search the "Steam\config\config.vdf" file for extra install paths
	# this is a purely optional step, so it's OK if it fails
	try:
		import io
		baseInstallFolderRegex = re.compile(r'^\s*"BaseInstallFolder_\d+"\s*"([^"]+)"', re.MULTILINE)
		steamConfigVDFLocation = os.path.join(defaultSteamPath, r'config\config.vdf')
		with io.open(steamConfigVDFLocation, 'r', encoding='UTF-8') as configVDFFile:
			allSteamPaths += baseInstallFolderRegex.findall(configVDFFile.read())
	except Exception as e:
		traceback.print_exc()

	logger.printNoTerminal("Will scan the following steam install locations: {}".format(allSteamPaths))

	# normpath added so returned paths have consistent slash directions (registry key has forward slashes on Win...)
	try:
		allPossibleGamePaths = []

		for steamCommonPath in (os.path.join(steamPath, r'steamapps\common') for steamPath in allSteamPaths):
			for gameFolderName in os.listdir(steamCommonPath):
				gameFolderPath = os.path.join(steamCommonPath, gameFolderName)
				if os.path.isdir(gameFolderPath):
					allPossibleGamePaths.append(
						os.path.normpath(
							gameFolderPath
						)
					)

		return allPossibleGamePaths
	except:
		print("findPossibleGamePaths: Couldn't open registry key folder - Steam folder deleted?")
		return []

	return []

# Get paths which COULD be game paths.
def getMaybeGamePaths():
	"""
	If supported, searches the computer for things that might be Higurashi games
	Currently only does things on Mac OS and Windows
	TODO: Find ways to search for games on Linux

	:param str gameName: The name of the game to search for (should be either "Higurashi" or "Umineko"), used to reduce the time spent searching on Mac OS
	:return: A list of game paths that might be Higurashi games
	:rtype: list[str]
	"""
	allPossibleGamePaths = []

	if common.Globals.IS_WINDOWS:
		allPossibleGamePaths.extend(findPossibleGamePathsWindows())

	if common.Globals.IS_MAC:
		# mdfind is kind of slow, don't run it more than we have to
		allPossibleGamePaths.extend(
			x for x in subprocess.check_output(["mdfind", "kMDItemContentType == com.apple.application-bundle && ** == '*Higurashi*'"])
				.decode("utf-8")
				.split("\n") if x
		)

		for gamePath in subprocess.check_output(["mdfind", "kMDItemContentType == com.apple.application-bundle && ** == '*Umineko*'"]).decode("utf-8").split("\n"):
			allPossibleGamePaths.append(gamePath)
			# GOG installer makes a `.app` that contains the actual game at `/Contents/Resources/game`
			gogPath = os.path.join(gamePath, "Contents/Resources/game")
			if os.path.exists(gogPath):
				allPossibleGamePaths.append(gogPath)

	# Scan hardcoded paths for game subfolders
	hardCodedGameContainingPaths = []
	if common.Globals.IS_MAC:
		hardCodedGameContainingPaths.append("~/Library/Application Support/Steam/steamapps/common/")
	if common.Globals.IS_WINDOWS:
		hardCodedGameContainingPaths.append("c:/games/Mangagamer")
	if common.Globals.IS_LINUX:
		hardCodedGameContainingPaths.append("~/.steam/steam/steamapps/common/")
		hardCodedGameContainingPaths.append("~/.steam/steambeta/steamapps/common/")

	for hardCodedPathNotNormalized in hardCodedGameContainingPaths:
		hardCodedPath = os.path.realpath(os.path.expanduser(hardCodedPathNotNormalized))
		try:
			for gameFolderName in os.listdir(hardCodedPath):
				gameFolderPath = os.path.normpath(os.path.join(hardCodedPath, gameFolderName))
				if os.path.isdir(gameFolderPath):
					allPossibleGamePaths.append(gameFolderPath)
		except:
			print("Warning: Failed to scan hard coded path: {}".format(hardCodedPath))

	# if all methods fail, return empty list
	return sorted(allPossibleGamePaths)

def getPossibleIdentifiersFromFolder(folderPath):
	# type: (str) -> List[str]
	# Given a folder, retrieves the possible identifiers for that folder

	if not os.path.exists(folderPath):
		print("WARNING: getPossibleIdentifiersFromPath() on path [{}] but path didn't exist".format(folderPath))
		return []

	if not os.path.isdir(folderPath):
		print("WARNING: getPossibleIdentifiersFromPath() on path [{}] but path is not a folder".format(folderPath))
		return []

	infoPlist = os.path.join(folderPath, "Contents/Info.plist")
	if common.Globals.IS_MAC and os.path.exists(infoPlist):
		try:
			info = subprocess.check_output(
				["plutil", "-convert", "json", "-o", "-", infoPlist]
			)
			parsed = json.loads(info)
			name = parsed["CFBundleExecutable"] + "_Data" # type: str
			# GoG Umineko installs will be formatted like this but we *don't* want to use it
			if name.startswith("Higurashi"):
				return [name]
			else:
				return []
		except (subprocess.CalledProcessError, KeyError):
			pass

	return os.listdir(folderPath)


def scanForFullInstallConfigs(subModConfigList, possiblePaths=None, scanExtraPaths=True):
	# type: (List[installConfiguration.SubModConfig], [str], bool) -> [installConfiguration.FullInstallConfiguration]
	"""
	This function has two purposes:
		- When given a specific game path ('possiblePaths' argument), it checks if any of the given SubModConfig
		  can be installed into that path. Each SubModConfig which can be installed into that path will be returned
		  as a FullInstallConfiguration object.

		- When not given a specific game path, it searches the computer for valid installations where the given
		  SubModConfig could be installed to. Each valid (installation + SubModConfig) combination will be returned
		  as a FullInstallConfiguration object.

	:param subModConfigList: A **list** of SubModConfig which are to be searched for on disk
	:param possiblePaths: (Optional) Specify folders to check if the given SubModConfig can be installed into that path.
	:return:    A list of FullInstallConfig, each representing a valid install path that the
				given SubModConfig(s) couldbe installed into.
	"""

	returnedFullConfigs = []
	pathsToBeScanned = possiblePaths

	if not pathsToBeScanned:
		pathsToBeScanned = getMaybeGamePaths()

	# Build a mapping from subModIdentifier -> List[subMod]
	# This tells us, for each identifier, which subMods are compatible with that identifier (can be installed)
	# In all our games, the identifiers are the same for each subMod (but different for each Mod),
	# but it is easier to work with in the installer if we work with subMods

	from collections import defaultdict
	subModConfigDictionary = defaultdict(list) #type: defaultdict[List[SubModConfig]]
	for subMod in subModConfigList:
		for identifier in subMod.identifiers:
			subModConfigDictionary[identifier].append(subMod)

	if scanExtraPaths:
		extraPaths = []
		for gamePath in pathsToBeScanned:
			# MacOS: Any subpath with '.app' is also checked in case the containing path was manually entered
			extraPaths.extend(glob.glob(os.path.join(gamePath, "*.app")))
			# GOG Linux: Higurashi might be inside a 'game' subfolder
			extraPaths.extend(glob.glob(os.path.join(gamePath, "game")))

		pathsToBeScanned += extraPaths

	logger.printNoTerminal("Scanning:\n\t- " + "\n\t- ".join(pathsToBeScanned))

	for gamePath in pathsToBeScanned:
		possibleIdentifiers = getPossibleIdentifiersFromFolder(gamePath)
		subModConfigsInThisGamePath = set()
		for possibleIdentifier in possibleIdentifiers:
			try:
				possibleSteamPaths = [
					os.path.join(gamePath, "steam_api.dll"),
					os.path.join(gamePath, "Contents/Plugins/CSteamworks.bundle"),
					os.path.join(gamePath, "libsteam_api.so")
				]

				isSteam = False
				for possibleSteamPath in possibleSteamPaths:
					if os.path.exists(possibleSteamPath):
						isSteam = True

				# Add each submod which is compatible with the found identifier, unless it has already been detected at this path.
				for subModConfig in subModConfigDictionary[possibleIdentifier]:
					if subModConfig not in subModConfigsInThisGamePath:
						subModConfigsInThisGamePath.add(subModConfig)
						returnedFullConfigs.append(installConfiguration.FullInstallConfiguration(subModConfig, gamePath, isSteam))
						print("Found Game [{}] at [{}] id [{}]".format(subModConfig.modName, gamePath, possibleIdentifier))

			except KeyError:
				pass

	return returnedFullConfigs

def scanUserSelectedPath(subModConfigList, gameExecutablePath):
	# type: (List[SubModConfig], [str]) -> ([FullInstallConfiguration], str)
	"""
	Scans a user-selected path for configs. Unlike the normal "scanForFullInstallConfigs()" function,
	this will attempt to search all parent directories, incase a user has selected a subdirectory of the game directory
	by accident.
	:param subModConfigList:
	:param gameExecutablePath: A path to the game executable, or to a folder containing the game.
	:return: A tuple - The first is an array of valid FullInstallConfigurations.
					 - The second is an error message (on success a 'success' message is generated)
	"""
	if gameExecutablePath:
		if os.path.isfile(gameExecutablePath):
			gameExecutablePath = os.path.dirname(gameExecutablePath)

		# Search upwards for the game path, in case user has selected a deep subfolder of the game path
		alreadyScanned = set()
		for scanAttempt in range(10):
			fullInstallConfigs = scanForFullInstallConfigs(subModConfigList=subModConfigList,
			                                               possiblePaths=[gameExecutablePath],
			                                               scanExtraPaths= scanAttempt==0)
			if fullInstallConfigs:
				return fullInstallConfigs, "scanUserSelectedPath(): Path [{}] Ok".format(gameExecutablePath)

			alreadyScanned.add(gameExecutablePath)
			gameExecutablePath = os.path.dirname(gameExecutablePath)
			if gameExecutablePath in alreadyScanned:
				break

		# Failed to find path. Notify user which paths tried to be searched to find the file.
		errorStrings = ["scanUserSelectedPath(): Can't install the mod. Searched:"] + sorted(list(alreadyScanned))
		errorMessage = '\n - '.join(errorStrings)
		return None, errorMessage

	return None, "scanUserSelectedPath(): game executable path is falsey: [{}]".format(gameExecutablePath)
