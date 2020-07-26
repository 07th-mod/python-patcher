# Python Patcher

If you just want to install the mod, [**click here for the installer download page**](https://github.com/07th-mod/python-patcher/releases).

This repository contains the mod installer, used for installing all 07th-mod mods. The installer is cross-platform and written in python.

**The below information is for developers only.**

## Python Development Environment Setup

If you have no preference for IDE, I would recommend `Pycharm` as it will help reduce mistakes while you're writing your code. Please conform to the follwing guidelines:

- **Please use tabs, not spaces,** when editing the python code, and enable smart tabs if your editor supports them.

- **Ensure your code can run under both Python 2 and 3**. We are currently supporting Python 2 only for MacOS - we may remove this requirement in the future.

Please note that pycharm will attempt to index files in the project folder - this may cause problems when you run
the installer from pycharm, as the installer may try to move a file Pycharm is currently reading, causing it to
fail (I have only seen this happen once).

## JSON Mod Definition

The patcher reads the file [installData.json](installData.json) to figure out what mods are available.  The spec for this file is defined as a `Codable` Swift struct in [JSONValidator.swift](JSONValidator/Sources/JSONValidator/JSONValidator.swift)

The validator will run automatically on every push, to check the `installData.json` is correctly formatted. Because the validator is quite strict, the validator will need to be updated if the `installData.json` format is changed.

## Developer Mode

The installer has a global variable called DEVELOPER_MODE, which controls how it behaves. Developer mode will be activated if an `installData.json` is found on disk adjacent to the install script. This will be the case if you clone the git repository, then run the script.

In developer mode, the installer will prefer local files (on disk) if they are present, instead of remote files (from github). This mode will Specifically: 

- `installData.json`
- all .md files in the `news` folder
- `cachedDownloadSizes.json`

## Cached Download Sizes

The Github repository contains a file called `cachedDownloadSizes.json` to allow the installer to calculate the size of a mod without having to query each download link. When the installer runs in normal mode, it downloads this file from Github each time the installer is run.

When the installer is run in developer mode, it checks that all URLs in `installData.json` are present in `cachedDownloadSizes.json` - if not the `cachedDownloadSizes.json` file is automatically regenerated. Please commit this `cachedDownloadSizes.json` to the git repository each time it changes.

## HTTPGUI / Web Interface

The web interface component is located in the httpGUI folder.

It is setup as a npm package with `eslint`, such that you can install
the `markdownlint` plugin in Visual Studio Code and have code
style checks/syntax checks etc. applied.

To setup the development environment:

- Install `npm`
- Install `visual studio code`
- Install the `markdownlint` plugin for visual studio code (available in the marketplace)
- Open a terminal in the `httpGUI` subdirectory, then run `npm install eslint`
- Open the httpGUI **folder** in Visual Studio Code. Just opening the file by itself won't work.
- You will likely get a huge number of warnings as the file will have CRLF
  line endings (TODO: fix git settings so it downloads as LF). To fix this,
  on the bottom right of the window, click where it says `CRLF`, then choose
  `LF`

To use the plugin:

- When you get an error, move the text cursor to the end of the red squiggle
- A lightbulb icon will appear
- Click the lightbulb icon and you can automatically fix the issue
- Moving the mouse cursor over a red squiggle will explain the error

## Safe Mode / Interactive Text Mode

The installer contains an interactive text mode installer, which can be used by the end user if the graphical installer fails (this is different from the "command line interface").

## Command line interface

The installer also ships with an alternative command line interface
for advanced users. For instructions, please refer to [this section](https://07th-mod.com/wiki/Umineko/Umineko-Part-3a-Cross-Platform-Installer/#power-users) of the wiki.

## Github Actions Setup

It is HIGHLY recommended to use a linter when editing Github Actions .yml files - pycharm provides this functionality.

Please read the comments in the `.github/workflows/test_and_deploy.yml` file for more information.

### Compiling the Windows Loader

The windows loader is not well documented. Please contact one of the dev team members if you have trouble building - it is more than likely there is an error in the instructions below, rather than somethign wrong on your end.

The installer is mostly setup to build on travis - if you want to build locally, you'll need to do the following (WINDOWS ONLY):

- Install Rust
- Download `7za.exe` (you may need to rename it to `7za.exe` if it is called `7z.exe`), and place it next to `travis_build_script.py` (or put 7za on your path)
- Open a command window
- In the command window, set the `TRAVIS_TAG` environment variable using `set TRAVIS_TAG=v9.9.9`
- Run `python travis_build_script.py win` (make sure to include the `win` part), **in the same command window**

The built exe will be located in the `travis_installer_output` folder

