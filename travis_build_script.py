import glob
import os
import re
import shutil
import subprocess
import sys

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

# No wildcards allowed in these paths to be ignored
ignore_paths = [staging_folder, output_folder, bootstrap_copy_folder, 'httpGUI/node_modules', 'bootstrap', '.git', '.idea', '.gitignore', '.travis.yml', '__pycache__']
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

# copy bootstrap folder to a temp folder
shutil.copytree('bootstrap', bootstrap_copy_folder)

# copy all files in the root github directory, except those in ignore_patterns
shutil.copytree('.', staging_folder, ignore=ignore_filter)

# now, copy the staged files into each os's bootstrap folder's install_data directory
for osBootStrapPath in glob.glob(f'{bootstrap_copy_folder}/*/'):
	print("processing", osBootStrapPath)
	# osBootStrapPath = os.path.join(bootStrapRoot, osFolderName)
	osInstallData = os.path.join(osBootStrapPath, 'install_data')
	if IS_WINDOWS:
		call(['xcopy', '/E', '/I', staging_folder, osInstallData])
	else:
		call(['cp', '-r', staging_folder + '/.', osInstallData])

# RELATIVE PATHS MUST CONTAIN ./
tar_gz(f'./{bootstrap_copy_folder}/higu_linux64_installer/', os.path.join(output_folder, 'seventh_mod_installer_linux.tar.gz'))
zip(f'./{bootstrap_copy_folder}/higu_win_installer/', os.path.join(output_folder, 'seventh_mod_installer_windows.zip'))
zip(f'./{bootstrap_copy_folder}/higu_win_installer_32/', os.path.join(output_folder, 'seventh_mod_installer_windows32.zip'))

# NOTE: mac zip doesn't need subdir - use '/*' to achieve this
zip(f'./{bootstrap_copy_folder}/higu_mac_installer/*', os.path.join(output_folder, 'seventh_mod_installer_mac.zip'))

try_remove_tree(staging_folder)
try_remove_tree(bootstrap_copy_folder)
