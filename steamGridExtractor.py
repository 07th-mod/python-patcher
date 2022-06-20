from __future__ import unicode_literals

import common
import glob
import shutil
import os
import commandLineParser

def getSteamPath():
    try:
        if common.Globals.IS_LINUX:
            return os.path.expanduser("~/.local/share/Steam/")
        elif common.Globals.IS_WINDOWS:
            try:
                import winreg
            except ImportError:
                import _winreg as winreg
            return winreg.QueryValueEx(
                winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
                "SteamPath",
            )[0]
        else:
            return None
    except:
        return None

def getUserDataFolders():
    steamPath = getSteamPath()
    if steamPath:
        return glob.glob(
            os.path.join(steamPath, "userdata", "**", "config"), recursive=True
        )
    else:
        return None


def extractSteamGrid(downloadDir):
    try:
        userDataFolders = getUserDataFolders()

        commandLineParser.printSeventhModStatusUpdate(98, "Downloading and Extracting Steam Grid")
        print("Downloading and Extracting Steam Grid Icons to {}".format(userDataFolders))

        downloaderAndExtractor = common.DownloaderAndExtractor(modFileList=[],
                                                               downloadTempDir=downloadDir,
                                                               extractionDir=downloadDir,
                                                               supressDownloadStatus=True)
        downloaderAndExtractor.addItemManually(url="https://07th-mod.com/installer/steamgrid/higumi-steamgrid.zip",
                                               extractionDir=downloadDir)
        downloaderAndExtractor.download()

        # Extract to each steam user's data folder (steam has one folder per user)
        if userDataFolders:
            for i in userDataFolders:
                shutil.unpack_archive(os.path.join(downloadDir, "higumi-steamgrid.zip"), i)
    except Exception as e:
        print("Steamgrid Installation Failed: {}".format(e))
