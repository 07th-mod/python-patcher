# Changelog

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
installation time (especially on a HDD), and also reduce the number of voice files on disk from about 45,000 to just one file.

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
