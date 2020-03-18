from __future__ import print_function, unicode_literals

import datetime
import io
import re
import shutil
import sys, os, platform, subprocess, json
import threading
import time
import traceback
import tempfile
import webbrowser

import commandLineParser
import installConfiguration

try:
	"".decode("utf-8")
	def decodeStr(string):
		return string.decode("utf-8")
except AttributeError:
	def decodeStr(string):
		return string

try:
	from urllib.request import urlopen, Request
	from urllib.parse import urlparse, quote
	from urllib.error import HTTPError
except ImportError:
	from urllib2 import urlopen, Request, HTTPError
	from urlparse import urlparse
	from urllib import quote

try:
	import ssl
	if ssl.OPENSSL_VERSION_NUMBER < 0x10001000: # Version 1.0.1, first to support TLS 1.1 and 1.2
		SSL_VERSION_IS_OLD = True
	else:
		SSL_VERSION_IS_OLD = False
except ImportError:
	# No SSL at all
	SSL_VERSION_IS_OLD = True

try:
	from typing import Optional, List, Tuple, Dict
except:
	pass

def findWorkingExecutablePath(executable_paths, flags):
	#type: (List[str], List[str]) -> str
	"""
	Try to execute each path in executable_paths to see which one can be called and returns exit code 0
	The 'flags' argument is any extra flags required to make the executable return 0 exit code
	:param executable_paths: a list [] of possible executable paths (eg. "./7za", "7z")
	:param flags: a list [] of any extra flags like "-h" required to make the executable have a 0 exit code
	:return: the path of the valid executable, or None if no valid executables found
	"""
	with open(os.devnull, 'w') as os_devnull:
		for path in executable_paths:
			try:
				if subprocess.call([path] + flags, stdout=os_devnull, stderr=os_devnull) == 0:
					return path
			except:
				pass

	return None

# Python 2 Compatibility
def read_input():
	try:
		return input()
	except:
		return raw_input()

def printErrorMessage(text):
	"""
	Prints message in red if stdout is a tty
	"""
	try:
		if sys.stdout.isatty:
			print("\x1b[1m\x1b[31m" + text + "\x1b[0m")
		else:
			print(text)
	except AttributeError:
		print(text)


################################################## Global Variables#####################################################
class Globals:
	GITHUB_MASTER_BASE_URL = "https://raw.githubusercontent.com/07th-mod/python-patcher/master/"
	# The installer info version this installer is compatibile with
	# Increment it when you make breaking changes to the json files
	JSON_VERSION = 7

	# Define constants used throughout the script. Use function calls to enforce variables as const
	IS_WINDOWS = platform.system() == "Windows"
	IS_LINUX = platform.system() == "Linux"
	IS_MAC = platform.system() == "Darwin"

	# Set os string matching string used in the JSON file, for convenience
	OS_STRING = "windows"
	if IS_LINUX:
		OS_STRING = "linux"
	elif IS_MAC:
		OS_STRING = "mac"

	ARIA_EXECUTABLE = None
	SEVEN_ZIP_EXECUTABLE = None
	CURL_EXECUTABLE = None # Not required, but if available will be used to download filenames on systems with old SSL versions

	#Print this string from the installer thread to notify of an error during the installation.
	INSTALLER_MESSAGE_ERROR_PREFIX = "Install Failed!: "

	LOG_FOLDER = 'INSTALLER_LOGS'
	LOG_BASENAME = datetime.datetime.now().strftime('MOD-INSTALLER-LOG-%Y-%m-%d_%H-%M-%S.txt')
	LOG_FILE_PATH = os.path.join(LOG_FOLDER, LOG_BASENAME)

	LOGS_ZIP_FILE_PATH = "07th-mod-logs.zip"

	# Set to 'True' in main.py if installData.json is detected on disk
	DEVELOPER_MODE = False

	BUILD_INFO = 'Build info not yet retrieved'
	INSTALL_LOCK_FILE_PATH = 'lockfile.lock'

	IS_PYTHON_2 = sys.version_info.major == 2

	DOWNLOAD_TO_EXTRACTION_SCALING = 2.5

	URL_FILE_SIZE_LOOKUP_TABLE = {}

	PERMISSON_DENIED_ERROR_MESSAGE = "Permission error: See our installer wiki FAQ about this error at http://07th-mod.com/wiki/Higurashi/Higurashi-Part-1---Voice-and-Graphics-Patch/#extraction-stage-fails-i-get-an-acess-denied-error-when-overwriting-files"

	@staticmethod
	def scanForExecutables():
		# query available executables. If any installation of executables is done in the python script, it must be done
		# before this executes
		print("Validating Executables...")
		Globals.CURL_EXECUTABLE = findWorkingExecutablePath(["curl"], ["-I", "https://07th-mod.com/"])

		ariaSearchPaths = ["./aria2c", "./.aria2c", "aria2c"]
		Globals.ARIA_EXECUTABLE = findWorkingExecutablePath(ariaSearchPaths, ['https://07th-mod.com/', '--dry-run=true'])

		if Globals.ARIA_EXECUTABLE is None:
			print("\nWARNING: aria2 failed to download 07th-mod website. Using fallback detection method.")
			Globals.ARIA_EXECUTABLE = findWorkingExecutablePath(ariaSearchPaths, ['-h'])

		if Globals.ARIA_EXECUTABLE is None:
			# TODO: automatically download and install dependencies
			print("ERROR: aria2c executable not found (aria2c). Please install the dependencies for your platform.")
			exitWithError()
		else:
			print("Found aria2c at [{}]".format(Globals.ARIA_EXECUTABLE))

		Globals.SEVEN_ZIP_EXECUTABLE = findWorkingExecutablePath(["./7za64", "./7za", "./.7za", "7za", "./7z", "7z"], ['-h'])
		if Globals.SEVEN_ZIP_EXECUTABLE is None:
			# TODO: automatically download and install dependencies
			print("ERROR: 7-zip executable not found (7za or 7z). Please install the dependencies for your platform.")
			exitWithError()
		else:
			print("Found 7-zip at [{}]".format(Globals.SEVEN_ZIP_EXECUTABLE))

	@staticmethod
	def loadCachedDownloadSizes(modList):
		"""
		In normal mode:
		  - Load cached download sizes from Github (`cachedDownloadSizes.json` in repo root).
		  - On failure to retrieve, will leave the lookup table as an empty dict
		In developer mode:
		  - Load cached download sizes from `cachedDownloadSizes.json` on disk
		  - If any URLs from installData.json are missing, this function will automatically update `cachedDownloadSizes.json`

		:param modList: The JSON object returned by common.getModList()
		"""
		try:
			if Globals.DEVELOPER_MODE:
				downloadSizesDict, _error = getJSON('cachedDownloadSizes.json', isURL=False)
			else:
				downloadSizesDict, _error = getJSON(Globals.GITHUB_MASTER_BASE_URL + 'cachedDownloadSizes.json', isURL=True)

			if downloadSizesDict is None:
				print("ERROR: Failed to retrieve cachedDownloadSizes.json file")
			else:
				Globals.URL_FILE_SIZE_LOOKUP_TABLE = downloadSizesDict

			# In developer mode, check that all URLs in the json file also exist in the downloadList.
			# If they don't, regenerate the downloadList
			if Globals.DEVELOPER_MODE:
				if sys.version_info >= (3, 0):
					import cacheDownloadSizes
					for urlToCheck in cacheDownloadSizes.getAllURLsFromModList(modList):
						if urlToCheck not in Globals.URL_FILE_SIZE_LOOKUP_TABLE:
							print("DEVELOPER: cachedDownloadSizes.json is missing url {} - regenerating list".format(urlToCheck))
							cacheDownloadSizes.generateCachedDownloadSizes()
							break
				else:
					print("DEVELOPER: skipping cachedDownloadSizes.json regeneration as you are running Python 2. Please use Python 3 to regenerate the download size cache.")

		except Exception:
			print("Developer ERROR: Failed to read URL File Size Lookup Table")
			traceback.print_exc()

	@staticmethod
	def getBuildInfo():
		try:
			with open('build_info.txt', 'r') as build_info_file:
				Globals.BUILD_INFO = build_info_file.read()
		except:
			Globals.BUILD_INFO = 'No build_info.txt file found - probably a dev release.'

