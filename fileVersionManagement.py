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
	remoteVersionURL = "https://raw.githubusercontent.com/drojf/python-patcher/master/versionData.json"

	def __init__(self, subMod, modFileList, localVersionFilePath):
		#type: (installConfiguration.SubModConfig, List[installConfiguration.ModFile], str) -> None
		self.targetID = subMod.modName + '/' + subMod.subModName
		self.unfilteredModFileList = modFileList
		self.localVersionFilePath = localVersionFilePath
		self.localVersionObject, localError = common.getJSON(localVersionFilePath, isURL=False)

		# The remote JSON stores a version dict for each mod-subMod pair. Extract only the one that we want
		self.remoteVersionObject = None

		if common.Globals.DEVELOPER_MODE and os.path.exists("versionData.json"):
			allRemoteVersions, remoteError = common.getJSON("versionData.json", isURL=False)
		else:
			allRemoteVersions, remoteError = common.getJSON(VersionManager.remoteVersionURL, isURL=True)


		# Check the remote submod matches the game/submod pair to be installed
		if allRemoteVersions is not None:
			for remoteVersion in allRemoteVersions:
				if remoteVersion['id'] == self.targetID:
					self.remoteVersionObject = remoteVersion
					break

		if remoteError is not None:
			print("Error retrieving remote version".format(remoteError))

		self.logJSONVersions()

		# In theory can always re-install everything if can't get the remote server, but most likely it means
		# remote version this indicates an error with the server, so halt if this happens.
		if self.remoteVersionObject is None:
			raise Exception("Can't get version information for {} from server! Installation stopped.".format(self.targetID))

	def getFilesRequiringUpdate(self):
		#type: () -> (List[installConfiguration.ModFile], bool)
		""" :return: returns a modified mod file list consisting of files which require update AND
		a boolean value indicating whether a full update is needed"""
		updatedFileList = self.unfilteredModFileList

		if self.localVersionObject is None or self.remoteVersionObject is None:
			for file in self.unfilteredModFileList:
				file.updateReason = "Failed to retreive version information from local or remote"
		else:
			updatedFileList = filterFileListInner(self.unfilteredModFileList, self.localVersionObject, self.remoteVersionObject)

		print("\nInstaller Update Information:")
		for file in updatedFileList:
			print("Updating [{}] because [{}]".format(file.id, file.updateReason))

		return updatedFileList, set(updatedFileList) == set(self.unfilteredModFileList)

	def saveVersionsToFile(self):
		""" After install is successful, call this function to save the remote version info to local file """
		with io.open(self.localVersionFilePath, 'w', encoding='utf-8') as file:
			file.write(json.dumps(self.remoteVersionObject, ensure_ascii=False, encoding='utf-8'))

	def logJSONVersions(self):
		logger.printNoTerminal("\nLocal Version:")
		if self.localVersionObject:
			logger.printNoTerminal(json.dumps(self.localVersionObject, indent=4, sort_keys=True))
		else:
			logger.printNoTerminal("No Local Version Information!")

		logger.printNoTerminal("Remote Version:")
		if self.remoteVersionObject:
			logger.printNoTerminal(json.dumps(self.remoteVersionObject, indent=4, sort_keys=True))
		else:
			logger.printNoTerminal("No Remote Version Information!")


# given a mod
def filterFileListInner(modFileList, localJSONObject, remoteJSONObject):
	#type: (List[installConfiguration.ModFile], Dict, Dict) -> List[installConfiguration.ModFile]

	# Do a sanity check that all the mod files have unique IDs. If they don't, just assume all files need to be updated
	sanityCheckSet = set()
	for file in modFileList:
		if file.id in sanityCheckSet:
			print("ERROR: duplicate file ID {} detected - just updating everything", file.id)
			return modFileList
		sanityCheckSet.add(file.id)

	localVersionInfo = SubModVersionInfo(localJSONObject)
	remoteVersionInfo = SubModVersionInfo(remoteJSONObject)
	updatesRequiredDict = SubModVersionInfo.getFilesNeedingInstall(localVersionInfo, remoteVersionInfo)

	updateSet = set()

	# Get the list of files which either have no version status or require an update
	# needUpdate can be three values:
	# - True: The file definitely needs an update as the version is different
	# - False: The file definitely DOES NOT need an update as the version is the same
	# - None: The version info is missing on either the local or remote side. Since status is unknown, do an update.
	# Since we want to be safe, only remove the file if the status is False
	directUpdateList = []
	for file in modFileList:
		result = updatesRequiredDict.get(file.id)
		if result is None:
			needUpdate, updateReason = True, "Missing version info"
		else:
			needUpdate, updateReason = result

		file.updateReason = updateReason
		if needUpdate is not False:
			directUpdateList.append(file)
			updateSet.add(file.id)

	# Add dependencies of the above files which need updates to the update set
	# For example, if there is an "graphics-update" pack, it must always overwrite the "graphics" pack,
	# even if it has not changed.
	debug_dependency_list = []
	for file in directUpdateList:
		for otherFile in modFileList:
			if otherFile.priority > file.priority and otherFile.id not in updateSet:
				updateSet.add(otherFile.id)
				debug_dependency_list.append(otherFile.id)
				otherFile.updateReason = "{} is a dependency of {}".format(file.id, otherFile.id)

	# Convert the update set back into a modfile list
	return [x for x in modFileList if x.id in updateSet]


class SubModVersionInfo:
	def __init__(self, jsonObject):
		"""
		:param jsonObject:
		:param id: The ID is of the form "Onikakushi Ch.1/full". Local JSON have this ID saved in them, but remote
		"""
		self.jsonObject = jsonObject
		self.id = jsonObject['id']
		self.fileVersionsDict = {} #type: Dict[str, FileVersion]
		for row in jsonObject['files']:
			self.fileVersionsDict[row['id']] = FileVersion(row['id'], row['version'])

	# There are four cases when a file should be installed:
	# - There is no previous install info
	# - The previous install was a different submod (for example, installing 'full' onto 'voice-only')
	# - The file is not at all installed. This will trigger on UI mods of different versions, an unmodded game,
	#   or when you add a new file to an existing mod
	# - The remote version of the file does not match.
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
			return installAll("No local version info")

		if localVersionInfo.id != remoteVersionInfo.id:
			return installAll("A Different submod is installed")

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
			updatesRequired[remoteID] = False, "Version are the same"

		return updatesRequired


class FileVersion:
# 	# NOTE: the "id" can be different from the 'name'
# 	# This is because in the file list, the overriden files have the same name as the 'normal' files
# 	# The ID for a 'normal' file is 'name', but the ID for an overriden file is the 'overrideName'.
# 	# This allows us to determine which file was previously installed, even if the 'name' field is the same.
	def __init__(self, id, version):
		# type: (str, str) -> None
		self.id = id
		self.version = version
#
	def equals(self, other):
		# type: (FileVersion) -> bool
		"""
		For now, we only check if the versions are equal/not equal, rather than
		whether there is a "newer" version.
		"""
		return self.version == other.version

	def __repr__(self):
		return "{}-{}".format(self.id, self.version)
