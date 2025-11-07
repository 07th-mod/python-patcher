from __future__ import unicode_literals

import common
import glob
import shutil
import os
import commandLineParser

def getSteamPath():
    try:
        if common.Globals.IS_LINUX:
            # Newer versions of Steam use this path
            altSteamPath = os.path.expanduser("~/.steam/steam")

            if os.path.exists(altSteamPath):
                return altSteamPath

            # Older versions of Steam and the Steam Deck use this path
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
        elif common.Globals.IS_MAC:
            return os.path.expanduser('~/Library/Application Support/Steam')
        else:
            return None
    except:
        return None

def getUserDataFolders():
    steamPath = getSteamPath()

    print("steamGridExtractor.getUserDataFolders: Looking for user data folders inside [{}]".format(steamPath))

    if steamPath:
        if not os.path.exists(steamPath):
            print("steamGridExtractor.getUserDataFolders: WARNING: steamPath [{}] does not exist! steamGrid extraction will probably fail!".format(steamPath))

        maybePaths = glob.glob(
            os.path.join(steamPath, "userdata", "**", "config"), recursive=True
        )

        # Only return folders, not files called 'config'
        return list(filter(os.path.isdir, maybePaths))
    else:
        return None


def extractSteamGrid(downloadDir):
    commandLineParser.printSeventhModStatusUpdate(98, "Downloading and Extracting Steam Grid")

    # Try to find/guess the steam user data folder where the steam grid assets should be extracted
    userDataFolders = None
    try:
        userDataFolders = getUserDataFolders()
    except Exception as e:
        print("steamGridExtractor.extractSteamGrid: Failed to get Steam User Data folders (where steamgrid extracted): {}".format(e))

    if not userDataFolders:
        print("steamGridExtractor.extractSteamGrid: WARNING: not extracting steamgrid icons as no steam user data folders found")
        return

    print("steamGridExtractor.extractSteamGrid: Found {} Steam User Data folders: {}".format(len(userDataFolders), userDataFolders))

    # Download the steamgrid assets
    try:
        steamGridURL = "https://github.com/07th-mod/patch-releases/releases/download/mod-common-v1.0/higumi-steamgrid.zip"

        print("steamGridExtractor.extractSteamGrid: Downloading Steam Grid Icons from [{}]...".format(steamGridURL))
        downloaderAndExtractor = common.DownloaderAndExtractor(modFileList=[],
                                                               downloadTempDir=downloadDir,
                                                               extractionDir=downloadDir,
                                                               supressDownloadStatus=True)
        downloaderAndExtractor.addItemManually(url=steamGridURL,
                                               extractionDir=downloadDir)
        downloaderAndExtractor.download()
    except Exception as e:
        print("steamGridExtractor.extractSteamGrid: Steamgrid Installation - Failed to download steamgrid assets zip file: {}".format(e))

    # Extract to each found user's data folder (steam has one folder per user)
    for i in userDataFolders:
        try:
            print("steamGridExtractor.extractSteamGrid: Extracting Steam Grid Icons to [{}]...".format(i), end="")
            print("OK")
            shutil.unpack_archive(os.path.join(downloadDir, "higumi-steamgrid.zip"), i)
        except Exception as e:
            print("ERROR")
            print("steamGridExtractor.extractSteamGrid: Warning - failed to extract to [{}], but other paths may work. Error: {}".format(i, e))

