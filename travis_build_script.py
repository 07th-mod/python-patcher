from __future__ import unicode_literals

import glob
import json
import os
import re
import shutil
import subprocess
import sys
import datetime
import platform
import tempfile

from io import BytesIO
from zipfile import ZipFile
from urllib.request import urlopen

print("--- Running 07th-Mod Installer Build using Python {} ---".format(sys.version))

BUILD_LINUX_MAC = True
# If user specified which platform to build for, use that platform. Otherwise, attempt to detect platform automatically.
if len(sys.argv) == 2:
	if "win" in sys.argv[1].lower():
		BUILD_LINUX_MAC = False
else:
	BUILD_LINUX_MAC = not (platform.system() == "Windows")

print(f"Building Linux Mac: {BUILD_LINUX_MAC}")

IS_WINDOWS = sys.platform == "win32"

EMBEDDED_PYTHON_ZIP_URL = "https://www.python.org/ftp/python/3.7.7/python-3.7.7-embed-win32.zip"

# Required Environment Variables
GIT_REF = os.environ.get("GITHUB_REF")    # Github Tag / Version info
GIT_TAG = GIT_REF.split('/')[-1]

def call(args, **kwargs):
	print("running: {}".format(args))
	retcode = subprocess.call(args, shell=IS_WINDOWS, **kwargs) # use shell on windows
	if retcode != 0:
		raise SystemExit(retcode)


def try_remove_tree(path):
	try:
		if os.path.isdir(path):
			shutil.rmtree(path)
		else:
			os.remove(path)
	except FileNotFoundError:
		pass

# From https://stackoverflow.com/a/12526809/848627, but modified to use scandir
def clear_folder_if_exists(path):
	if not os.path.exists(path):
		return

	with os.scandir(path) as entries:
		for entry in entries:
			try:
				shutil.rmtree(entry.path)
			except OSError:
				os.remove(entry.path)

def zip(input_path, output_filename):
	try_remove_tree(output_filename)
	call(["7z", "a", output_filename, input_path])


def tar_gz(input_path, output_filename: str):
	try_remove_tree(output_filename)
	tempFileName = re.sub("\\.gz", "", output_filename, re.IGNORECASE)
	call(["7z", "a", tempFileName, input_path])
	call(["7z", "a", output_filename, tempFileName])
	os.remove(tempFileName)

def pre_build_validation():
	import installConfiguration
	import common
	import fileVersionManagement
	print("Travis validation started")

	# Code is modified version of main.getSubModConfigList since I don't want to import/setup logger.py
	sub_mod_configs = []
	for mod in common.getModList("installData.json", isURL=False):
		for submod in mod['submods']:
			conf = installConfiguration.SubModConfig(mod, submod)
			sub_mod_configs.append(conf)

	fileVersionManagement.Developer_ValidateVersionDataJSON(sub_mod_configs)
	print("Travis validation success")


print("Python {}".format(sys.version))
min_python = (3, 8)
if not sys.version_info >= min_python:
	print(f"\nERROR: This script requires at least Python {min_python[0]}.{min_python[1]} to run")
	raise SystemExit(-1)

pre_build_validation()

print("\nTravis python build script started\n")

# first, copy the files we want into a staging folder
staging_folder = os.path.join(tempfile.gettempdir(), '07th-mod_patcher_staging')
output_folder = 'travis_installer_output'
bootstrap_copy_folder = 'travis_installer_bootstrap_copy'

# No wildcards allowed in these paths to be ignored
ignore_paths = [
	staging_folder,
	output_folder,
	bootstrap_copy_folder,
	'JSONValidator',
	'installData.json',
	'versionData.json',
	'cachedDownloadSizes.json',
	'httpGUI/node_modules',
	'bootstrap',
	'.git',
	'.github',
	'.idea',
	'.gitignore',
	'.travis.yml',
	'__pycache__',
	'news',
	'install_loader',
	'installerTests',
	'Onikakushi Ch.1 Downloads',
	'Watanagashi Ch.2 Downloads',
	'Tatarigoroshi Ch.3 Downloads',
	'Himatsubushi Ch.4 Downloads',
	'Meakashi Ch.5 Downloads',
	'Tsumihoroboshi Ch.6 Downloads',
	'Minagoroshi Ch.7 Downloads',
	'Console Arcs Downloads',
	'Umineko Question (Ch. 1-4) Downloads',
	'Umineko Answer (Ch. 5-8) Downloads',
	'Umineko Tsubasa Downloads',
	'Umineko Hane Downloads',
	'INSTALLER_LOGS',
	'github_actions_changelog_template.txt',
]
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

# Make sure the output folder exists
os.makedirs(output_folder, exist_ok=True)

clear_folder_if_exists(bootstrap_copy_folder)
clear_folder_if_exists(output_folder)
clear_folder_if_exists(staging_folder)

# copy bootstrap folder to a temp folder
shutil.copytree('bootstrap', bootstrap_copy_folder, dirs_exist_ok=True)

