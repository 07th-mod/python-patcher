import glob
import os
import re
import shutil
import subprocess
import sys
import datetime

BUILD_LINUX_MAC = True
if len(sys.argv) == 2:
	if "win" in sys.argv[1].lower():
		BUILD_LINUX_MAC = False

print(f"Building Linux Mac: {BUILD_LINUX_MAC}")

IS_WINDOWS = sys.platform == "win32"

def call(args):
	print("running: {}".format(args))
	retcode = subprocess.call(args, shell=IS_WINDOWS) # use shell on windows
	if retcode != 0:
		exit(retcode)


def try_remove_tree(path):
	try:
		if os.path.isdir(path):
			shutil.rmtree(path)
		else:
			os.remove(path)
	except FileNotFoundError:
		pass


def zip(input_path, output_filename):
	try_remove_tree(output_filename)
	call(["7z", "a", output_filename, input_path])


def tar_gz(input_path, output_filename: str):
	try_remove_tree(output_filename)
	tempFileName = re.sub("\.gz", "", output_filename, re.IGNORECASE)
	call(["7z", "a", tempFileName, input_path])
	call(["7z", "a", output_filename, tempFileName])
	os.remove(tempFileName)

print("\nTravis python build script started\n")

# first, copy the files we want into a staging folder
staging_folder = 'travis_installer_staging'
output_folder = 'travis_installer_output'
bootstrap_copy_folder = 'travis_installer_bootstrap_copy'
loader_build_folder = 'rust_loader_build'

# No wildcards allowed in these paths to be ignored
ignore_paths = [staging_folder, output_folder, bootstrap_copy_folder, 'JSONValidator', 'installData.json', 'httpGUI/node_modules', 'bootstrap', '.git', '.idea', '.gitignore', '.travis.yml', '__pycache__', 'news']
ignore_paths_realpaths = set([os.path.realpath(x) for x in ignore_paths])

def ignore_filter(folderPath, folderContents):
	ignored_children = []

	for child in folderContents:
		fullPath = os.path.join(folderPath, child)
		if os.path.realpath(fullPath) in ignore_paths_realpaths:
			ignored_children.append(child)

	# ignoredChildrenString = f'Ignoring: {ignored_children}' if ignored_children else ''
	print(f'\nCopying Folder: [{folderPath}]')
	for child in ignored_children:
		print(f' - Ignored [{child}]')

	return ignored_children #ignore_patterns_func(folderPath, folderContents)

try_remove_tree(bootstrap_copy_folder)
try_remove_tree(output_folder)
try_remove_tree(staging_folder)
try_remove_tree(loader_build_folder)

# Make sure the output folder exists
os.makedirs(output_folder, exist_ok=True)

# copy bootstrap folder to a temp folder
shutil.copytree('bootstrap', bootstrap_copy_folder)

# copy all files in the root github directory, except those in ignore_patterns
shutil.copytree('.', staging_folder, ignore=ignore_filter)

# Save the build information in the staging folder. Will later be read by installer.
with open(os.path.join(staging_folder, 'build_info.txt'), 'w', encoding='utf-8') as build_info_file:
	build_info_file.write(f'Build Date: {datetime.datetime.now()}\n')
	build_info_file.write(f'Git Tag (Version): {os.environ.get("TRAVIS_TAG")}\n')

# now, copy the staged files into each os's bootstrap folder's install_data directory
for osBootStrapPath in glob.glob(f'{bootstrap_copy_folder}/*/'):
	print("processing", osBootStrapPath)
	# osBootStrapPath = os.path.join(bootStrapRoot, osFolderName)
	osInstallData = os.path.join(osBootStrapPath, 'install_data')
	if IS_WINDOWS:
		call(['xcopy', '/E', '/I', '/Y', staging_folder, osInstallData])
	else:
		call(['cp', '-r', staging_folder + '/.', osInstallData])

################ Special extra tasks FOR WINDOWS ONLY ##############
# Extract the python archive
call(["7z", "x", f'./{bootstrap_copy_folder}/higu_win_installer_32/install_data/python_archive.7z', f'-o./{bootstrap_copy_folder}/higu_win_installer_32/install_data/'])
# Delete the python archive
try_remove_tree(f'./{bootstrap_copy_folder}/higu_win_installer_32/install_data/python_archive.7z')
# Re-compress the python and httpGUI files into an encrypted archive
call(["7z", "a", f'./{bootstrap_copy_folder}/higu_win_installer_32/install_data/python_archive.7z', f'./{bootstrap_copy_folder}/higu_win_installer_32/install_data/python', '-ppassword', '-mhe'])
call(["7z", "a", f'./{bootstrap_copy_folder}/higu_win_installer_32/install_data/httpGUI_archive.7z', f'./{bootstrap_copy_folder}/higu_win_installer_32/install_data/httpGUI', '-ppassword', '-mhe'])
# Remove the python and httpGUI folders
try_remove_tree(f'./{bootstrap_copy_folder}/higu_win_installer_32/install_data/python')
try_remove_tree(f'./{bootstrap_copy_folder}/higu_win_installer_32/install_data/httpGUI')
################ End windows special tasks ##############

# RELATIVE PATHS MUST CONTAIN ./
if BUILD_LINUX_MAC:
	os.rename(f'./{bootstrap_copy_folder}/higu_linux64_installer/', f'./{bootstrap_copy_folder}/07th-Mod_Installer_Linux64/')
	tar_gz(f'./{bootstrap_copy_folder}/07th-Mod_Installer_Linux64/', os.path.join(output_folder, '07th-Mod.Installer.linux.tar.gz'))
# zip(f'./{bootstrap_copy_folder}/higu_win_installer/', os.path.join(output_folder, '07th-Mod.Installer.win64.zip'))
# zip(f'./{bootstrap_copy_folder}/higu_win_installer_32/', os.path.join(output_folder, '07th-Mod.Installer.win.zip'))

if not BUILD_LINUX_MAC:
	os.rename(f'./{bootstrap_copy_folder}/higu_win_installer_32/', f'./{bootstrap_copy_folder}/07th-Mod_Installer_Windows/')
	call(['7z', 'a', '-aoa', os.path.join(loader_build_folder, '07th-Mod.Installer.Windows.7z'), f'./{bootstrap_copy_folder}/07th-Mod_Installer_Windows/'])
	# copy 7za binary to current directory
	shutil.copy('bootstrap/higu_win_installer_32/install_data/7za.exe', os.path.join(loader_build_folder, '7za.exe'))
	shutil.copy('installer_loader.rs', os.path.join(loader_build_folder, 'installer_loader.rs'))
	# compile the rust loader
	loader_exe_name = '07th-Mod.Installer.Windows.exe'
	call(['rustc', '-O', os.path.join(loader_build_folder, 'installer_loader.rs'), '-o', os.path.join(loader_build_folder, loader_exe_name)])
	shutil.copy(os.path.join(loader_build_folder, loader_exe_name), os.path.join(output_folder, loader_exe_name))


# NOTE: mac zip doesn't need subdir - use '/*' to achieve this
if BUILD_LINUX_MAC:
	os.rename(f'./{bootstrap_copy_folder}/higu_mac_installer/', f'./{bootstrap_copy_folder}/07th-Mod_Installer_Mac/')
	zip(f'./{bootstrap_copy_folder}/07th-Mod_Installer_Mac/*', os.path.join(output_folder, '07th-Mod.Installer.mac.zip'))

try_remove_tree(staging_folder)
try_remove_tree(bootstrap_copy_folder)
