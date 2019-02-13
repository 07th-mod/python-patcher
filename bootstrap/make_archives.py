import os, shutil
from subprocess import call

output_dir = "python_patcher_bootstrap_output"

if os.path.exists(output_dir):
    shutil.rmtree(output_dir)

call(["7za", "a", os.path.join(output_dir,"higu_win_installer.zip"),          "higu_win_installer"])
call(["7za", "a", os.path.join(output_dir,"higu_win_installer_32.zip"),       "higu_win_installer_32"])
call(["7za", "a", os.path.join(output_dir,"higu_mac_installer.zip"),          ".\higu_mac_installer\*"]) #MUST include the .\ otherwise 7z will create subdir
call(["7za", "a", os.path.join(output_dir,"higu_linux64_installer.tar"),      "higu_linux64_installer"])
call(["7za", "a", os.path.join(output_dir,"higu_linux64_installer.tar.gz"),   os.path.join(output_dir,"higu_linux64_installer.tar")])

os.remove(os.path.join(output_dir, "higu_linux64_installer.tar"))
