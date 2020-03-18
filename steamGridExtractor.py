from __future__ import unicode_literals

import common
import glob
import shutil
import os


def getUserDataFolders():
    if not common.Globals.IS_WINDOWS:
        return None

    import winreg

    try:
        defaultSteamPath = winreg.QueryValueEx(
            winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
            "SteamPath",
        )[0]
        return glob.glob(
            os.path.join(defaultSteamPath, "userdata", "**", "config"), recursive=True
        )
    except:
        return None


def extractSteamGrid():
    try:
        userDataFolders = getUserDataFolders()
        if userDataFolders:
            for i in userDataFolders:
                shutil.unpack_archive("higumi-steamgrid.zip", i)
    except:
        pass
