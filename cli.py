import argparse
import main as gui_main
import common
import uminekoInstaller
import uminekoNScripterInstaller
import higurashiInstaller
import logger
import installConfiguration
import sys


def main(*, game_name, game_path, mod_type, mod_options, is_steam):
    sys.stdout = logger.Logger(common.Globals.LOG_FILE_PATH)
    logger.setGlobalLogger(sys.stdout)
    sys.stderr = logger.StdErrRedirector(sys.stdout)
    gui_main.check07thModServerConnection()
    common.Globals.scanForExecutables()
    modList = gui_main.getModList()
    subModList = gui_main.getSubModConfigList(modList)
    print("\n")
    suitableSubMods = [
        x
        for x in subModList
        if all(y in x.modName.lower().split() for y in game_name.lower().split("-"))
        and x.subModName == mod_type
    ]
    if len(suitableSubMods) == 0:
        print(f'Could not find a mod matching "{game_name}"')
        return
    neededSubMod = suitableSubMods[0]
    for i in mod_options:
        found = False
        for j in neededSubMod.modOptions:
            if j.id == i:
                found = True
                j.value = True
        if not found:
            print(f"No match found for option {i}")
            return
    install_config = installConfiguration.FullInstallConfiguration(
        neededSubMod, game_path, is_steam
    )
    if neededSubMod.family == "umineko":
        uminekoInstaller.mainUmineko(install_config)
    elif neededSubMod.family == "umineko_nscripter":
        uminekoNScripterInstaller.main(install_config)
    elif neededSubMod.family == "higurashi":
        higurashiInstaller.main(install_config)
    else:
        print(
            f"Submod family is not recognised, the script may be out of date."
            "Please ask us to update it."
        )


if __name__ == "__main__":
    argparser = argparse.ArgumentParser()
    argparser.add_argument(
        "-g",
        "--game",
        dest="game_name",
        required=True,
        help='Name of the game, e.g. "minagoroshi" or "umineko-question"',
    )
    argparser.add_argument(
        "-p",
        "--path",
        dest="game_path",
        required=True,
        help="Path to the game's install location",
    )
    argparser.add_argument(
        "-m",
        "--mod-type",
        dest="mod_type",
        required="true",
        help=(
            'Submod type, can be "full" or "voice-only".'
            "For Umineko Answer Arcs, this should be "
            '"novel-mode", "adv-mode" or "voice-only".'
        ),
    )
    argparser.add_argument(
        "-o",
        "--mod-option",
        action="append",
        dest="mod_options",
        default=[],
        help=(
            "Enable a specific mod option by its ID. "
            "Can be repeated multiple times to enable many options."
        ),
    )
    argparser.add_argument(
        "--non-steam",
        action="store_false",
        dest="is_steam",
        default=True,
        help="Specify if you're modding a non-Steam version of the game.",
    )
    args = argparser.parse_args()
    main(**vars(args))
