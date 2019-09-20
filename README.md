# Python Patcher

Repository for the cross-platform python-based installer.

## Bootstrap Files

You can build the bootstrap archives by running make_archives.py

## Python Development Environment

The python files should run under both Python 2 and 3 (please try to maintain compatability with both when editing the code).

The project is currently setup to use with the IDE `Pycharm`, so use IDE this if possible.

Please note that pycharm will attempt to index files in the project folder - this may cause problems when you run
the installer from pycharm, as the installer may try to move a file Pycharm is currently reading, causing it to
fail (I have only seen this happen once).

## JSON Mod Definition

The patcher reads the file [installData.json](installData.json) to figure out what mods are available.  The spec for this file is defined as a `Codable` Swift struct in [JSONValidator.swift](JSONValidator/Sources/JSONValidator/JSONValidator.swift)

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

## Travis Setup

It is HIGHLY recommended to use a linter when editing .travis.yml files - pycharm provides this functionality.

Here is a list of steps I used to setup travis:

### Allowing travis to upload to the repository

- Install ruby
- Do `gem install travis`
- Open a terminal while inside this repository
- Run `travis setup releases --com`. This will start a setup wizard which will update your .travis.yml file's deploy section.
- Enter your Github username and password when asked
- The setup will ask for a "File to Upload". This just sets a default value in the .travis.yml - you can change it later
- Accept the default values for the rest of the options
- See what changes the setup wizard made to your .travis.yml file

There are some additional options which had to be set:

`file_glob: true`: Allow using globb'd paths in the `file` option

`file: travis_installer_output/*`: set which files to add to the releases

`skip_cleanup: true`: this MUST be set such that after the previous script is run, the files are not cleaned up (first the script is run, then travis copies the files from the specified place)

```travis
  on:
    repo: 07th-mod/python-patcher
    tags: true
```

This ensures that releases are only deployed on tagged pushes, not every push.

### Compiling the Windows Loader

The windows loader is not well documented. Please contact one of the dev team members if you have trouble building - it is more than likely there is an error in the instructions below, rather than somethign wrong on your end.

The installer is mostly setup to build on travis - if you want to build locally, you'll need to do the following (WINDOWS ONLY):

- Install Rust
- Download `7za.exe` (you may need to rename it to `7za.exe` if it is called `7z.exe`), and place it next to `travis_build_script.py`
- Open a command window
- In the command window, set the `TRAVIS_TAG` environment variable using `set TRAVIS_TAG=v9.9.9`
- Run `python travis_build_script.py win` (make sure to include the `win` part), **in the same command window**

The built exe will be located in the `travis_installer_output` folder

#### Useful Resources

- <https://github.com/cclauss/Travis-CI-Python-on-three-OSes>
- <https://github.com/drojf/Travis-CI-Python-on-three-OSes>
- <https://docs.travis-ci.com/user/multi-os/>
