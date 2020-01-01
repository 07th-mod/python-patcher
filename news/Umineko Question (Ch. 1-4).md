# Changelog

## Fix Disappearing Issue in ADV mode, NVL linebreak fix, various other fixes - 23/12/2019

On 23/11/2019, a fix was applied to fix the backlog disappearing, which was successful. It also applied a fix for the text disappearing issue, but that only fixed some of the bugs in the script.

This most recent update will hopefully fix the disappearing text issue for good. This would occur when playing ADV mode (only affects Question Arcs). The text would be displayed, but upon reaching the point where the line would wrap/a page break would occur, the text would disappear.

You can see (spoilery) example here, but it's very obvious while you're playing when it happens: https://github.com/07th-mod/umineko-question/issues/147

I have decided to issue a warning that if you're using ADV mode, to expect there to be some bugs. Please report any bugs to us on Github or Discord so they can be fixed.

In addition, a somewhat separate issue of double-spaced line breaks not being properly displayed in NVL mode was also fixed.

I would **highly recommend upgrading** the next time you reach the end of an episode (remember, save files don't work properly when the script changes, so you need to start a new chapter after a script update).

List of fixes:

- Fix `br` (double spaced line breaks) in NVL mode
- Force clickwait before text overflows when text is displayed automatically (ADV)
- Spot fix for graphical textbox artifact at end of episode 4 (ADV)
- Fix voicedelay causing unecessary delay before text is displayed (NVL and ADV)
- Fix places where empty textbox remains on screen during a delay (ADV, possibly NVL)
- Fix some invalid/wrong nametags (ADV)

## Fix Text Overflow Bug - 19/08/2019

Fix bug where text would overflow the text box if there were repeated "automatic" lines (lines which appear without clicking). This would have happened a handful of times during the course of the game.

## Add Upscaled Ryukishi Sprites Option - 09/07/2019

Added Upscaled Ryukishi sprites option. See "mod options" section of wiki for more details.

## Add Upscaled Pachinko Sprites Option - 22/06/2019

An option to replace the PS3 sprites with upscaled versions of the Pachinko sprites (Mangagamer, non-ryukishi sprites)
has been added.

There may still be some times in the game where the PS3 sprites will appear (CGs will use PS3 sprites, and so will
zoomed in sprites for the Answer arcs). There are also some Pachinko characters which don't have sprites at all -
they will show up with the PS3 sprites. The character portraits for the Answer Arcs will show as PS3 sprites, too.

## Question Arcs Missing Voices Bug Fix - 15/06/2019

Quite a fair way into the game on the Question Arcs, voices would fail to play back (for certain characters).

This was due to a very big `arc4.nsa` which had all the voice files in it. The voice file was too large for the game to handle, so everything past a certain point wouldn't play.

In the new version of the patch, the voice file is split into two smaller files (`arc4.nsa` and `arc5.nsa`) so the game can handle it.

This problem affected all installs from 19/05/2019 to 15/06/2019, so there would have been a roughly 1-month span where your 
install would have had broken voices. If you installed during this time, it would be best to either manually apply the voice 
file pack, or re-install the game using the installer.

## Mangagamer (Non-Steam) Voice File Bug Fix - 26/05/2019

The layout of the the `arc[X].nsa` files is different between the Mangagamer and Steam versions. The recent
voice file optimization did not take that into account, and thus broke voice playback for users who have the Mangagamer (non-steam) release of Umineko.

This has been fixed on the latest installer. If you have this problem and don't want to re-install,
just rename the `arc4.nsa` file to `arc1.nsa`, so the game can find it.

## Voice File Optimization - 19/05/2019

The voice files are now stored as a single file (`arc4.nsa`). This will speed up
installation time (especially on a HDD), and also reduce the number of voice files on disk from about 51,000 to just one file.

We don't expect any issues, but if you find any problems with voice playback, please let us know.

## WARNING: 02/05/2019

We have had a couple reports of performance problems for Chapters 5-8, even on high end PCs.
On very low end PCs (like atom CPU laptops with integrated graphics), this is expected, but not on high end PCs.

Firstly, please launch the game unmodded to check the game works correctly without mods. Please do not make any
saves though, as saves from the unmodded game are not compatible.

Please make sure to close all CPU intensive programs in the background (even your web browser!). This is because the
game uses the CPU for graphics rendering, and is single threaded, so even if you have a multicore processor
it can only ever use one core.

It's also possible for a poor performing hard disk to cause performance problems, as images are loaded
by the engine each time they are displayed (as far as we know).

If you still have problems, please post your CPU and GPU specs and a description of how
the lag appears on our Discord for us to analyse.

If you figure out what's causing the problem, please let us know as we really want to sort this issue out.

### High Resolution Monitors

High resolution screens (greater than 1080p) can also cause problems (mainly on integrated graphics). Forcing your desktop
screen resolution lower may help. You can test if this is a problem by playing in windowed mode with a small
window - performance will usually improve.

#### Older news

23/02/2019: On the 05/02/2019 a change was made to the manual mac install instructions which would prevent you from starting the game. It has now been reverted (sorry abou that).

28-01-2019: Cross Platform Installer is now suggested in install instructions. Wiki has been refactored.

28-01-2019: Add ADV mode to Full Patch of Question Arcs

17-11-18: Add beta version of Question Arcs in 1080p resolution (previously resolution was 960p, resulting in some blurriness). You can install it via the installer or manually. Add ability to toggle language with 'Tab' button.

2-10-18: Add Japanese Language mode (thanks Naoki!). Note: currently doesn't work for "Voice Only" or answer arcs "ADV mode", due to those versions using a different script.

15-07-18: Some small changes to both arcs (to update you need both the latest script file and the latest update zip)

- For Question arcs only, add the option to view the original game's videos since some consider the PS3 openings too spoilery. (Question arcs issue #101)
- Use English title logo for Question arcs (Question arcs issue #100)
- Fix transparency of images for one scene for Answer arcs (use alphablend mode images)

06-06-18: For Chiru Arcs only, minor update to script and assets (see issue [#47](https://github.com/07th-mod/umineko-answer/issues/47))

05-05-18: For Question Arcs only, fix some missing voice delays.

01-05-18: Update all .exes to give a reminder if you forget to rename the `0.utf` to `0.u` instead of the generic/incorrect error message. Backup of the old .exes can be found [here](https://github.com/07th-mod/resources/releases/download/Beato/umineko_exe_backup_2018-05-01.7z).

13-04-18: Add [missing Maria/Rosa Alternate Sprites](https://github.com/07th-mod/umineko-question/issues/93) to the merged update pack (pack v4 cumulative) for Question Arcs only.

02-04-18: Question arc script was updated to fix voice/unvoiced delay bugs.

17-02-18: **Did Steam update your game, breaking your patch?** Follow the [Question Arc Instructions](https://github.com/07th-mod/umineko-question#warning---steam-updates) or the [Answer Arc Instructions](https://github.com/07th-mod/umineko-answer#warning---steam-updates).
