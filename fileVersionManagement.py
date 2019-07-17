import json

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
	def __init__(self, modFileList, localVersionFilePath, remoteVersionURL):
		self.unfilteredModFileList = modFileList
		self.localVersionFilePath = localVersionFilePath
		self.localVersionObject, _localError = common.getJSON(localVersionFilePath, isURL=False)
		self.remoteVersionObject, _remoteError = common.getJSON(remoteVersionURL, isURL=True)

		print("Local Version:")
		print(self.localVersionObject)
		print("Remote Version:")
		print(self.remoteVersionObject)

		# In theory can always re-install everything if can't get the remote server, but most likely it means
		# remote version this indicates an error with the server, so halt if this happens.
		if self.remoteVersionObject is None:
			raise Exception("Can't get version information from server! Installation stopped.")

	def getFilesRequiringUpdate(self):
		"""
		:return: returns a modified mod file list consisting of files which require update
		"""
		if self.localVersionObject is None or self.remoteVersionObject is None:
			return self.unfilteredModFileList

		return filterFileListInner(self.unfilteredModFileList, self.localVersionObject, self.remoteVersionObject)

	def saveVersionsToFile(self):
		"""
		After install is successful, call this function to save the remote version info to local file
		"""
		with open(self.localVersionFilePath, 'w', encoding='utf-8') as localFilePath:
			json.dump(self.remoteVersionObject, localFilePath)

# # note: modFileList must already include any fileOverrides (from buildFileListSorted() in FullInstallConfiguration
# def filterFileListOuter(modFileList, localVersionFilePath, remoteVersionURL):
# 	# type: (List[installConfiguration.ModFile], str, str) -> (List[installConfiguration.ModFile], Dict)
# 	"""
#
# 	:param modFileList:
# 	:param localVersionFilePath:
# 	:param remoteVersionURL:
# 	:return: returns the mod file list of files which require update, and also the remote json dict which should
# 	         be saved to disk after install is completed
# 	"""
# 	localVersionObject, _localError = common.getJSON(localVersionFilePath, isURL=False)
# 	remoteVersionObject, _remoteError = common.getJSON(remoteVersionURL, isURL=True)
#
# 	if localVersionObject is None or remoteVersionObject is None:
# 		return modFileList
#
# 	filterFileListInner(modFileList, localVersionObject, remoteVersionObject), remoteVersionObject

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
	versionInformation = remoteVersionInfo.getFilesNeedingInstall(localVersionInfo)

	updateSet = set()

	# Get the list of files which either have no version status or require an update
	directUpdateList = []
	for file in modFileList:
		needUpdate = versionInformation.get(file.id)
		if needUpdate is not False:
			directUpdateList.append(file)
			updateSet.add(file.id)

	# Add dependencies of the above files which need updates to the update set
	for file in directUpdateList:
		print("If {} is updated, then need to update".format(file.name))
		for otherFile in modFileList:
			if otherFile.priority > file.priority:
				print("adding dependencey", otherFile.id)
				updateSet.add(otherFile.id)

	print("FullUpdateList", updateSet)

	# Convert the update set back into a modfile list
	return [x for x in modFileList if x.id in updateSet]


class SubModVersionInfo:
	def __init__(self, jsonObject):
		self.jsonObject = jsonObject
		self.subModName = jsonObject['subModName']
		self.fileVersionsDict = {} #type: Dict[str, FileVersion]
		for row in jsonObject['files']:
			self.fileVersionsDict[row['id']] = FileVersion(row['id'], row['version'])

	# There are four cases when a file should be installed:
	# - There is no previous install info
	# - The previous install was a different submod (for example, installing 'full' onto 'voice-only')
	# - The file is not at all installed. This will trigger on UI mods of different versions, an unmodded game,
	#   or when you add a new file to an existing mod
	# - The remote version of the file does not match.
	def getFilesNeedingInstall(self, local):
		# type: (Optional[SubModVersionInfo]) -> Dict[str, bool]
		""":type local: SubModVersionInfo"""

		# Assume that all files need to be installed
		updatesRequired = {}
		for fileVersion in self.fileVersionsDict.values():
			updatesRequired[fileVersion.id] = True

		if local is None:
			print("No local version info - full install required")
			return updatesRequired

		if local.subModName != self.subModName:
			print("Different submod is installed - full install required")
			return updatesRequired

		# Iterate through each file and and remove it if it does not need to be installed
		for remoteID, remoteVersion in self.fileVersionsDict.items():
			localVersion = local.fileVersionsDict.get(remoteID)

			if localVersion is None:
				print("Local does not have {} installed".format(remoteID))
				continue

			if not localVersion.equals(remoteVersion):
				print("Local is {} but latest is {}".format(localVersion, remoteVersion))
				continue

			# all checks passed, therefore file does not need to be installed.
			updatesRequired[remoteID] = False

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