# Note: previously the script created output folder in advance and then used dirs_exist_ok=True to
# sidestep a problem in Python 3.8 where copying from the current folder
# '.' would not ignore the destination folder even when applied as an ignore folder (the function caches
# ignore folders *before* creating the output folder), leading to endless recursive copying behavior.
# We now use a temp folder not in the cwd which avoids this behavior and should work on any Python 3.X version
# copy all files in the root github directory, except those in ignore_patterns
shutil.copytree('.', staging_folder, ignore=ignore_filter, dirs_exist_ok=True)

# Save the build information in the staging folder. Will later be read by installer.
with open(os.path.join(staging_folder, 'build_info.json'), 'w', encoding='utf-8') as build_info_file:
	json.dump({
		"build_date": f"{datetime.datetime.now()}",
		"git_tag": f"{GIT_TAG}",
	}, build_info_file, indent="\t", sort_keys=True)

# now, copy the staged files into each os's bootstrap folder's install_data directory
for osBootStrapPath in glob.glob(f'{bootstrap_copy_folder}/*/'):
	print("processing", osBootStrapPath)
	# osBootStrapPath = os.path.join(bootStrapRoot, osFolderName)
	osInstallData = os.path.join(osBootStrapPath, 'install_data')
	if IS_WINDOWS:
		call(['xcopy', '/E', '/I', '/Y', staging_folder, osInstallData])
	else:
		call(['cp', '-r', staging_folder + '/.', osInstallData])

# FOR WINDOWS BUILDS ONLY: Download and Extract the embedded python archive
if not BUILD_LINUX_MAC:
	ZipFile(
		BytesIO(urlopen(EMBEDDED_PYTHON_ZIP_URL).read())
	).extractall(path=f'./{bootstrap_copy_folder}/higu_win_installer_32/install_data/python')

# RELATIVE PATHS MUST CONTAIN ./
if BUILD_LINUX_MAC:
	os.rename(f'./{bootstrap_copy_folder}/higu_linux64_installer/', f'./{bootstrap_copy_folder}/07th-Mod_Installer_Linux64/')
	tar_gz(f'./{bootstrap_copy_folder}/07th-Mod_Installer_Linux64/', os.path.join(output_folder, '07th-Mod.Installer.linux.tar.gz'))
# zip(f'./{bootstrap_copy_folder}/higu_win_installer/', os.path.join(output_folder, '07th-Mod.Installer.win64.zip'))
# zip(f'./{bootstrap_copy_folder}/higu_win_installer_32/', os.path.join(output_folder, '07th-Mod.Installer.win.zip'))

if not BUILD_LINUX_MAC:
	# Create an archive of the contents install_data folder (no subfolder)
	loader_src_folder = 'install_loader/src'
	tar_path = os.path.join(loader_src_folder, 'install_data.tar')
	xz_path = tar_path + '.xz'
	try_remove_tree(tar_path)
	try_remove_tree(xz_path)
	call(['7z', 'a', '-aoa', tar_path, f'./{bootstrap_copy_folder}/higu_win_installer_32/install_data/*'])
	call([
			'7z',
			'a',
			'-mx=9',     # max compression level
			'-md=256m',  # 256m dictionary size (memory used for compression is much higher than this)
			'-mmt=3',    # use 3 threads (using > 3 threads results in increased archive size)
			'-aoa',
			xz_path,
			tar_path
		])

	# Compile the rust loader
	# If not using a manifest file, DO NOT put the words "install", "patch", "update", etc. in the filename,
	# or else windows will force running the .exe as administrator
	# https://stackoverflow.com/questions/31140051/windows-force-uac-elevation-for-files-if-their-names-contain-update
	# If using msvc linker, embed a manifest/change msvc linker options, as per
	# https://www.reddit.com/r/rust/comments/8tooi0/hey_rustaceans_got_an_easy_question_ask_here/e1lk7tw?utm_source=share&utm_medium=web2x
	loader_exe_name = '07th-Mod.Installer.Windows.exe'
	call(['cargo', 'rustc', '--release', '--', '-C', 'link-arg=/MANIFEST:embed'], cwd=loader_src_folder)

	# Copy the exe to the final output folder
	final_exe_path = os.path.join(output_folder, loader_exe_name)
	shutil.copy('install_loader/target/release/seventh_mod_loader.exe', final_exe_path)

# NOTE: mac zip doesn't need subdir - use '/*' to achieve this
if BUILD_LINUX_MAC:
	os.rename(f'./{bootstrap_copy_folder}/higu_mac_installer/', f'./{bootstrap_copy_folder}/07th-Mod_Installer_Mac/')
	zip(f'./{bootstrap_copy_folder}/07th-Mod_Installer_Mac/*', os.path.join(output_folder, '07th-Mod.Installer.mac.zip'))

try_remove_tree(staging_folder)
try_remove_tree(bootstrap_copy_folder)
