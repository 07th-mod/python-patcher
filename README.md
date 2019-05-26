# Python Patcher

Repository for the cross-platform python-based installer.

## Bootstrap Files

You must have Git LFS installed to download the bootstrap files.

You can build the bootstrap archives by running make_archives.py

## Python Development Environment

The python files should run under both Python 2 and 3 (please try to maintain compatability with both when editing the code).

The project is currently setup to use with the IDE `Pycharm`, so use IDE this if possible.

Please note that pycharm will attempt to index files in the project folder - this may cause problems when you run
the installer from pycharm, as the installer may try to move a file Pycharm is currently reading, causing it to
fail (I have only seen this happen once).

## JSON Mod Definition

The patcher reads the file [installData.json](installData.json) to figure out what mods are available.  The spec for this file is defined as a `Codable` Swift struct in [JSONValidator.swift](JSONValidator/Sources/JSONValidator/JSONValidator.swift)

## Developer's note about remote files

The installer will prefer local files (on disk) if they are present, instead of remote files (from github). Specifically: 

- `installData.json`
- all .md files in the `news` folder

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

### Windows Builds

We have had some issues with windows defender stalling downloads on our windows builds (it seems to do with us
distributing a python distribution).

On Chrome and Edge (not Firefox), when you downloaded the old zip, it would get stuck at 100% while the zip file was being scanned.
Chrome would then refuse to download any other files while the windows defender service would be stuck at 30% CPU for 20 minutes or more.

To fix this, we have encrypted the python distribution and the httpGUI archives with the password 'password', so windows defender has to wait until the files are extracted before it can scan them.

#### Useful Resources

- <https://github.com/cclauss/Travis-CI-Python-on-three-OSes>
- <https://github.com/drojf/Travis-CI-Python-on-three-OSes>
- <https://docs.travis-ci.com/user/multi-os/>
