# Python Patcher

Repository for the cross-platform python-based installer.

## Bootstrap Files

You must have Git LFS installed to download the bootstrap files.

You can build the bootstrap archives by running make_archives.py

## Python Development Environment

The python files should run under both Python 2 and 3 (please try to maintain compatability with both when editing the code).

The project is currently setup to use with the IDE `Pycharm`, so use IDE this if possible.

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
