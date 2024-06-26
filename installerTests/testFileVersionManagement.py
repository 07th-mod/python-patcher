import json
import os
import shutil
import sys
import unittest
import tempfile

import common
import fileVersionManagement
import installConfiguration
import logger


def stripReason(idToNeedUpdateAndReasonDict):
	retVal = {}
	for id, (needUpdate, reason) in idToNeedUpdateAndReasonDict.items():
		retVal[id] = needUpdate
	return retVal

def convertUpdateInformationToModFileList(fileList, updateInformation):
	return [x for x in fileList if updateInformation[x.id][0]]

class TestSubModVersion(unittest.TestCase):
	localJSON = json.loads("""
	{
		"id" : "Onikakushi Ch.1/full",
		"lastAttemptedInstallID": "Onikakushi Ch.1/full",
		"files":[
			{"id": "cg",      "version": "1.0.0"},
			{"id": "cgalt",   "version": "1.0.0"},
			{"id": "movie-unity",   "version": "1.0.0"},
			{"id": "voices",  "version": "1.0.0"},
			{"id": "script",  "version": "6.1.0"}
		]
	}
	""")

	remoteJSON = json.loads("""
	{
		"id" : "Onikakushi Ch.1/full",
		"lastAttemptedInstallID": "Onikakushi Ch.1/full",
		"files": [
			{"id": "cg",      "version": "1.0.0"},
			{"id": "cgalt",   "version": "1.2.0"},
			{"id": "movie",   "version": "1.0.0"},
			{"id": "voices",  "version": "1.0.1"},
			{"id": "script",  "version": "6.2.0"}
		]
	}
	""")

	voiceOnlyJSON = json.loads("""
	{
		"id" : "Onikakushi Ch.1/voice-only",
		"lastAttemptedInstallID": "Onikakushi Ch.1/voice-only",
		"files": [
			{"id": "cg",      "version": "1.0.0"},
			{"id": "cgalt",   "version": "1.2.0"},
			{"id": "movie",   "version": "1.0.0"},
			{"id": "voices",  "version": "1.0.1"},
			{"id": "script",  "version": "6.2.0"}
		]
	}
	""")

	voiceWithFullPartiallyInstalledJSON = json.loads("""
	{
		"id" : "Onikakushi Ch.1/voice-only",
		"lastAttemptedInstallID": "Onikakushi Ch.1/full",
		"files": [
			{"id": "cg",      "version": "1.0.0"},
			{"id": "cgalt",   "version": "1.2.0"},
			{"id": "movie",   "version": "1.0.0"},
			{"id": "voices",  "version": "1.0.1"},
			{"id": "script",  "version": "6.2.0"}
		]
	}
	""")

	testInstallDataString = """
{
	"version": 4,
	"mods": [
		{
			"family": "higurashi",
			"name": "Onikakushi Ch.1",
			"target": "Onikakushi",
			"CFBundleName": "Higurashi When They Cry - Ch.1 Onikakushi",
			"dataname": "HigurashiEp01_Data",
			"identifiers" : ["HigurashiEp01_Data", "HigurashiEp01.x86_64", "HigurashiEp01.exe"],
			"submods": [
				{
					"name": "full",
					"descriptionID": "higurashiFull",
					"files":[
						{"name": "cg",      "url":"https://07th-mod.com/rikachama/graphics/Onikakushi-CG.7z",                "priority": 0},
						{"name": "cgalt",   "url":"https://07th-mod.com/rikachama/graphics/Onikakushi-CGAlt.7z",             "priority": 0},
						{"name": "movie",   "url":"https://07th-mod.com/rikachama/video/Onikakushi-Movie.7z",             "priority": 0},
						{"name": "voices",  "url":"https://07th-mod.com/rikachama/voice/Onikakushi-Voices.7z",            "priority": 0},
						{"name": "ui",      "url":null,                                                             "priority": 0},
						{"name": "script",  "url":"https://07th-mod.com/latest.php?repository=onikakushi",          "priority": 5}
					],
					"fileOverrides" : [
						{"name": "movie", "id": "movie-unix",  "os": ["mac", "linux"], "url":"https://07th-mod.com/rikachama/video/Onikakushi-Movie_UNIX.7z"},
						{"name": "ui",    "id": "ui-windows",  "os": ["windows"],      "unity": null, "url":"https://07th-mod.com/ui.php?chapter=onikakushi&os=win&unity=5.2.2f1"},
						{"name": "ui",    "id": "ui-unix" ,    "os": ["mac", "linux"], "unity": "5.2.2f1", "url":"https://07th-mod.com/ui.php?chapter=onikakushi&os=unix&unity=5.2.2f1"}
					]
				}
			],
			"modOptionGroups": [
				{
					"name" : "BGM Options", "type": "downloadAndExtract",
					"radio": [
						{"name": "Default BGM", "description": "Use the default Background Music"},
						{
							"name": "Old BGM", "description": "Restores the music tracks from the original release (pre-2019)",
							"data": {"url": "https://07th-mod.com/rikachama/audio/Higurashi-OldBGM.7z", "relativeExtractionPath": "HigurashiEp01_Data/StreamingAssets", "priority": 10}
						}
					]
				},
				{
					"name" : "SE Options", "type": "downloadAndExtract",
					"radio": [
						{"name": "Default SE", "description": "Use the default Sound Effects", "data":null},
						{
							"name": "Old SE", "description": "Restores the SE from the original release (pre-2019)",
							"data": {"url": "https://07th-mod.com/rikachama/audio/Higurashi-OldSE.7z", "relativeExtractionPath": "HigurashiEp01_Data/StreamingAssets", "priority": 10}
						}
					]
				},
				{
					"name" : "Additional Downloads", "type": "downloadAndExtract",
					"checkBox": [
						{
							"name": "OST Remake", "description": "Handmade remakes of several music tracks from the original release (pre-2019) - [Click here to listen to audio samples](https://radiataalice.bandcamp.com/album/hinamizawa-syndrome-vol-1)",
							"data": {"url": "https://07th-mod.com/misc/Higurashi.OST.Remake.zip", "relativeExtractionPath": "HigurashiEp01_Data/StreamingAssets", "priority": 20}
						}
					]
				}
			]
		}
	]
}
	"""

	def getModListFromDummyJSON(self):
		tmpdir = tempfile.mkdtemp()
		tempJSONPath = os.path.join(tmpdir, "temp.json")
		with open(tempJSONPath, 'w', ) as tempJSON:
			tempJSON.write(self.testInstallDataString)

		print(tempJSONPath)

		modList = common.getModList(tempJSONPath, isURL=False)
		shutil.rmtree(tmpdir)
		return modList

	# test when no updates required
	def test_no_update(self):
		local = fileVersionManagement.SubModVersionInfo(TestSubModVersion.localJSON)
		remote = fileVersionManagement.SubModVersionInfo(TestSubModVersion.localJSON)
		result = fileVersionManagement.SubModVersionInfo.getFilesNeedingInstall(local, remote)

		self.assertEqual(stripReason(result), {'cg':False, 'cgalt':False, 'movie-unity':False, 'voices':False, 'script':False})

	# test different submod name
	def test_different_subModName(self):
		local = fileVersionManagement.SubModVersionInfo(TestSubModVersion.localJSON)
		remote = fileVersionManagement.SubModVersionInfo(TestSubModVersion.voiceOnlyJSON)
		result = fileVersionManagement.SubModVersionInfo.getFilesNeedingInstall(local, remote)

		self.assertEqual(stripReason(result), {'cg':True, 'cgalt':True, 'movie':True, 'voices':True, 'script':True})

	# test no local version
	def test_no_local(self):
		local = None
		remote = fileVersionManagement.SubModVersionInfo(TestSubModVersion.remoteJSON)
		result = fileVersionManagement.SubModVersionInfo.getFilesNeedingInstall(local, remote)

		self.assertEqual(stripReason(result), {'cg':True, 'cgalt':True, 'movie':True, 'voices':True, 'script':True})

	# test if partially installed full ontop of voice-only, then reverted to voice-only (should do a full re-install)
	def test_voice_partial_install_full_then_voice(self):
		local = fileVersionManagement.SubModVersionInfo(TestSubModVersion.voiceWithFullPartiallyInstalledJSON)
		remote = fileVersionManagement.SubModVersionInfo(TestSubModVersion.voiceOnlyJSON)
		result = fileVersionManagement.SubModVersionInfo.getFilesNeedingInstall(local, remote)

		self.assertEqual(stripReason(result), {'cg':True, 'cgalt':True, 'movie':True, 'voices':True, 'script':True})


	def test_import(self):
		local = fileVersionManagement.SubModVersionInfo(TestSubModVersion.localJSON)
		remote = fileVersionManagement.SubModVersionInfo(TestSubModVersion.remoteJSON)
		result = fileVersionManagement.SubModVersionInfo.getFilesNeedingInstall(local, remote)

		self.assertEqual(stripReason(result), {'cg':False, 'cgalt':True, 'movie':True, 'voices':True, 'script':True})

	def test_highLevelFunctions(self):
		remoteSubModVersionJSONString = """
		{
			"id" : "Onikakushi Ch.1/full",
			"files":[
				{"id": "cg",                  "version": "1.0.0"},
				{"id": "cgalt",               "version": "1.0.0"},
				{"id": "movie",               "version": "1.0.0"},
				{"id": "voices",              "version": "1.0.0"},
				{"id": "script",              "version": "6.1.0"},
				{"id": "movie-unix",          "version": "1.0.0"},
				{"id": "ui-windows",          "version": "1.0.0"},
				{"id": "ui-unix",             "version": "1.0.0"}
			]
		}
		"""
		remoteVersionObject = fileVersionManagement.SubModVersionInfo(json.loads(remoteSubModVersionJSONString))

		test_dir = tempfile.mkdtemp()


		modList = self.getModListFromDummyJSON()
		mod = modList[0]
		submod = mod['submods'][0]

		subModConfig = installConfiguration.SubModConfig(mod, submod)
		fullConfig = installConfiguration.FullInstallConfiguration(subModConfig, test_dir, True)

		originalModFileList = fullConfig.buildFileListSorted('datadir')

		# If there is no file present, all files should require download
		fileVersionManager = fileVersionManagement.VersionManager(
			fullInstallConfiguration=fullConfig,
			modFileList=originalModFileList,
			localVersionFolder=test_dir,
			_testRemoteSubModVersion=remoteVersionObject)

		self.assertEqual(fileVersionManager.getFilesRequiringUpdate(), originalModFileList)
		self.assertEqual(fileVersionManager.fullUpdateRequired(), True)

		fileVersionManager.saveVersionInstallFinished()

		# If there is a file present which is identical, no files should require download
		fileVersionManagerIdentical = fileVersionManagement.VersionManager(
			fullInstallConfiguration=fullConfig,
			modFileList=originalModFileList,
			localVersionFolder=test_dir,
			_testRemoteSubModVersion=remoteVersionObject)

		self.assertEqual(fileVersionManagerIdentical.getFilesRequiringUpdate(), [])
		self.assertEqual(fileVersionManagerIdentical.fullUpdateRequired(), False)

		shutil.rmtree(test_dir)

	def test_filterFileListInner(self):
		modList = self.getModListFromDummyJSON()

		mod = modList[0]
		submod = mod['submods'][0]

		subModConfig = installConfiguration.SubModConfig(mod, submod)
		fullConfig = installConfiguration.FullInstallConfiguration(subModConfig, '.', True)
		fileList = fullConfig.buildFileListSorted('datadir')

		# Test if versions have not changed
		unchangedTestSet = (json.loads("""
		{
			"id" : "Onikakushi Ch.1/full",
			"lastAttemptedInstallID" : "Onikakushi Ch.1/full",
			"files":[
				{"id": "cg",      "version": "1.0.0"},
				{"id": "cgalt",   "version": "1.0.0"},
				{"id": "movie",   "version": "1.0.0"},
				{"id": "voices",  "version": "1.0.0"},
				{"id": "script",  "version": "6.1.0"},
				{"id": "ui-windows",  "version": "2.1.0"}
			]
		}
		"""), json.loads("""
		{
			"id" : "Onikakushi Ch.1/full",
			"lastAttemptedInstallID" : "Onikakushi Ch.1/full",
			"files":[
				{"id": "cg",      "version": "1.0.0"},
				{"id": "cgalt",   "version": "1.0.0"},
				{"id": "movie",   "version": "1.0.0"},
				{"id": "voices",  "version": "1.0.0"},
				{"id": "script",  "version": "6.1.0"},
				{"id": "ui-windows",  "version": "2.1.0"}
			]
		}
		"""))

		updateInformation = fileVersionManagement.getFilesNeedingUpdate(fileList,
		                                            fileVersionManagement.SubModVersionInfo(unchangedTestSet[0]),
		                                            fileVersionManagement.SubModVersionInfo(unchangedTestSet[1]))

		result = convertUpdateInformationToModFileList(fileList, updateInformation)

		self.assertEqual(result, [])
		print("Unchanged", [x.id for x in result])

		# Test if 'cg' version changes, that both 'cg' and 'script' need update
		dependencyTestSet = (json.loads("""
		{
			"id" : "Onikakushi Ch.1/full",
			"lastAttemptedInstallID" : "Onikakushi Ch.1/full",
			"files":[
				{"id": "cg",      "version": "1.0.0"},
				{"id": "cgalt",   "version": "1.0.0"},
				{"id": "movie",   "version": "1.0.0"},
				{"id": "voices",  "version": "1.0.0"},
				{"id": "script",  "version": "6.1.0"},
				{"id": "ui-windows",  "version": "2.1.0"}
			]
		}
		"""), json.loads("""
		{
			"id" : "Onikakushi Ch.1/full",
			"lastAttemptedInstallID" : "Onikakushi Ch.1/full",
			"files":[
				{"id": "cg",      "version": "1.0.1"},
				{"id": "cgalt",   "version": "1.0.0"},
				{"id": "movie",   "version": "1.0.0"},
				{"id": "voices",  "version": "1.0.0"},
				{"id": "script",  "version": "6.1.0"},
				{"id": "ui-windows",  "version": "2.1.0"}
			]
		}
		"""))

		updateInformation = fileVersionManagement.getFilesNeedingUpdate(fileList, fileVersionManagement.SubModVersionInfo(dependencyTestSet[0]),
		                                            fileVersionManagement.SubModVersionInfo(dependencyTestSet[1]))

		result = convertUpdateInformationToModFileList(fileList, updateInformation)

		idSet = set(x.id for x in result)
		self.assertIn('cg', idSet) #cg changed version
		self.assertIn('script', idSet) #script is a dependency of cg (must overwrite cg)
		idSet.remove('cg')
		idSet.remove('script')
		self.assertEqual(idSet, set()) #no other items should remain in the list

	def setUp(self):
		class DummyLogger:
			def write(self, message, runCallbacks=True, noTerminal=False):
				print(message)

		logger.setGlobalLogger(DummyLogger())
