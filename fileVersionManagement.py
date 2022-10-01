from __future__ import unicode_literals

import io
import json
import os
from datetime import datetime

import logger

try:
	from typing import List, Dict, Optional, Set, Tuple
except:
	pass

try:
	from urllib.request import urlopen, Request
	from urllib.parse import urlparse, quote
	from urllib.error import HTTPError
except ImportError:
	from urllib2 import urlopen, Request, HTTPError
	from urlparse import urlparse
	from urllib import quote

import common
import installConfiguration

class VersionManager:
	localVersionFileName = "installedVersionData.json"
	def userDidPartialReinstall(self, gameInstallTimeProbePath):
		"""
		:param gameInstallTimeProbePath: A file to probe to determine when the game was installed
		:return: True if user did a partial re-install. Returns false if not sure.
				Could possibly return True if user has been messing/copying their game folder around
		"""
		if not os.path.exists(self.localVersionFilePath) or not os.path.exists(gameInstallTimeProbePath):
			if self.verbosePrinting:
				print("userDidPartialReinstall: localVersionFilePath or gameInstallTimeProbePath was missing - assuming no partial reinstall")
			return False

		# If the game was installed AFTER when the mod was applied, user has probably partially re-installed the game
		# by using steam to uninstall, then re-install the game, rather than deleting the game folder fully
		# For the game files, the "created" date is the date the game was installed
		# For the version file, the "modified" date is when the game mod was last applied
		return os.path.getctime(gameInstallTimeProbePath) > os.path.getmtime(self.localVersionFilePath)

	def __init__(self, fullInstallConfiguration, modFileList, localVersionFolder, _testRemoteSubModVersion=None, verbosePrinting=True, repairMode=True):
		#type: (installConfiguration.FullInstallConfiguration, List[installConfiguration.ModFile], str, Optional[SubModVersionInfo], bool, bool) -> None
		subMod = fullInstallConfiguration.subModConfig
		self.verbosePrinting = verbosePrinting
		self.targetID = subMod.modName + '/' + subMod.subModName
		self.unfilteredModFileList = modFileList
		self.localVersionFilePath = os.path.join(localVersionFolder, VersionManager.localVersionFileName)

		modOptionParser = installConfiguration.ModOptionParser(fullInstallConfiguration)

		# Get remote and local versions
		try:
			self.localVersionInfo = getLocalVersion(self.localVersionFilePath)
		except Exception as error:
			self.localVersionInfo = None
			print("VersionManager: Error while retrieving version information: {}".format(error))

		# allow overriding the remote sub mod version for testing purposes
		if _testRemoteSubModVersion is not None:
			self.remoteVersionInfo = _testRemoteSubModVersion
		else:
			try:
				self.remoteVersionInfo = getRemoteVersion(self.targetID)
			except Exception as error:
				self.remoteVersionInfo = None
				print("VersionManager: Error while retrieving remote version information {}".format(error))

		if verbosePrinting:
			logger.printNoTerminal("\nLocal Version: {}".format(self.localVersionInfo))
			logger.printNoTerminal("Remote Version: {}".format(self.remoteVersionInfo))

		# If can't retrieve version info, mark everything as needing update
		if self.localVersionInfo is None:
			self.updatesRequiredDict = {}
			for file in self.unfilteredModFileList:
				self.updatesRequiredDict[file.id] = (True, "No local version information - Assuming update is required")
		elif self.remoteVersionInfo is None:
			self.updatesRequiredDict = {}
			for file in self.unfilteredModFileList:
				self.updatesRequiredDict[file.id] = (True, "Failed to retrieve remote version information")
		else:
			# Mark files which need update
			self.updatesRequiredDict = getFilesNeedingUpdate(self.unfilteredModFileList, self.localVersionInfo, self.remoteVersionInfo, repairMode=modOptionParser.repairMode)

			if verbosePrinting:
				print("\nInstaller Update Information:")
				for fileID, (needsUpdate, updateReason) in self.updatesRequiredDict.items():
					print("[{}]: status: [{}] because [{}]".format(fileID, needsUpdate, updateReason))

		# If file has 'skipIfModNewerThan' property, disable it if the mod install is older than the given date
		for file in self.unfilteredModFileList:
			if file.skipIfModNewerThan is not None and self.updatesRequiredDict[file.id][0]:
				installIsNewer, reason = installNewerThanDate(self.localVersionFilePath, file.skipIfModNewerThan)
				if installIsNewer:
					msg = "Not installing {} because: ({})".format(file.id, reason)
					self.updatesRequiredDict[file.id] = (False, "Not installing because you already have these files")
					if verbosePrinting:
						logger.printNoTerminal(msg)
				else:
					msg = "{} - Will install because: ({})".format(self.updatesRequiredDict[file.id][1], reason)
					self.updatesRequiredDict[file.id] = (self.updatesRequiredDict[file.id][0], "You are missing these files (judging from your last mod install date)")
					if verbosePrinting:
						logger.printNoTerminal(msg)



		# Check how many updates are required
		updatesRequiredList = self.updatesRequiredDict.values()
		self.totalNumUpdates = len(updatesRequiredList)
		self.numUpdatesRequired = sum([needsUpdate for (needsUpdate, _) in updatesRequiredList])
		if verbosePrinting:
			print("Full Update: {} ({}/{}) excluding mod options".format(self.fullUpdateRequired(), self.numUpdatesRequired, self.totalNumUpdates))

	def fullUpdateRequired(self):
		return self.localVersionInfo is None

	def getFilesRequiringUpdate(self):
		#type: () -> List[installConfiguration.ModFile]
		""" :return: returns a modified mod file list consisting of files which require update AND
		a boolean value indicating whether a full update is needed"""
		# Convert the update set back into a modfile list
		return [x for x in self.unfilteredModFileList if self.updatesRequiredDict[x.id][0]]

	# When install starts, mark which submod is attempted to be installed
	def saveVersionInstallStarted(self):
		if self.localVersionInfo is None:
			print("VersionManager: Not saving local version info as this is the 'first' install")
			return

		# Update the existing version info with new install id, in case the game/mod variant changed
		self.localVersionInfo.serialize(self.localVersionFilePath, lastAttemptedInstallID=self.remoteVersionInfo.id)

	# When install finishes, copy the remoteVersionInfo
	def saveVersionInstallFinished(self, forcedSaveFolder=None):
		if self.remoteVersionInfo is None:
			print("VersionManager: ERROR: Not saving remote version info as it couldn't be retrieved from server")
			return

		versionSavePath = self.localVersionFilePath
		if forcedSaveFolder is not None:
			versionSavePath = os.path.join(forcedSaveFolder, VersionManager.localVersionFileName)

		# Save only the version info of files which were relevant to the last installation
		# This includes:
		#  - Files installed on a previous installation, which were not updated on the latest install attempt
		#  - Files which were re-installed or installed for the first time on the latest install attempt
		self.remoteVersionInfo.serialize(versionSavePath,
										lastAttemptedInstallID=self.remoteVersionInfo.id,
										idsToSerialize={f.id for f in self.unfilteredModFileList})

	@staticmethod
	def deleteLocalVersionFileIfExists(localVersionFolder):
		localVersionFilePathToDelete = os.path.join(localVersionFolder, VersionManager.localVersionFileName)
		if os.path.exists(localVersionFilePathToDelete):
			os.remove(localVersionFilePathToDelete)


