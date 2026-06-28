import os
import shutil
import tempfile
import unittest

import common
import gameScanner
import installConfiguration


class DummySubModConfig:
	autodetect = True
	family = "higurashi"
	dataName = "HigurashiEp08_Data"
	identifiers = ["HigurashiEp08_Data"]
	modName = "Matsuribayashi Ch.8"


class TestCrossOverGameScanner(unittest.TestCase):
	def setUp(self):
		self.tempDir = tempfile.mkdtemp()

	def tearDown(self):
		shutil.rmtree(self.tempDir)

	def test_finds_windows_steam_in_crossover_bottle(self):
		bottlesPath = os.path.join(self.tempDir, "Bottles")
		bottlePath = os.path.join(bottlesPath, "Steam")
		steamPath = os.path.join(bottlePath, "drive_c", "Program Files (x86)", "Steam")
		secondarySteamPath = os.path.join(bottlePath, "drive_c", "SteamLibrary")
		commonPath = os.path.join(steamPath, "steamapps", "common")
		secondaryCommonPath = os.path.join(secondarySteamPath, "steamapps", "common")
		os.makedirs(commonPath)
		os.makedirs(secondaryCommonPath)

		libraryFoldersPath = os.path.join(steamPath, "steamapps", "libraryfolders.vdf")
		with open(libraryFoldersPath, "w") as libraryFoldersFile:
			libraryFoldersFile.write(
				'"libraryfolders"\n'
				'{\n'
				'\t"0"\n'
				'\t{\n'
				'\t\t"path"\t\t"C:\\\\Program Files (x86)\\\\Steam"\n'
				'\t}\n'
				'\t"1"\n'
				'\t{\n'
				'\t\t"path"\t\t"C:\\\\SteamLibrary"\n'
				'\t}\n'
				'}\n'
			)

		self.assertEqual(
			gameScanner.findPossibleCrossOverSteamPathsMac(bottlesPath),
			[os.path.realpath(steamPath), os.path.realpath(secondarySteamPath)]
		)

	def test_scan_marks_crossover_higurashi_install_as_wine(self):
		gamePath = os.path.join(self.tempDir, "Higurashi When They Cry Hou - Ch.8 Matsuribayashi")
		os.makedirs(os.path.join(gamePath, "HigurashiEp08_Data"))
		open(os.path.join(gamePath, "HigurashiEp08.exe"), "w").close()
		open(os.path.join(gamePath, "steam_api.dll"), "w").close()

		originalIsWindows = common.Globals.IS_WINDOWS
		try:
			common.Globals.IS_WINDOWS = False
			fullConfigs, partiallyUninstalledPaths = gameScanner.scanForFullInstallConfigs(
				[DummySubModConfig()],
				possiblePaths=[gamePath]
			)
			self.assertEqual(partiallyUninstalledPaths, [])
			self.assertEqual(len(fullConfigs), 1)
			self.assertTrue(fullConfigs[0].isWine)
			self.assertTrue(fullConfigs[0].isSteam)
		finally:
			common.Globals.IS_WINDOWS = originalIsWindows

	def test_higurashi_windows_exe_is_wine_on_non_windows(self):
		gamePath = os.path.join(self.tempDir, "Higurashi When They Cry Hou - Ch.8 Matsuribayashi")
		os.makedirs(gamePath)
		open(os.path.join(gamePath, "HigurashiEp08.exe"), "w").close()

		originalIsWindows = common.Globals.IS_WINDOWS
		try:
			common.Globals.IS_WINDOWS = False
			fullConfig = installConfiguration.FullInstallConfiguration(DummySubModConfig(), gamePath, True)
			self.assertTrue(fullConfig.isWine)

			common.Globals.IS_WINDOWS = True
			fullConfig = installConfiguration.FullInstallConfiguration(DummySubModConfig(), gamePath, True)
			self.assertFalse(fullConfig.isWine)
		finally:
			common.Globals.IS_WINDOWS = originalIsWindows