def exitWithError():
	""" On Windows, prevent window closing immediately when exiting with error. Other plaforms just exit. """
	print("ERROR: The installer cannot continue. Press any key to exit...")
	if Globals.IS_WINDOWS:
		read_input()
	sys.exit(1)

# You can use the 'exist_ok' of python3 to do this already, but not in python 2
def makeDirsExistOK(directoryToMake):
	try:
		os.makedirs(directoryToMake)
	except OSError:
		pass

def trySystemOpen(path, normalizePath=False):
	"""
	Tries to open a given path using the system 'open' function
	The path can be a on-disk folder or a URL
	NOTE: this function call does not block! (uses subprocess.Popen)
	NOTE: paths won't open properly on windows if they contain backslashes. Set 'normalizePath' to handle this problem.
	:param path: the path to show
	:return: true if successful, false otherwise
	"""
	try:
		if normalizePath:
			path = os.path.normpath(path)

		if Globals.IS_WINDOWS:
			return subprocess.Popen(["explorer", path]) == 0
		elif Globals.IS_MAC:
			return subprocess.Popen(["open", path]) == 0
		else:
			return subprocess.Popen(["xdg-open", path]) == 0
	except:
		return False

def openURLInBrowser(url):
	webbrowser.open(url, new=2, autoraise=True)

