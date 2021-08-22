### Installation Instructions

- **Please download the installer to your computer, then run it - don't run directly from your browser**
- Please read the [Higurashi](https://07th-mod.com/wiki/Higurashi/Higurashi-Getting-started/) or [Umineko](https://07th-mod.com/wiki/Umineko/Umineko-Getting-started/) wiki sections for more information.

### Known Issues

- **You may need to refresh the webpage (web GUI) if it does not load or seems to hang**.
  - This will happen for MacOS users / Python 2 / Python 3.6 and below using the Chrome web browser (Firefox seems to be OK)
  - This shouldn't happen on Windows builds / Python 3.7 and up as we've applied a fix

<details>
  <summary><b>Linux: Higurashi with GNOME Desktop/Ubuntu Crashes - CLICK TO EXPAND</b></summary>

GNOME Desktop (the default on Ubuntu) *may* cause Higurashi Ep.4 and upwards to crash the entire desktop when you start the game.

We've had varying reports - Ubuntu 19.10 with GNOME 3.34.2. seems to work (except for a crash in Tatarigoroshi on first startup). But previously we've had crash reports from anyone using GNOME. This happens even on the base game (without any mods applied).

If you have this issue, a workaround is to install XFCE desktop. You can follow [this guide](https://linuxconfig.org/how-to-install-xubuntu-desktop-on-ubuntu-18-04-bionic-beaver-linux) to install XFCE desktop (it can be installed alongside GNOME).

Please make sure you can launch the base game before applying any mods (please don't make any saves on the base game as they are not compatible with the mod).

</details>

### Troubleshooting

- If you are having installer trouble, or the game does not run properly, follow the [**Support Checklist**](https://07th-mod.com/wiki/support-checklist/) to solve your problem

### Explanation of Windows Versions of the Installer

1. `07th-Mod.Installer.Windows.exe` (Requires Administrator) - Try this first.
2. `07th-Mod.Installer.Windows.SafeMode.exe` (Requires Administrator) - If the installer does not start up at all, or you have other problems, try this version of the installer. It uses a text-based interface for the launcher.
3. `07th-Mod.Installer.Windows.NoLauncher.zip` (No Administrator Required): See below instructions

#### No Launcher instructions

- Use this version if the above two do not work. It may be useful if:
  - You do not have administrator privileges
  - Your Antivirus software refuses to launch the above two .exes
  - The above two .exes immediately crash, so you're unable to run the installer

- Usage Instructions
  - You might need to install the [Visual C++ Redistributable (x86)](https://aka.ms/vs/16/release/vc_redist.x86.exe) ([linked from this page](https://support.microsoft.com/en-au/topic/the-latest-supported-visual-c-downloads-2647da03-1eea-4433-9aff-95f26a218cc0)), but most people will already have it.
  - Extract the `.zip` file to your desktop or downloads folder (NOT program files or the game root, as this may cause permissions issues)
  - Double click on the `install.bat` file.
    - A terminal will open, followed by a special page in your web browser (you use this webpage to install the mod).
    - If the `install.bat` does not work, close the terminal, then double click the `install_safe_mode.bat` for the text-only installer

### Important Changes

- put your changes here