def installNewerThanDate(versionDataJsonPath, date):
	# type: (str, datetime) -> Tuple[bool, str]
	if not os.path.exists(versionDataJsonPath):
		now = datetime.now()
		if now > date:
			return True, "Unmodded install AND current time [{}] is NEWER than cutoff date [{}]".format(now, date)
		else:
			return False, "Unmodded install AND current time [{}] is OLDER than cutoff date [{}]".format(now, date)

	installDateModified = datetime.fromtimestamp(os.path.getmtime(versionDataJsonPath))

	if installDateModified > date:
		return True, "Modded install AND mod updated/installed on [{}] is NEWER than cutoff date [{}]".format(installDateModified, date)
	else:
		return False, "Modded install AND mod updated/installed on [{}] is OLDER than cutoff date [{}]".format(installDateModified, date)

def getLocalVersion(localVersionFilePath):
	localVersionObject, localError = common.getJSON(localVersionFilePath, isURL=False)
	return None if localVersionObject is None else SubModVersionInfo(localVersionObject)


def getRemoteVersion(remoteTargetID):
	remoteVersionURL = common.Globals.GITHUB_MASTER_BASE_URL + "versionData.json"

	# Get remote version
	if common.Globals.DEVELOPER_MODE and os.path.exists("versionData.json"):
		allRemoteVersions, remoteError = common.getJSON("versionData.json", isURL=False)
	else:
		allRemoteVersions, remoteError = common.getJSON(remoteVersionURL, isURL=True)

	if remoteError is not None:
		print("Error retrieving remote version".format(remoteError))

	# The remote JSON stores a version dict for each mod-subMod pair. Extract only the one that we want
	remoteVersionObject = None
	if allRemoteVersions is not None:
		for remoteVersion in allRemoteVersions:
			if remoteVersion['id'] == remoteTargetID:
				remoteVersionObject = remoteVersion
				break

	# In theory can always re-install everything if can't get the remote server, but most likely it means
	# remote version this indicates an error with the server, so halt if this happens.
	if remoteVersionObject is None:
		raise Exception("Can't get version information for {} from server! Installation stopped.".format(remoteTargetID))

	return SubModVersionInfo(remoteVersionObject)