#TODO: capture both stdout and stderr
# TODO: in the future, this function could be simplified (remove aria2c specific hacks) by:
# - using --summary-interval=5 for aria2c to force the long summary to be printed more often (which gives a newline)
# - OR running aria2c in RPC mode
# 7z would also need to be checked on all platforms as working correctly.
# lineMonitor must be an object with a "process(line)" function, which will be called at each newline, %, or ']' char
# It can be used to monitor the output of the process being run.
def runProcessOutputToTempFile(arguments, ariaMode=False, sevenZipMode=False, lineMonitor=None):
	print("----- BEGIN EXECUTING COMMAND: [{}] -----".format(" ".join(arguments)))

	# need universal_newlines=True so stdout is opened in normal. However, this might result in garbled japanese(unicode) characters!
	# to fix this properly, you would need to make a custom class which takes in raw bytes using stdout.read(10)
	# and then periodically convert newline delimited sections of the text to utf-8 (or whatever encoding), and catch bad encoding errors
	# See comments on https://stackoverflow.com/a/15374326/848627 and answer https://stackoverflow.com/a/48880977/848627
	proc = subprocess.Popen(arguments, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

	def readUntilEOF(proc, fileLikeObject):
		stringBuffer = []
		while proc.poll() is None:
			try:
				fileLikeObject.flush()
				while True:
					character = fileLikeObject.read(1)

					if character:
						stringBuffer.append(character)

						writeOutBuffer = False

						# Write out buffer if newline detected
						if character == '\n':
							writeOutBuffer = True

						# Insert newline after ']' characters
						if ariaMode and character == ']':
							stringBuffer.append('\n')
							writeOutBuffer = True

						# Insert newline after % characters
						if sevenZipMode and character == '%':
							stringBuffer.append('\n')
							writeOutBuffer = True

						if writeOutBuffer:
							line = ''.join(stringBuffer)
							print(line, end='')
							if lineMonitor:
								lineMonitor.process(line)
							stringBuffer = []
					else:
						break
			except Exception as e:
				#reduce cpu usage if some exception is continously thrown
				print("Error in [runProcessOutputToTempFile()]: {}".format(traceback.format_exc(e)))
				time.sleep(.1)

	# Monitor stderr on one thread, and monitor stdout on main thread
	t = threading.Thread(target=readUntilEOF, args=(proc, proc.stderr))
	t.start()

	readUntilEOF(proc, proc.stdout)

	print("--------------- EXECUTION FINISHED ---------------\n")
	return proc.returncode

#when calling this function, use named arguments to avoid confusion!
def aria(downloadDir=None, inputFile=None, url=None, followMetaLink=False, useIPV6=False, outputFile=None):
	"""
	Calls aria2c with some default arguments:

	Note about continuing downloads/control file save frequency
	By default, aria2c saves the control file every 60s, or when aria2c is closed non-forcefully.
	This means that if you close aria2c forcefully, you will lose up to the last 1 minute of download.
	This value can be changed with --auto-save-interval=<SEC>, but we have left it as the default here.

	:param downloadDir: The directory to store the downloaded file(s)
	:param inputFile: The path to a file containing multiple URLS to download (see aria2c documentation)
	:param outputFile: When downloading a single file, if this is specified, it will be downloaded with the given name
	:return Returns the exit code of the aria2c call
	"""
	arguments = [
		Globals.ARIA_EXECUTABLE,
		"--file-allocation=none", # Pre-allocate space where the downloaded file will be saved
		'--continue=true', # Allow continuing the download of a partially downloaded file (is this flag actually necessary?)
		'--retry-wait=5',  # Seconds to wait between retries
		'-m 0', # max number of retries (0=unlimited). In some cases, like server rejects download, aria2c won't retry.
		'-x 8', # max connections to the same server
		'-s 8', # Split - Try to use N connections per each download item
		'-j 1', # max concurrent download items (eg number of separate urls which can be downloaded in parallel)
		'--auto-file-renaming=false',
		# By default, if aria2c detects a file already exists with the same name, and is different size to the file
		# being downloaded (lets call this 'test.zip'), it will save to a different name ('test.2.zip', 'test.3.zip' etc)
		# This option prevents this from happening. Continuing existing downloads where the file size is the same is still supported.
		'--allow-overwrite=true',
		# By default, aria2c will just error out if auto-renaming is disabled. Enabling this option allows aria2c to overwrite existing files,
		# if they cannot be continued (by the --continue argument)
	]

	if followMetaLink:
		arguments.append('--follow-metalink=mem')
		arguments.append('--check-integrity=true')  # check integrity when using metalink
	else:
		arguments.append('--follow-metalink=false')

	if not useIPV6:
		arguments.append('--disable-ipv6=true')

	#Add an extra command line argument if the function argument has been provided
	if downloadDir:
		arguments.append('-d ' + downloadDir)

	if inputFile:
		arguments.append('--input-file=' + inputFile)

	if url:
		arguments.append(url)

	if outputFile:
		arguments.append("--out=" + outputFile)

	# On linux, there is some problem where the console buffer is not read by runProcessOutputToTempFile(...) until
	# a newline is printed. I was unable to fix this properly, however setting 'summary-interval' (default 60s) lower will
	# force a newline to be printed every 5 seconds/the console output to flush.
	if Globals.IS_LINUX:
		arguments.append('--summary-interval=5')

	# with open('seven_zip_stdout.txt', "w", buffering=100) as outfile:
	# 	return subprocess.call(arguments, stdout=outfile)
	return runProcessOutputToTempFile(arguments, ariaMode=True)


class SevenZipMonitor:
	regexSevenZipError = re.compile(r'^\s*ERROR:.*')

	def __init__(self):
		self.error_access_denied = False
		self.error_delete_output_file = False
		self.error_data = False
		self.unknown_error_string = None

	def process(self, line):
		if SevenZipMonitor.regexSevenZipError.match(line):
			got_error = False

			if 'Data Error' in line:
				self.error_data = True
				got_error = True

			if 'Access is denied' in line:
				self.error_access_denied = True
				got_error = True

			if 'Can not delete output file' in line:
				self.error_access_denied = True
				got_error = True

			if not got_error:
				self.unknown_error_string = line

	def getErrorMessage(self):
		errors = []

		if self.error_access_denied or self.error_delete_output_file:
			errors.append(Globals.PERMISSON_DENIED_ERROR_MESSAGE)

		if self.error_data:
			errors.append("Archive Corrupted Error: This error should never happen - please send the 07th-mod team your install log")

		if self.unknown_error_string:
			errors.append("Unknown Error: {}. You may want to check our Installer FAQ: http://07th-mod.com/wiki/Higurashi/Higurashi-Part-1---Voice-and-Graphics-Patch/#installer-faq-and-troubleshooting or get help on our Discord Server: https://discord.gg/pf5VhF9".format(self.unknown_error_string))

		return '\n'.join(errors)

def sevenZipExtract(archive_path, outputDir=None, lineMonitor=None):
	arguments = [Globals.SEVEN_ZIP_EXECUTABLE,
				 "x",
				 archive_path,
				 "-aoa",  # overwrite All existing files without prompt (-ao means 'overwrite mode', a means 'All')
				 "-bso1", # redirect standard Output messages to stdout
				 "-bsp1", # redirect Progress update messages to stdout
				 "-bse2", # redirect Error messages to stderr
				 ]

	if outputDir:
		arguments.append('-o' + outputDir)
	return runProcessOutputToTempFile(arguments, sevenZipMode=True, lineMonitor=lineMonitor)

def sevenZipTest(archive_path):
	"""
	Validate/Test a 7-zip archive.

	:param archive_path: The path to the archive to test
	:return: The 7-zip return code as an int (0 is Success),
	"""
	arguments = [Globals.SEVEN_ZIP_EXECUTABLE, "t", archive_path]
	return runProcessOutputToTempFile(arguments, sevenZipMode=True)

def tryGetRemoteNews(newsName):
	"""
	:param changelogName: the name of the changelog to retrieve, without file extension
	There should be one for each mod, and one called 'news' for the index.html page
	:return:
	"""
	localPath = 'news/' + newsName + '.md'
	url = Globals.GITHUB_MASTER_BASE_URL + 'news/' + quote(newsName) + '.md'
	try:
		if Globals.DEVELOPER_MODE and os.path.exists(localPath):
			file = open(localPath, 'rb') #read as bytes to match urlopen in python 3
		else:
			file = urlopen(Request(url, headers={"User-Agent": ""}))
	except HTTPError as error:
		return """The news [{}] couldn't be retrieved from [{}] the server.""".format(newsName, url)

	return file.read().decode('utf-8')

def getDonationStatus():
	# type: () -> (Optional[str], Optional[str])
	"""
	:return: (months_remaining, funding_goal_percentage) as a tuple (can both be None if regex failed)
	"""
	# NOTE: Even though the markdown has double-quotes, the served page has no quotation
	#       so do not put any double quotes in the below regex
	donationStatusRegex = re.compile(r'<progress\s*value=(\d+).*data-months-remaining=(\d+)>', re.IGNORECASE)

	try:
		file = urlopen(Request(r"http://07th-mod.com/wiki/", headers={"User-Agent": ""}))
	except HTTPError as error:
		return None, None

	entirePage = file.read().decode('utf-8')

	match = donationStatusRegex.search(entirePage)
	if match:
		return match.group(2), match.group(1)

	return None, None

def getJSON(jsonURI, isURL):
	#type: (str, bool) -> (Dict, Exception)
	"""

	:param jsonURI: Path to a file or URL to download
	:param isURL: Specify whether the URI is for a URL or path
	:return: 
	"""
	tmpdir = None
	try:
		if isURL:
			if not SSL_VERSION_IS_OLD:
				file = urlopen(Request(jsonURI, headers={"User-Agent": ""}))
			else:
				tmpdir = tempfile.mkdtemp()
				if aria(url=jsonURI, downloadDir=tmpdir, outputFile="info.json") != 0:
					return None, Exception("ERROR - could not download modList [{}]. Installation Stopped")

				file = io.open(os.path.join(tmpdir, "info.json"), "r", encoding='utf-8')
		else:
			file = io.open(jsonURI, "r", encoding='utf-8')
	except HTTPError as error:
		return None, error
	except Exception as anyError:
		return None, anyError

	info = json.load(file, encoding='utf-8')
	file.close()
	if tmpdir:
		shutil.rmtree(tmpdir)

	return info, None

def getModList(jsonURI, isURL):
	"""
	Gets the list of available mods from the 07th Mod server

	:return: A list of mod info objects
	:rtype: list[dict]
	"""
	def errorHandler(error):
		print(error)
		print("Couldn't reach 07th Mod Server to download patch info")
		print("Note that we have blocked Japan from downloading (VPNs are compatible with this installer, however)")
		exitWithError()

	info, exception = getJSON(jsonURI, isURL)
	if info is None:
		errorHandler(exception)

	try:
		version = info["version"]
		if version > Globals.JSON_VERSION:
			print("\n\n-------------------------------------------------------------------------------")
			printErrorMessage("Your installer is out of date.")
			printErrorMessage("Please download the latest version of the installer and try again.")
			print("\nYour installer is compatible with mod listings up to version {} but the latest listing is version {}".format(Globals.JSON_VERSION, version))
			print("-------------------------------------------------------------------------------\n")
			exitWithError()
	except KeyError:
		print("Warning: The mod info listing is missing a version number.  Things might not work.")
		return info
	return info["mods"]

def printSupportedGames(modList):
	"""
	Prints a list of games that have mods available for them
	:param list[dict] modList: The list of available mods
	"""
	print("Supported games:")
	for game in set(x["target"] for x in modList):
		print("  " + game)

def makeExecutable(executablePath):
	current = os.stat(executablePath)
	os.chmod(executablePath, current.st_mode | 0o111)

def getMetalinkFilenames(url):
	import xml.etree.ElementTree as ET

	downloadDir = tempfile.mkdtemp()

	# Download the metalink file
	if aria(downloadDir, url=url) != 0:
		raise Exception("ERROR - could not download metalink [{}]. Installation Stopped".format(url))

	# Load/Parse the metalink file into memory
	tree = ET.parse(
		os.path.join(downloadDir, os.path.basename(url))
	)

	# Remove the metalink file/folder as soon as it's loaded into memory
	shutil.rmtree(downloadDir)

	root = tree.getroot()

	def getTagNoNamespace(tag):
		return tag.split('}')[-1]

	# return the 'name' attribute of each 'file' node.
	# ignore namespaces by removing the {stuff} part of the tag
	filename_length_pairs = []
	for fileNode in root.iter():
		if getTagNoNamespace(fileNode.tag) == 'file':
			length = 0
			for fileNodeChild in fileNode:
				if getTagNoNamespace(fileNodeChild.tag) == 'size':
					try:
						length = int(fileNodeChild.text)
					except:
						pass
			filename_length_pairs.append((fileNode.attrib['name'], length))

	return filename_length_pairs

class SevenZipException(Exception):
	def __init__(self, errorReason):
		# type: (str) -> None
		self.errorReason = errorReason  # type: str

	def __str__(self):
		return self.errorReason

def extractOrCopyFile(filename, sourceFolder, destinationFolder, copiedOutputFileName=None):
	makeDirsExistOK(destinationFolder)
	sourcePath = os.path.join(sourceFolder, filename)

	if '.7z' in filename.lower() or '.zip' in filename.lower():
		monitor = SevenZipMonitor()
		if sevenZipExtract(sourcePath, outputDir=destinationFolder, lineMonitor=monitor) != 0:
			raise SevenZipException("{}\n\n Could not extract [{}]".format(monitor.getErrorMessage(), sourcePath))

	else:
		try:
			shutil.copy(sourcePath, os.path.join(destinationFolder, copiedOutputFileName if copiedOutputFileName else filename))
		except shutil.SameFileError:
			print("Source and Destination are the same [{}]. No action taken.".format(sourcePath))

def prettyPrintFileSize(fileSizeBytesWithSign):
	#type: (int) -> str

	fileSizeBytes = fileSizeBytesWithSign
	sign = ''

	if fileSizeBytesWithSign < 0:
		fileSizeBytes = -fileSizeBytesWithSign
		sign = '-'

	if fileSizeBytes >= 1e9:
		return "{}{:.2f}".format(sign, fileSizeBytes / 1e9).strip('0').strip('.') + ' GB'
	elif fileSizeBytes >= 1e6:
		return "{}{:.2f}".format(sign, fileSizeBytes / 1e6).strip('0').strip('.') + ' MB'
	elif fileSizeBytes > 0:
		return "{}{:.2f}".format(sign, fileSizeBytes / 1e3).strip('0').strip('.') + ' KB'
	else:
		return "0 KB"


class DownloaderAndExtractor:
	"""
	####################################################################################################################
	#
	# Downloads and/or Extracts a list of ModFile objects
	#
	# Usage: Call 'download' then 'extract'.
	# If you have metalinks in your path, callin only 'extract' may require fetching the metafiles to determine what
	# to extract
	#
	# a ModFile is an object which contains a url and a priority (int). The priority extraction order.
	# See the modfile class for more information
	# You can use the FullInstallConfig.buildFileListSorted() to generate the modFileList, which handles
	# ordering the ModFiles and using different modfiles on different operating systems/steam/mg installs
	#
	# Metafile Handling:
	# - For metafiles, we need to look for filenames within each metafile to know what to extract
	# - The order of the download and extraction is maintained through the list ordering.
	#
	# Archive Handling:
	# - Archives will be extracted in to the downloadTempDir folder
	#
	# Other file handling:
	# - Any other types of files will be copied (overwritten) from the downloadTempDir to the extractionDir
	# - If the path of the file is the same as the destination (a no op), the file won't be copied (it will do nothing)
	#
	# Folder Creation:
	# - All folders will be created if they don't already exist
	#
	# Failure Modes:
	# - if any downloads or extractions fail, the script will terminate
	# - TODO: could improve success rate by retrying aria downloads multiple times
	#
	####################################################################################################################

	:param modFileList:		The a list of ModFile objects which will be downloaded and/or extracted
	:param downloadTempDir: The folder where downloads will be saved
	:param extractionDir:	The folder where archives will be extracted to, and where any files will be copied to
	:return:
	"""
	MAX_DOWNLOAD_ATTEMPTS = 3

	class ExtractableItem:
		def __init__(self, filename, length, destinationPath, fromMetaLink, remoteLastModified):
			self.filename = filename
			self.length = length
			self.destinationPath = os.path.normpath(destinationPath)
			self.fromMetaLink = fromMetaLink
			self.remoteLastModified = remoteLastModified

		def __repr__(self):
			return '[{} ({})] to [{}] {}'.format(self.filename, prettyPrintFileSize(self.length), self.destinationPath, "(metalink)" if self.fromMetaLink else "")

		def clearDownloadIfNeededAndWriteControlFile(self, downloadDir):
			# Files from metalinks are checksummed, so clearing old downloads is not required
			if self.fromMetaLink:
				return

			# If remote has no date modified, assume file needs to be cleared
			if self.remoteLastModified is None:
				print("ExtractableItem: Clearing [{}] as remote has no last-modified".format(self.filename))
				self._tryDeleteOldDownloadAndAriaFile(downloadDir)
				return

			# If local date modified is different, clear the file and update control file
			localDateModifiedControlPath = os.path.join(downloadDir, self._dateModifiedControlFilename())
			localLastModified = self._readLocalDateModified(localDateModifiedControlPath)
			if self._normalizeDateModified(localLastModified) != self._normalizeDateModified(self.remoteLastModified):
				print("ExtractableItem: Clearing [{}] as local [{}] and remote [{}] last-modified differ"
				      .format(self.filename, localLastModified, self.remoteLastModified))
				self._tryDeleteOldDownloadAndAriaFile(downloadDir)
				self._updateLocalDateModified(localDateModifiedControlPath)
			else:
				# Take no action if local and remote date modified is the same - can resume the download normally
				pass

		@staticmethod
		def _normalizeDateModified(lastModifiedStringOrNone):
			#type: (Optional[str]) -> Optional[str]
			return None if lastModifiedStringOrNone is None else lastModifiedStringOrNone.strip()

		def _dateModifiedControlFilename(self):
			return self.filename + ".dateModified"

		def _readLocalDateModified(self, localDateModifiedControlPath):
			if not os.path.exists(localDateModifiedControlPath):
				return None

			try:
				with io.open(localDateModifiedControlPath, "r", encoding='UTF-8') as f:
					return f.read()
			except:
				print("Failed to load date modified file {}".format(localDateModifiedControlPath))
				return None

		def _updateLocalDateModified(self, localDateModifiedControlPath):
			try:
				with io.open(localDateModifiedControlPath, "w", encoding='UTF-8') as f:
					f.write(self.remoteLastModified)
			except:
				print("Failed to write date modified file {}".format(localDateModifiedControlPath))

		def _tryDeleteOldDownloadAndAriaFile(self, downloadDir):
			oldDownloadPath = os.path.join(downloadDir, self.filename)
			try:
				if os.path.exists(oldDownloadPath):
					os.remove(oldDownloadPath)
				if os.path.exists(oldDownloadPath + ".aria2"):
					os.remove(oldDownloadPath + ".aria2")
			except Exception as e:
				print("ExtractableItem: Failed to delete {}: {}".format(oldDownloadPath, e))

	def __init__(self, modFileList, downloadTempDir, extractionDir, downloadProgressAmount=45, extractionProgressAmount=45):
		# type: (List[installConfiguration.ModFile], str, str, int, int) -> None
		self.modFileList = modFileList
		self.downloadTempDir = downloadTempDir
		self.defaultExtractionDir = extractionDir
		self.downloadAndExtractionListsBuilt = False

		# These variables indicate how much download and extract should count towards the total reported progress
		self.downloadProgressAmount = downloadProgressAmount
		self.extractionProgressAmount = extractionProgressAmount

		# Invariant: downloadList and extractablesForEachDownload should always be the same size
		self.downloadList = [] # type: List[str]
		self.extractablesForEachDownload = [] # type: List[List[DownloaderAndExtractor.ExtractableItem]]

		self.extractList = [] # type: List[DownloaderAndExtractor.ExtractableItem]

	def buildDownloadAndExtractionList(self):
		#type: () -> None
		"""
		This function fills in the self.downloadList and self.extractList lists, based on the self.modFileList
		If there are existing values in the self.downloadList or self.extractList, they are retained
		:return:
		"""

		commandLineParser.printSeventhModStatusUpdate(1, "Querying URLs to be Downloaded")
		for i, file in enumerate(self.modFileList):
			print("Querying URL: [{}]".format(file.url))
			self.addItemManually(file.url, self.defaultExtractionDir)

		self.downloadAndExtractionListsBuilt = True

	def download(self):
		if not self.downloadAndExtractionListsBuilt:
			self.buildDownloadAndExtractionList()

		# download all urls to the download temp folder
		makeDirsExistOK(self.downloadTempDir)
		makeDirsExistOK(self.defaultExtractionDir)

		# check if any downloads have been modified on the server - if so, delete the local downloads
		for extractableItem in self.extractList:
			extractableItem.clearDownloadIfNeededAndWriteControlFile(self.downloadTempDir)

		totalDownloadSize = self.totalDownloadSize()
		for i, url in enumerate(self.downloadList):
			extractables = self.extractablesForEachDownload[i]
			attempt = 0
			for attempt in range(DownloaderAndExtractor.MAX_DOWNLOAD_ATTEMPTS):
				overallPercentage = int(i*self.downloadProgressAmount/len(self.downloadList))
				commandLineParser.printSeventhModStatusUpdate(overallPercentage, "Downloading: {} (total) DL Folder: [{}] URL: [{}] (Attempt: {}/{})"
				                                              .format(prettyPrintFileSize(totalDownloadSize), self.downloadTempDir, url, attempt + 1, DownloaderAndExtractor.MAX_DOWNLOAD_ATTEMPTS))
				if aria(self.downloadTempDir, url=url, followMetaLink=DownloaderAndExtractor.__urlIsMetalink(url)) != 0:
					raise Exception("ERROR - could not download [{}]. Installation Stopped".format(url))

				# If all extractables were valid, then we are finished with this download item
				# and can move on to the next one
				if not self.extractablesHasInvalidArchives(extractables):
					break
			else:
				# Too many attempts
				raise Exception("ERROR - Tried to download [{}] {} times, but file was corrupted each time. Installation Stopped".format(url, attempt + 1))

	def extractablesHasInvalidArchives(self, extractables):
		# type:(List[DownloaderAndExtractor.ExtractableItem]) -> Optional[bool]
		"""
		NOTE: this validation function won't check certain types of files, and just skip over them:
		  - extractables from metalinks won't be checked as they should be guarenteed to download correctly
		  - extractables which aren't archives don't have a method to be checked, so they will be skipped

		If the file is a non-checksummed archive, test it to make sure it downloaded correctly.
		If it did not download correctly, delete the file.

		:param extractables:
		:return: returns true if at least one input extractable is invalid
		"""
		atLeastOneInvalid = False

		for extractableItem in extractables: #type: DownloaderAndExtractor.ExtractableItem
			# If the item was from a metalink, assume it was already verified/skip verification
			if extractableItem.fromMetaLink:
				continue

			# If the file doesn't look like an archive, skip it as we don't know how to validate it
			_, extension = os.path.splitext(extractableItem.filename)
			if extension not in ['.zip', '.7z']:
				continue

			# Use 7z to test if the archive is valid
			extractableItemPath = os.path.join(self.downloadTempDir, extractableItem.filename)
			if sevenZipTest(extractableItemPath) == 0:
				continue

			# Archive is not valid, so delete the item and flag that this set of files needs to be re-downloaded
			os.remove(extractableItemPath)
			atLeastOneInvalid = True

		return atLeastOneInvalid

	def extract(self):
		if not self.downloadAndExtractionListsBuilt:
			self.buildDownloadAndExtractionList()

		# extract or copy all files from the download folder to the game directory
		for i, extractableItem in enumerate(self.extractList):
			overallPercentage = self.downloadProgressAmount + int(i*self.extractionProgressAmount/len(self.extractList))
			commandLineParser.printSeventhModStatusUpdate(overallPercentage, "Extracting {}".format(extractableItem))
			fileNameNoExt, extension = os.path.splitext(extractableItem.filename)

			#TODO: the '.u' and '.utf' logic is specific to umineko - shouldn't be in this class
			extractOrCopyFile(extractableItem.filename,
			                  self.downloadTempDir,
			                  extractableItem.destinationPath,
			                  copiedOutputFileName=(fileNameNoExt + '.u') if '.utf' in extension else extractableItem.filename)

	def addItemManually(self, url, extractionDir):
		"""
		Use this function to manually add a file or metalink to download and extract, with a custom extraction directory
		Items added by this function will be downloaded/extracted AFTER any already existing items in the download/extract list.
		:param url: The URL or metalink to download
		:param extractionDir: The folder where the file(s) will be extracted
		"""
		extractables = DownloaderAndExtractor.getExtractableItem(url=url, extractionDir=extractionDir)
		self.downloadList.append(url)
		self.extractablesForEachDownload.append(extractables)
		self.extractList.extend(extractables)

	def printPreview(self):
		pretty_file_size = prettyPrintFileSize(self.totalDownloadSize())
		print("\nFirst these files will be downloaded (Total Download Size: {}):\n - ".format(pretty_file_size), end='')
		print('\n - '.join(self.downloadList))
		print("\nThen these files will be extracted or copied:\n - ", end='')
		print('\n - '.join(['{}'.format(x) for x in self.extractList]))
		print()

	def totalDownloadSize(self):
		return sum([x.length for x in self.extractList])

	@staticmethod
	def getExtractableItem(url, extractionDir):
		#type: (str, str) -> List[ExtractableItem]
		"""
		Returns a list of ExtractableItems given a url. ExtractableItems represent a file on disk which can be
		extracted or moved to the target `extractionDir` directory
		Normally each url represents exactly one file, but a metalink may contain multiple files.
		:param url: The url of the file or metalink to download
		:param extractionDir: Where to extract or move the downloaded file to after download is finished
		:return:
		"""
		if DownloaderAndExtractor.__urlIsMetalink(url):
			metalinkFilenames = getMetalinkFilenames(url)
			print("Metalink contains: ", metalinkFilenames)
			return [DownloaderAndExtractor.ExtractableItem(
				filename=filename,
				length=length,
				destinationPath=extractionDir,
				fromMetaLink=True,
				remoteLastModified=None) for filename, length in metalinkFilenames]
		else:
			filename, length, remoteLastModified = DownloaderAndExtractor.__getFilenameFromURL(url)
			return [DownloaderAndExtractor.ExtractableItem(
				filename=filename,
				length=length,
				destinationPath=extractionDir,
				fromMetaLink=False,
				remoteLastModified=remoteLastModified)]

	@staticmethod
	def __urlIsMetalink(url):
		name, ext = os.path.splitext(urlparse(url).path)
		return ext == '.meta4' or ext == '.metalink'

	@staticmethod
	def __getFilenameFromURL(url):
		# type: (str) -> Tuple[str, int, str]
		"""
		Returns the filename of the file at the given URL, and it's file size.
		If the file size cannot be retrieved, returns a file size of 0
		:param url: The url of a file or a url which will eventually redirect to a file
		:return: A tuple of (filename, filesize, remoteLastModified) of the file pointed by the url
		remoteLastModified can be None if not present in the http response header
		"""

		# It's not a huge deal if the filename download is insecure (the actual download is done with Aria)
		if SSL_VERSION_IS_OLD and Globals.CURL_EXECUTABLE is None and url[0:5] == "https":
			url = "http" + url[5:]

		# if the url has a contentDisposition header, use that instead
		contentDisposition = None
		remoteLastModified = None
		responseURL = url
		if SSL_VERSION_IS_OLD and Globals.CURL_EXECUTABLE is not None:
			# On old SSL if we have curl use that instead
			with open(os.devnull, 'w') as os_devnull:
				# Get the header, the -X GET is required because the github download links return a 403 if you try to send a HEAD request
				headers = subprocess.check_output(["curl", "-ILX", "GET", url], stderr=os_devnull).decode("utf-8")
			# If there's redirects curl may print multiple headers with multiple content dispositions.  We want the last one
			contentDisposition = re.findall("Content-Disposition: (.+)", headers, re.IGNORECASE)
			contentDisposition = contentDisposition[-1].strip() if contentDisposition else None
			lengthString = re.findall("Content-Length: (.+)", headers, re.IGNORECASE)
			lengthString = lengthString[-1].strip() if lengthString else None
			remoteLastModified = re.findall("Last-Modified: (.+)", headers, re.IGNORECASE)
			remoteLastModified = remoteLastModified[-1].strip() if remoteLastModified else None
			responseURL = re.findall("Location: (.+)", headers, re.IGNORECASE)
			responseURL = responseURL[-1].strip() if responseURL else url
		else:
			httpResponse = urlopen(Request(url, headers={"User-Agent": ""}))
			try:
				contentDisposition = httpResponse.getheader("Content-Disposition")  # python 3
				lengthString = httpResponse.getheader('Content-Length')
				remoteLastModified = httpResponse.getheader("Last-Modified")
			except AttributeError:
				contentDisposition = httpResponse.info().getheader("Content-Disposition")  # python 2
				lengthString = httpResponse.info().getheader('Content-Length')
				remoteLastModified = httpResponse.info().getheader("Last-Modified")
			responseURL = httpResponse.url

		try:
			length = int(lengthString)
		except:
			length = 0

		filename = None

		# try to set the filename based on the content disposition field
		if filename is None:
			if contentDisposition:
				result = re.search(r"filename=(.*)", contentDisposition)
				if result and len(result.groups()) > 0:
					filename = result.group(1).strip().strip('"')

		# try to set the filename based on the redirected url
		if filename is None:
			filename = os.path.basename(urlparse(responseURL).path)

		# default filename is derived from original URL
		if filename is None:
			filename = os.path.basename(urlparse(url).path)


		return filename, length, remoteLastModified

def tryCreateLockFile():
	# type: () -> ()
	"""
	Creates a global lock file if it doesn't already exist.
	All instances of the installer with the same current working directory will 'see' this lock file.
	"""
	try:
		if not os.path.exists(Globals.INSTALL_LOCK_FILE_PATH):
			with open(Globals.INSTALL_LOCK_FILE_PATH, 'w') as _:
				pass
	except:
		pass

def lockFileExists():
	# type: () -> bool
	"""
	Returns true if the lock file (indicating install in progress) exists, false otherwise.
	"""
	return os.path.exists(Globals.INSTALL_LOCK_FILE_PATH)

def tryDeleteLockFile():
	# type: () -> ()
	"""
	Tries to delete the lock file - no error is raised if it fails, but success / failure is logged to file
	"""
	try:
		if lockFileExists():
			os.remove(Globals.INSTALL_LOCK_FILE_PATH)
			print("Install Completed: Deleted the lock file")
	except:
		print('WARNING: Failed to delete lock file!')

def checkFreeSpace(installPath, recommendedFreeSpaceBytes):
	# type: (str, int) -> (Optional[bool], str)
	"""
	Checks for free disk space.
	NOTE: this function will return 'None' for haveEnoughFreeSpace if the disk space cannot be queried.
	This will happen on Python 2.7 installations (e.g. MacOS), however the freeSpaceAdvisoryString will still be populated

	:param installPath: The install path whose root disk is to be checked for free space
	:param recommendedFreeSpaceBytes: The recommended amount of free space for this installation
	:return: Tuple of:
	freeSpaceAdvisoryString: a message to the user indicating whether there is enough space on the selected install path
	haveEnoughFreeSpace: Indicates the free space status according to the following:
	 - null: Couldn't query the free space. freeSpaceAdvisoryString will still have a message in this case.
	 - false: There is not enough free space
	 - true: There is  enough free space on disk
	"""
	recommendedFreeSpaceString = prettyPrintFileSize(recommendedFreeSpaceBytes)

	# Try to calculate actual free space
	free_space = None
	try:
		from shutil import disk_usage
		free_space = disk_usage(installPath).free
	except:
		print("Failed to query amount of free disk space - probably using Python 2 on MacOS")
		pass

	freeSpaceAdvisoryString = "Install requires approximately {} of free disk space at [{}] for extraction and temporary files.".format(installPath, recommendedFreeSpaceString)
	haveEnoughFreeSpace = None

	if free_space is not None:
		freeSpaceString = prettyPrintFileSize(free_space)
		if free_space < recommendedFreeSpaceBytes:
			freeSpaceAdvisoryString = "WARNING: You might not have enough free disk space! at [{}]" \
			                          "(have {}, need {})".format(installPath, freeSpaceString, recommendedFreeSpaceString)
			haveEnoughFreeSpace = False
		else:
			freeSpaceAdvisoryString = "You have enough free disk space at [{}] (have {}, need {})".format(installPath, freeSpaceString,
			                                                                                      recommendedFreeSpaceString)
			haveEnoughFreeSpace = True

	return haveEnoughFreeSpace, freeSpaceAdvisoryString
