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
import gameScanner

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
	from typing import Optional, List, Tuple
except:
	pass

def findWorkingExecutablePath(executable_paths, flags):
	"""
	Try to execute each path in executable_paths to see which one can be called and returns exit code 0
	The 'flags' argument is any extra flags required to make the executable return 0 exit code
	:param executable_paths: a list [] of possible executable paths (eg. "./7za", "7z")
	:param flags: any extra flags like "-h" required to make the executable have a 0 exit code
	:return: the path of the valid executable, or None if no valid executables found
	"""
	with open(os.devnull, 'w') as os_devnull:
		for path in executable_paths:
			try:
				if subprocess.call([path, flags], stdout=os_devnull) == 0:
					print("Found valid executable:", path)
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
	githubMasterBaseURL = "https://raw.githubusercontent.com/07th-mod/python-patcher/master/"
	# The installer info version this installer is compatibile with
	# Increment it when you make breaking changes to the json files
	JSON_VERSION = 4

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

	#Print this string from the installer thread to notify of an error during the installation.
	INSTALLER_MESSAGE_ERROR_PREFIX = "07th Mod - Install failed due to error: "

	LOG_FOLDER = 'INSTALLER_LOGS'
	LOG_BASENAME = datetime.datetime.now().strftime('MOD-INSTALLER-LOG-%Y-%m-%d_%H-%M-%S.txt')
	LOG_FILE_PATH = os.path.join(LOG_FOLDER, LOG_BASENAME)

	LOGS_ZIP_FILE_PATH = "07th-mod-logs.zip"

	DEVELOPER_MODE = False

	BUILD_INFO = 'Build info not yet retrieved'
	INSTALL_LOCK_FILE_PATH = 'lockfile.lock'

	IS_PYTHON_2 = sys.version_info.major == 2

	@staticmethod
	def scanForExecutables():
		# query available executables. If any installation of executables is done in the python script, it must be done
		# before this executes
		Globals.ARIA_EXECUTABLE = findWorkingExecutablePath(["./aria2c", "./.aria2c", "aria2c"], '-h')
		if Globals.ARIA_EXECUTABLE is None:
			# TODO: automatically download and install dependencies
			print("ERROR: aria2c executable not found (aria2c). Please install the dependencies for your platform.")
			exitWithError()

		Globals.SEVEN_ZIP_EXECUTABLE = findWorkingExecutablePath(["./7za64", "./7za", "./.7za", "7za", "./7z", "7z"], '-h')
		if Globals.SEVEN_ZIP_EXECUTABLE is None:
			# TODO: automatically download and install dependencies
			print("ERROR: 7-zip executable not found (7za or 7z). Please install the dependencies for your platform.")
			exitWithError()

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
def runProcessOutputToTempFile(arguments, ariaMode=False, sevenZipMode=False):
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
							print(''.join(stringBuffer), end='')
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
	TODO: list what each default argument does as comments next to arguments array?

	:param downloadDir: The directory to store the downloaded file(s)
	:param inputFile: The path to a file containing multiple URLS to download (see aria2c documentation)
	:param outputFile: When downloading a single file, if this is specified, it will be downloaded with the given name
	:return Returns the exit code of the aria2c call
	"""
	arguments = [
		Globals.ARIA_EXECUTABLE,
		"--file-allocation=none",
		'--continue=true',
		'--retry-wait=5',
		'-m 0', # max number of retries (0=unlimited). In some cases, like server rejects download, aria2c won't retry.
		'-x 8', # max connections to the same server
		'-s 8', # Split - Try to use N connections per each download item
		'-j 1', # max concurrent download items (eg number of separate urls which can be downloaded in parallel)
		# By default, if aria2c detects a file already exists with the same name, and is different size to the file
		# being downloaded (lets call this 'test.zip'), it will save to a different name ('test.2.zip', 'test.3.zip' etc)
		# This option prevents this from happening. Continuing existing downloads where the file size is the same is still supported.
		'--auto-file-renaming=false',
		# By default, aria2c will just error out if auto-renaming is disabled. Enabling this option allows aria2c to overwrite existing files,
		# if they cannot be continued (by the --continue argument)
		'--allow-overwrite=true',
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

def sevenZipExtract(archive_path, outputDir=None):
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
	return runProcessOutputToTempFile(arguments, sevenZipMode=True)

def tryGetRemoteNews(newsName):
	"""
	:param changelogName: the name of the changelog to retrieve, without file extension
	There should be one for each mod, and one called 'news' for the index.html page
	:return:
	"""
	localPath = 'news/' + newsName + '.md'
	url = Globals.githubMasterBaseURL + 'news/' + quote(newsName) + '.md'
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

def getModList(jsonURL):
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

	tmpdir = None
	try:
		if jsonURL[0:4] == "http":
			if not SSL_VERSION_IS_OLD:
				file = urlopen(Request(jsonURL, headers={"User-Agent": ""}))
			else:
				tmpdir = tempfile.mkdtemp()
				if aria(url=jsonURL, downloadDir=tmpdir, outputFile="info.json") != 0:
					errorHandler(Exception("ERROR - could not download modList [{}]. Installation Stopped"))

				file = io.open(os.path.join(tmpdir, "info.json"), "r", encoding='utf-8')
		else:
			file = io.open(jsonURL, "r", encoding='utf-8')
	except HTTPError as error:
		errorHandler(error)

	info = json.load(file, encoding='utf-8')
	file.close()
	if tmpdir:
		shutil.rmtree(tmpdir)
	try:
		version = info["version"]
		if version > Globals.JSON_VERSION:
			printErrorMessage("Your installer is out of date.")
			printErrorMessage("Please download the latest version of the installer and try again.")
			print("\nYour installer is compatible with mod listings up to version {} but the latest listing is version {}".format(Globals.JSON_VERSION, version))
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

def extractOrCopyFile(filename, sourceFolder, destinationFolder, copiedOutputFileName=None):
	makeDirsExistOK(destinationFolder)
	sourcePath = os.path.join(sourceFolder, filename)

	if '.7z' in filename.lower() or '.zip' in filename.lower():
		if sevenZipExtract(sourcePath, outputDir=destinationFolder) != 0:
			raise Exception("ERROR - could not extract [{}]. Installation Stopped".format(sourcePath))

	else:
		try:
			shutil.copy(sourcePath, os.path.join(destinationFolder, copiedOutputFileName if copiedOutputFileName else filename))
		except shutil.SameFileError:
			print("Source and Destination are the same [{}]. No action taken.".format(sourcePath))

def prettyPrintFileSize(fileSizeBytes):
	#type: (int) -> str

	if fileSizeBytes >= 1e9:
		return "{:.2f}".format(fileSizeBytes / 1e9).strip('0').strip('.') + ' GB'
	elif fileSizeBytes >= 1e6:
		return "{:.2f}".format(fileSizeBytes / 1e6).strip('0').strip('.') + ' MB'
	else:
		return "{:.2f}".format(fileSizeBytes / 1e3).strip('0').strip('.') + ' KB'

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
	class ExtractableItem:
		def __init__(self, filename, length, destinationPath, fromMetaLink):
			self.filename = filename
			self.length = length
			self.destinationPath = os.path.normpath(destinationPath)
			self.fromMetaLink = fromMetaLink

		def __repr__(self):
			return '[{} ({})] to [{}] {}'.format(self.filename, prettyPrintFileSize(self.length), self.destinationPath, "(metalink)" if self.fromMetaLink else "")

	def __init__(self, modFileList, downloadTempDir, extractionDir, downloadProgressAmount=45, extractionProgressAmount=45):
		# type: ([gameScanner.ModFile], str, str, int, int) -> None
		self.modFileList = modFileList
		self.downloadTempDir = downloadTempDir
		self.defaultExtractionDir = extractionDir
		self.downloadAndExtractionListsBuilt = False

		# These variables indicate how much download and extract should count towards the total reported progress
		self.downloadProgressAmount = downloadProgressAmount
		self.extractionProgressAmount = extractionProgressAmount

		self.downloadList = [] # type: List[str]
		self.extractList = [] # type: List[DownloaderAndExtractor.ExtractableItem]

	def buildDownloadAndExtractionList(self):
		"""
		This function fills in the self.downloadList and self.extractList lists, based on the self.modFileList
		If there are existing values in the self.downloadList or self.extractList, they are retained
		:return:
		"""
		commandLineParser.printSeventhModStatusUpdate(1, "Querying URLs to be Downloaded")
		for i, file in enumerate(self.modFileList):
			print("Querying URL: [{}]".format(file.url))
			self.downloadList.append(file.url)
			self.extractList.extend(
				DownloaderAndExtractor.getExtractableItem(url=file.url, extractionDir=self.defaultExtractionDir)
			)

		self.downloadAndExtractionListsBuilt = True

	def download(self):
		if not self.downloadAndExtractionListsBuilt:
			self.buildDownloadAndExtractionList()

		# download all urls to the download temp folder
		makeDirsExistOK(self.downloadTempDir)
		makeDirsExistOK(self.defaultExtractionDir)

		totalDownloadSize = self.totalDownloadSize()
		for i, url in enumerate(self.downloadList):
			overallPercentage = int(i*self.downloadProgressAmount/len(self.downloadList))
			commandLineParser.printSeventhModStatusUpdate(overallPercentage, "Downloading: {} (total) DL Folder: [{}] URL: [{}]"
			                                              .format(prettyPrintFileSize(totalDownloadSize), self.downloadTempDir, url))
			if aria(self.downloadTempDir, url=url, followMetaLink=DownloaderAndExtractor.__urlIsMetalink(url)) != 0:
				raise Exception("ERROR - could not download [{}]. Installation Stopped".format(url))

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
		self.downloadList.append(url)
		self.extractList.extend(DownloaderAndExtractor.getExtractableItem(url=url, extractionDir=extractionDir))

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
				fromMetaLink=True) for filename, length in metalinkFilenames]
		else:
			filename, length = DownloaderAndExtractor.__getFilenameFromURL(url)
			return [DownloaderAndExtractor.ExtractableItem(
				filename=filename,
				length=length,
				destinationPath=extractionDir,
				fromMetaLink=False)]

	@staticmethod
	def __urlIsMetalink(url):
		name, ext = os.path.splitext(urlparse(url).path)
		return ext == '.meta4' or ext == '.metalink'

	@staticmethod
	def __getFilenameFromURL(url):
		# type: (str) -> Tuple[str, int]
		"""
		Returns the filename of the file at the given URL, and it's file size.
		If the file size cannot be retrieved, returns a file size of 0
		:param url: The url of a file or a url which will eventually redirect to a file
		:return: A tuple of (filename, filesize) of the file pointed by the url
		"""

		# It's not a huge deal if the filename download is insecure (the actual download is done with Aria)
		if SSL_VERSION_IS_OLD and url[0:5] == "https":
			url = "http" + url[5:]

		# if the url has a contentDisposition header, use that instead
		httpResponse = urlopen(Request(url, headers={"User-Agent": ""}))
		contentDisposition = None
		try:
			contentDisposition = httpResponse.getheader("Content-Disposition")  # python 3
			lengthString = httpResponse.getheader('Content-Length')
		except AttributeError:
			contentDisposition = httpResponse.info().getheader("Content-Disposition")  # python 2
			lengthString = httpResponse.info().getheader('Content-Length')

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
			filename = os.path.basename(urlparse(httpResponse.url).path)

		# default filename is derived from original URL
		if filename is None:
			filename = os.path.basename(urlparse(url).path)


		return filename, length

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
		print("Free Disk Space query failed - probably using Python 2")
		pass

	freeSpaceAdvisoryString = "Install requires approximately {} of free disk space".format(recommendedFreeSpaceString)
	haveEnoughFreeSpace = None

	if free_space is not None:
		freeSpaceString = prettyPrintFileSize(free_space)
		if free_space < recommendedFreeSpaceBytes:
			freeSpaceAdvisoryString = "WARNING: You might not have enough free disk space! " \
			                          "(have {}, need {})".format(freeSpaceString, recommendedFreeSpaceString)
			haveEnoughFreeSpace = False
		else:
			freeSpaceAdvisoryString = "You have enough free disk space (have {}, need {})".format(freeSpaceString,
			                                                                                      recommendedFreeSpaceString)
			haveEnoughFreeSpace = True

	return haveEnoughFreeSpace, freeSpaceAdvisoryString