# given a mod
def getFilesNeedingUpdate(modFileList, localVersionInfo, remoteVersionInfo, repairMode):
	#type: (List[installConfiguration.ModFile], SubModVersionInfo, SubModVersionInfo, bool) -> Dict[str, Tuple[bool, str]]
	"""

	:param modFileList:
	:param localVersionInfo:
	:param remoteVersionInfo:
	:return: the returned value will contain one entry for each item in the modFileList
	"""

	# Do a sanity check that all the mod files have unique IDs
	sanityCheckSet = set()
	for file in modFileList:
		if file.id in sanityCheckSet:
			raise Exception("ERROR: duplicate file ID {} detected".format(file.id))
		sanityCheckSet.add(file.id)

	updatesRequiredDict = SubModVersionInfo.getFilesNeedingInstall(localVersionInfo, remoteVersionInfo)

	# This is a dictionary mapping the ID to a tuple of (shouldUpdate: bool, updateReason: str)
	updateDict = {} #type: Dict[str, Tuple[bool, str]]

	# Get the list of files which either have no version status or require an update
	# needUpdate can be three values:
	# - True: The file definitely needs an update as the version is different
	# - False: The file definitely DOES NOT need an update as the version is the same
	# - None: The version info is missing on either the local or remote side. Since status is unknown, do an update.
	# Since we want to be safe, only remove the file if the status is False
	directUpdateList = []
	for file in modFileList:
		result = updatesRequiredDict.get(file.id)
		needUpdate, updateReason = (True, "Missing version info") if result is None else result

		if not needUpdate and repairMode and file.installOnRepair:
			needUpdate = True
			updateReason = "Re-installing as Repair Mode Enabled"

		updateDict[file.id] = (needUpdate, updateReason)
		if needUpdate:
			directUpdateList.append(file)

	# Add dependencies of the above files which need updates to the update set
	# For example, if there is an "graphics-update" pack, it must always overwrite the "graphics" pack,
	# even if it has not changed.
	debug_dependency_list = []
	for file in directUpdateList:
		for otherFile in modFileList:
			if otherFile.priority > file.priority:
				# don't overwrite existing reason if the item is already to be updated
				if updateDict[otherFile.id][0] is not True:
					debug_dependency_list.append(otherFile.id)
					updateDict[otherFile.id] = (True, "{} is a dependency of {}".format(otherFile.id, file.id))

	# At this point, updateDict will contain one entry for each file in modFileList
	return updateDict

