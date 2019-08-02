import io
import json
import os

import logger

try:
	from typing import List, Dict, Optional
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

	def __init__(self, subMod, modFileList, localVersionFolder, _testRemoteSubModVersion=None):
		#type: (installConfiguration.SubModConfig, List[installConfiguration.ModFile], str, Optional[SubModVersionInfo]) -> None
		self.targetID = subMod.modName + '/' + subMod.subModName
		self.unfilteredModFileList = modFileList
		self.localVersionFilePath = os.path.join(localVersionFolder, VersionManager.localVersionFileName)

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
			self.updatesRequiredDict = getFilesNeedingUpdate(self.unfilteredModFileList, self.localVersionInfo, self.remoteVersionInfo)

			print("\nInstaller Update Information:")
			for fileID, (needsUpdate, updateReason) in self.updatesRequiredDict.items():
				print("[{}]: status: [{}] because [{}]".format(fileID, needsUpdate, updateReason))

		# Check how many updates are required
		updatesRequiredList = self.updatesRequiredDict.values()
		self.totalNumUpdates = len(updatesRequiredList)
		self.numUpdatesRequired = sum([needsUpdate for (needsUpdate, _) in updatesRequiredList])
		print("Full Update: {} ({}/{}) excluding mod options".format(self.fullUpdateRequired(), self.numUpdatesRequired, self.totalNumUpdates))

	def fullUpdateRequired(self):
		return self.numUpdatesRequired == self.totalNumUpdates

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

		self.localVersionInfo.serialize(self.localVersionFilePath, lastAttemptedInstallID=self.remoteVersionInfo.id)

	# When install finishes, copy the remoteVersionInfo
	def saveVersionInstallFinished(self):
		if self.remoteVersionInfo is None:
			print("VersionManager: ERROR: Not saving remote version info as it couldn't be retrieved from server")
			return

		self.remoteVersionInfo.serialize(self.localVersionFilePath, lastAttemptedInstallID=self.remoteVersionInfo.id)

	@staticmethod
	def tryDeleteLocalVersionFile(localVersionFolder):
		localVersionFilePathToDelete = os.path.join(localVersionFolder, VersionManager.localVersionFileName)
		if os.path.exists(localVersionFilePathToDelete):
			os.remove(localVersionFilePathToDelete)

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
def getFilesNeedingUpdate(modFileList, localVersionInfo, remoteVersionInfo):
	#type: (List[installConfiguration.ModFile], SubModVersionInfo, SubModVersionInfo) -> ()
	"""

	:param modFileList:
	:param localVersionInfo:
	:param remoteVersionInfo:
	:return: the returned value will contain one entry for each item in the modFileList
	"""

	# Do a sanity check that all the mod files have unique IDs. If they don't, just assume all files need to be updated
	sanityCheckSet = set()
	for file in modFileList:
		if file.id in sanityCheckSet:
			print("ERROR: duplicate file ID {} detected - just updating everything", file.id)
			return
		sanityCheckSet.add(file.id)

	updatesRequiredDict = SubModVersionInfo.getFilesNeedingInstall(localVersionInfo, remoteVersionInfo)

	updateDict = {}

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

	def serialize(self, path, lastAttemptedInstallID):
		files = [{'id':fileVersion.id, 'version': fileVersion.version}
		         for fileVersion in self.fileVersionsDict.values()]

		obj = {
			'id': self.id,
			'files' : files,
			'lastAttemptedInstallID': lastAttemptedInstallID
		}

		with io.open(path, 'w', encoding='utf-8') as file:
			file.write(json.dumps(obj, ensure_ascii=False, indent=4, sort_keys=True))

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
			return installAll("Full Install Required - A Different submod is installed")

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
		return "id: {} lastAttemptedInstallID: {} files: {}"\
			.format(self.id, self.lastAttemptedInstallID, ", ".join([x.__repr__() for x in self.fileVersionsDict.values()]))

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