class SubModVersionInfo:
	def __init__(self, jsonObject):
		"""
		:param jsonObject:
		"""
		self.id = jsonObject['id']
		self.fileVersionsDict = {} #type: Dict[str, FileVersion]
		for row in jsonObject['files']:
			self.fileVersionsDict[row['id']] = FileVersion(row['id'], row['version'])
		self.lastAttemptedInstallID = jsonObject.get('lastAttemptedInstallID')

	def serialize(self, path, lastAttemptedInstallID, idsToSerialize=None):
		def selectorFunction(id):
			if idsToSerialize is None:
				return True
			else:
				return id in idsToSerialize

		files = [{'id':fileVersion.id, 'version': fileVersion.version}
		         for fileVersion in self.fileVersionsDict.values() if selectorFunction(fileVersion.id)]

		obj = {
			'id': self.id,
			'files' : files,
			'lastAttemptedInstallDate': datetime.now().strftime("%Y-%m-%d %I:%M:%S %p"),
			'lastAttemptedInstallID': lastAttemptedInstallID
		}

		json_string = json.dumps(obj, ensure_ascii=False, indent=4, sort_keys=True)

		with io.open(path, 'w', encoding='utf-8') as file:
			file.write(json_string)

	# There are five cases when a file should be installed:
	# - There is no previous install info
	# - The previous install was a different submod (for example, installing 'full' onto 'voice-only')
	# - The file is not at all installed. This will trigger on UI mods of different versions, an unmodded game,
	#   or when you add a new file to an existing mod
	# - The remote version of the file does not match.
	# - A partial install was started on one submod, but we want to start a new install on a different submod (need to do a full install)
	@staticmethod
	def getFilesNeedingInstall(localVersionInfo, remoteVersionInfo):
		# type: (Optional[SubModVersionInfo], Optional[SubModVersionInfo]) -> Dict[str, (bool, str)]
		"""
		:type local: SubModVersionInfo
		:return a dict of (fileID, (needUpdate, reason)), where reason is a string describing why an update is required
		"""

		def installAll(reason):
			updatesRequired = {}
			for remoteVersion in remoteVersionInfo.fileVersionsDict.values():
				updatesRequired[remoteVersion.id] = True, reason
			return updatesRequired

		if localVersionInfo is None:
			return installAll("Full Install Required - No local version info")

		if localVersionInfo.id != remoteVersionInfo.id:
			return installAll("Full Install Required to overwrite existing mod - [{}] is currently installed, but want to install [{}]".format(localVersionInfo.id, remoteVersionInfo.id))

		if localVersionInfo.lastAttemptedInstallID is None:
			return installAll("Full Install Required - Missing last attempted install ID")

		if localVersionInfo.lastAttemptedInstallID != remoteVersionInfo.id:
			return installAll("Full Install Required - The last attempted install was [{}] but target/remote install is [{}]"
			                  .format(localVersionInfo.lastAttemptedInstallID, remoteVersionInfo.id))

		# Iterate through each file and and remove it if it does not need to be installed
		updatesRequired = {}
		for remoteID, remoteVersion in remoteVersionInfo.fileVersionsDict.items():
			localVersion = localVersionInfo.fileVersionsDict.get(remoteID)

			if localVersion is None:
				updatesRequired[remoteID] = True, "Local does not have {} installed".format(remoteID)
				continue

			if not localVersion.equals(remoteVersion):
				updatesRequired[remoteID] = True, "Local is {} but latest is {}".format(localVersion, remoteVersion)
				continue

			# all checks passed, therefore file does not need to be installed.
			updatesRequired[remoteID] = False, "No update required - Local {} is up-to-date".format(localVersion)

		return updatesRequired

	def __repr__(self):
		return "id: {} lastAttemptedInstallID: {} files:\n - {}"\
			.format(self.id, self.lastAttemptedInstallID, "\n - ".join([x.__repr__() for x in self.fileVersionsDict.values()]))

class FileVersion:
# 	# NOTE: the "id" can be different from the 'name'
# 	# This is because in the file list, the overriden files have the same name as the 'normal' files
# 	# The ID for a 'normal' file is 'name', but the ID for an overriden file is the 'overrideName'.
# 	# This allows us to determine which file was previously installed, even if the 'name' field is the same.
	def __init__(self, id, version):
		# type: (str, str) -> None
		self.id = id
		self.version = version

	def equals(self, other):
		# type: (FileVersion) -> bool
		"""
		For now, we only check if the versions are equal/not equal, rather than
		whether there is a "newer" version.
		"""
		return self.version == other.version

	def __repr__(self):
		return "{}-{}".format(self.id, self.version)

def Developer_ValidateVersionDataJSON(modList):
	#type: (List[installConfiguration.SubModConfig]) -> None

	onDiskVersionData, error = common.getJSON("versionData.json", isURL=False)

	# reformat versionData as mapping of { subModID : set(file.id) }
	reformattedVersionData = {}  # type: Dict[str, Set[str]]
	for versionData in onDiskVersionData:
		reformattedVersionData[versionData['id']] = set(file['id'] for file in versionData['files'])

	failureStrings = []
	for subMod in modList:
		# The ID in the versionData.json is of the format "game/mod_variant"
		subModID = subMod.modName + '/' + subMod.subModName

		# Check versionData has a listing for this submod
		if subModID not in reformattedVersionData:
			failureStrings.append(
				"DEVELOPER ERROR: versionData.json is missing the game/submod pair: {}".format(subModID))
			continue

		# Check for duplicate ids in installData.json
		dup_ids_check = set()
		for file in subMod.files + subMod.fileOverrides:
			if file.id in dup_ids_check:
				failureStrings.append(
					"DEVELOPER ERROR: In versionData.json, [{}] is has duplicate id [{}]".format(
						subModID, file.id))
			else:
				dup_ids_check.add(file.id)

		# Check each file in the submod exists in the versionData.json
		for file in subMod.files + subMod.fileOverrides:
			# Items with file.url = None are not downloaded/installed, so skip them
			if file.url is None:
				continue

			if file.id not in reformattedVersionData[subModID]:
				failureStrings.append(
					"DEVELOPER ERROR: In versionData.json, [{}] is missing [{}]".format(
						subModID, file.id))

	if failureStrings:
		raise Exception('\n'.join(failureStrings))
