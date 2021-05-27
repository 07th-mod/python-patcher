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
	from html.parser import HTMLParser
except:
	from HTMLParser import HTMLParser

try:
	from typing import Optional, List, Tuple, Dict, Callable, Any
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
	JSON_VERSION = 11

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

	# This variable force installation of mod assets from another operating system
	# Should be either "windows", "linux", or "mac" as per above OS_STRING values
	FORCE_ASSET_OS_STRING = None

	ARIA_EXECUTABLE = None
	SEVEN_ZIP_EXECUTABLE = None
	CURL_EXECUTABLE = None # Not required, but if available will be used to download filenames on systems with old SSL versions

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

	PERMISSON_DENIED_ERROR_MESSAGE = "Permission error: See our installer wiki FAQ about this error at https://07th-mod.com/wiki/Installer/faq/#extraction-stage-fails-i-get-an-acess-denied-error-when-overwriting-files"

	CA_CERT_PATH = None
	URLOPEN_IS_BROKEN = False

	NATIVE_LAUNCHER_PATH = None

	GIT_TAG = None
	"""The git tag associated with this installer release. Can be None if installer run directly from source"""
	BUILD_DATE = None
	"""The date this installer was built. Can be None if installer run directly from source"""
	INSTALLER_IS_LATEST = (None, "")
	"""True if installer is latest released version, False if installer is not latest, None if can't determine if is latest
	The second part of the tuple is set to a descriptive message explaining the version status"""

	@staticmethod
	def scanForCURL():
		# On Windows 10, default to system CURL (which uses Windows's certificates)
		# If not available, use the curl bundled with the installer, which uses included cert file 'curl-ca-bundle.crt'
		Globals.CURL_EXECUTABLE = findWorkingExecutablePath(["curl", "curl_bundled"], ["-I", "https://07th-mod.com/"])

	@staticmethod
	def scanForAria():
		ariaSearchPaths = ["./aria2c", "./.aria2c", "aria2c"]
		Globals.ARIA_EXECUTABLE = findWorkingExecutablePath(ariaSearchPaths, ['https://07th-mod.com/', '--dry-run=true'])

		if Globals.ARIA_EXECUTABLE is None:
			print("\nWARNING: aria2 failed to download 07th-mod website. Using fallback detection method.")
			Globals.ARIA_EXECUTABLE = findWorkingExecutablePath(ariaSearchPaths, ['-h'])

		if Globals.ARIA_EXECUTABLE is None:
			# TODO: automatically download and install dependencies
			raise Exception("ERROR: aria2c executable not found (aria2c). Please install the dependencies for your platform.")
		else:
			print("Found aria2c at [{}]".format(Globals.ARIA_EXECUTABLE))

	@staticmethod
	def scanForSevenZip():
		Globals.SEVEN_ZIP_EXECUTABLE = findWorkingExecutablePath(["./7za64", "./7za", "./.7za", "7za", "./7z", "7z"], ['-h'])
		if Globals.SEVEN_ZIP_EXECUTABLE is None:
			# TODO: automatically download and install dependencies
			raise Exception("ERROR: 7-zip executable not found (7za or 7z). Please install the dependencies for your platform.")
		else:
			print("Found 7-zip at [{}]".format(Globals.SEVEN_ZIP_EXECUTABLE))

	@staticmethod
	def scanForExecutables():
		print("Validating Executables...")
		startAndJoinThreads(
			[makeThread(t) for t in [Globals.scanForCURL, Globals.scanForAria, Globals.scanForSevenZip]]
		)

	@staticmethod
	def macUnQuarantineExecutable(path):
		errorString = None
		try:
			exit_code = subprocess.call(["xattr", "-d", "com.apple.quarantine", path])
			if exit_code != 0:
				errorString = "xattr returned exit code {}".format(exit_code)
		except Exception as e:
			errorString = str(e)

		if errorString is not None:
			print("""Error removing quarantine: {}
You can try manually running [{}] once so the installer can use the file.""".format(errorString, path))

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
							try:
								cacheDownloadSizes.generateCachedDownloadSizes()
							except:
								msg = "Failed to regenerate cachedDownloadSizes.json. Please check installer log for 'Could not query URL' to determine which URL in installData.json failed to load, and for other errors."
								print("DEVELOPER: " + msg)
								try:
									from tkinter import messagebox
									messagebox.showerror("Cached Download Regeneration Failure", msg)
								except:
									pass
							break
				else:
					print("DEVELOPER: skipping cachedDownloadSizes.json regeneration as you are running Python 2. Please use Python 3 to regenerate the download size cache.")

		except Exception:
			print("Developer ERROR: Failed to read URL File Size Lookup Table")
			traceback.print_exc()

	@staticmethod
	def getBuildInfo():
		try:
			with open('build_info.json', 'r') as build_info_file:
				buildInfo = json.load(build_info_file)
				Globals.BUILD_DATE = buildInfo['build_date']
				Globals.GIT_TAG = buildInfo['git_tag']
				Globals.BUILD_INFO = "Git Tag: {}\nBuild Date:{}".format(Globals.GIT_TAG, Globals.BUILD_DATE)

		except Exception as e:
			Globals.BUILD_INFO = None
			print("Failed to retrieve build info: {}".format(e))
			traceback.print_exc()

	@staticmethod
	def loadInstallerLatestStatus():
		try:
			latestVersion = getLatestInstallerVersion()
			currentVersion = Globals.GIT_TAG

			if currentVersion is None or latestVersion is None:
				Globals.INSTALLER_IS_LATEST = (None, "WARNING: Version status unknown. Current: {} Latest: {}".format(currentVersion, latestVersion))
			elif latestVersion == currentVersion:
				Globals.INSTALLER_IS_LATEST = (True, "Installer is latest version: {}".format(currentVersion))
			else:
				Globals.INSTALLER_IS_LATEST = (False, "WARNING: This installer [{}] is outdated. Latest installer is [{}]".format(currentVersion, latestVersion))
		except Exception as e:
			Globals.INSTALLER_IS_LATEST = (None, "WARNING: Version status unknown")
			print("Failed to determine whether installer was latest version: {}".format(e))
			traceback.print_exc()

		print("> {}".format(Globals.INSTALLER_IS_LATEST[1]))

	@staticmethod
	def scanCertLocation():
		if Globals.IS_LINUX:
			# List of cert locations from https://github.com/golang/go/blob/master/src/crypto/x509/root_linux.go
			for possibleCertLocation in [
				"/etc/ssl/certs/ca-certificates.crt",  # Debian/Ubuntu/Gentoo etc.
				"/etc/pki/tls/certs/ca-bundle.crt",  # Fedora/RHEL 6
				"/etc/ssl/ca-bundle.pem",  # OpenSUSE
				"/etc/pki/tls/cacert.pem",  # OpenELEC
				"/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem",  # CentOS/RHEL 7
				"/etc/ssl/cert.pem",  # Alpine Linux
			]:
				if os.path.exists(possibleCertLocation):
					Globals.CA_CERT_PATH = possibleCertLocation
					print("CA Cert - found at: {}".format(Globals.CA_CERT_PATH))
					return

		print("CA Cert - using default certificate")

# You can use the 'exist_ok' of python3 to do this already, but not in python 2
def makeDirsExistOK(directoryToMake):
	if os.path.exists(directoryToMake):
		return

	# Only return once the folder has actually been created
	for i in range(5):
		try:
			os.makedirs(directoryToMake)
		except Exception as e:
			print("Attempt {} to create {} failed: {}".format(i, directoryToMake, e))

		if os.path.exists(directoryToMake):
			return

		time.sleep(1)

	raise Exception("Couldn't create directory {}".format(directoryToMake))

def tryShowInFileBrowser(path):
	trySystemOpen(path, True)

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
	# drojf: Removed universal_newlines, to fix issues with non-windows locales breaking this part of the installer
	# see https://stackoverflow.com/questions/38181494/what-is-the-difference-between-using-universal-newlines-true-with-bufsize-1-an?rq=1
	# The default bufsize works fine on Windows (seems to be line buffered, or maybe the flush() works as expected on Windows)
	proc = subprocess.Popen(arguments, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

	def readUntilEOF(proc, fileLikeObject):
		stringBuffer = []
		while proc.poll() is None:
			try:
				fileLikeObject.flush()
				while True:
					if Globals.IS_PYTHON_2:
						character = fileLikeObject.read(1)
					else:
						character = fileLikeObject.read(1).decode(encoding='utf-8', errors='replace')

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
				print("Error in [runProcessOutputToTempFile()]: {}".format(traceback.format_exc()))
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

	if Globals.CA_CERT_PATH is not None:
		arguments.append("--ca-certificate=" + Globals.CA_CERT_PATH)

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
			errors.append("Unknown Error: {}. You may want to check our Installer FAQ: https://07th-mod.com/wiki/Higurashi/Higurashi-Part-1---Voice-and-Graphics-Patch/#installer-faq-and-troubleshooting or get help on our Discord Server: https://discord.gg/pf5VhF9".format(self.unknown_error_string))

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
	arguments = [Globals.SEVEN_ZIP_EXECUTABLE,
	             "t",
	             archive_path,
	             "-bso1",  # redirect standard Output messages to stdout
	             "-bsp1",  # redirect Progress update messages to stdout
	             "-bse2",  # redirect Error messages to stderr
	             ]
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
			with io.open(localPath, 'r', encoding='utf-8') as file:
				return file.read()
		else:
			return downloadFile(url, is_text=True)
	except HTTPError as error:
		return """The news [{}] couldn't be retrieved from [{}] the server.""".format(newsName, url)

def getDonationStatus():
	# type: () -> (Optional[str], Optional[str])
	"""
	:return: (months_remaining, funding_goal_percentage) as a tuple (can both be None if download or parsing failed)
	"""
	try:
		entirePage = downloadFile(r"https://07th-mod.com/wiki/", is_text=True)
	except HTTPError as error:
		return None, None

	class DonationHTMLParser(HTMLParser, object):
		def __init__(self):
			super(DonationHTMLParser, self).__init__()
			self.funding_goal_percentage = None
			self.months_remaining = None

		def handle_starttag(self, tag, attrs):
			if tag == "progress":
				for k, v in attrs:
					if k == 'value':
						self.funding_goal_percentage = v
					elif k == 'data-months-remaining':
						self.months_remaining = v

	parser = DonationHTMLParser()
	parser.feed(entirePage)

	return parser.months_remaining, parser.funding_goal_percentage

def getJSON(jsonURI, isURL):
	#type: (str, bool) -> (Dict, Exception)
	"""

	:param jsonURI: Path to a file or URL to download
	:param isURL: Specify whether the URI is for a URL or path
	:return: 
	"""
	tmpdir = None
	file = None
	try:
		if isURL:
			jsonString = downloadFile(jsonURI, is_text=True)
			info = json.loads(jsonString)
		else:
			file = io.open(jsonURI, "r", encoding='utf-8')
			info = json.load(file)
	except HTTPError as error:
		return None, error
	except Exception as anyError:
		return None, anyError
	finally:
		if file is not None:
			file.close()

	return info, None

def getModList(jsonURI, isURL):
	"""
	Gets the list of available mods from the 07th Mod server

	:return: A list of mod info objects
	:rtype: list[dict]
	"""
	info, exception = getJSON(jsonURI, isURL)
	if info is None:
		raise Exception("""------------------------------------------------------------------------
Error: Couldn't reach Github to download mod list! ({})

Please check the following:
- You have a working internet connection
- Check if you can manually download the following file ({})
- Check our Wiki for more solutions: https://www.07th-mod.com/wiki/Installer/faq/

Detailed Error: {}
------------------------------------------------------------------------""".format(jsonURI, jsonURI, exception))

	try:
		version = info["version"]
		if version > Globals.JSON_VERSION:
			printErrorMessage("Your installer is out of date.")
			printErrorMessage("Please download the latest version of the installer and try again.")
			raise Exception("""-------------------------------------------------------------------------------
Your installer is out of date.
Please download the latest version of the installer and try again.

Your installer is compatible with mod listings up to version {} but the latest listing is version {}
-------------------------------------------------------------------------------""".format(Globals.JSON_VERSION, version))
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

	root = ET.fromstring(downloadFile(url, is_text=True))

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

class DownloadAndVerifyError(Exception):
	def __init__(self, errorReason):
		# type: (str) -> None
		self.errorReason = errorReason  # type: str

	def __str__(self):
		return self.errorReason

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
			except Exception as e:
				print("Failed to load date modified file {}: {}".format(localDateModifiedControlPath, e))
				return None

		def _updateLocalDateModified(self, localDateModifiedControlPath):
			try:
				with io.open(localDateModifiedControlPath, "w", encoding='UTF-8') as f:
					f.write(self.remoteLastModified)
			except Exception as e:
				print("Failed to write date modified file {}: {}".format(localDateModifiedControlPath, e))

		def _tryDeleteOldDownloadAndAriaFile(self, downloadDir):
			oldDownloadPath = os.path.join(downloadDir, self.filename)
			try:
				if os.path.exists(oldDownloadPath):
					os.remove(oldDownloadPath)
				if os.path.exists(oldDownloadPath + ".aria2"):
					os.remove(oldDownloadPath + ".aria2")
			except Exception as e:
				print("ExtractableItem: Failed to delete {}: {}".format(oldDownloadPath, e))

	def __init__(self, modFileList, downloadTempDir, extractionDir, downloadProgressAmount=45, extractionProgressAmount=45, supressDownloadStatus=False):
		# type: (List[installConfiguration.ModFile], str, str, int, int, bool) -> None
		self.modFileList = modFileList
		self.downloadTempDir = downloadTempDir
		self.defaultExtractionDir = extractionDir
		self.downloadAndExtractionListsBuilt = False
		self.suppressDownloadStatus = supressDownloadStatus

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
		if not self.suppressDownloadStatus:
			commandLineParser.printSeventhModStatusUpdate(1, "Querying URLs to be Downloaded")
		for i, file in enumerate(self.modFileList):
			extractionDir = self.defaultExtractionDir
			if file.relativeExtractionPath is not None:
				extractionDir = os.path.join(self.defaultExtractionDir, file.relativeExtractionPath)

			self.addItemManually(file.url, extractionDir)

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
				if not self.suppressDownloadStatus:
					commandLineParser.printSeventhModStatusUpdate(overallPercentage, "Downloading: {} (total) DL Folder: [{}] URL: [{}] (Attempt: {}/{})"
					                                          .format(prettyPrintFileSize(totalDownloadSize), self.downloadTempDir, url, attempt + 1, DownloaderAndExtractor.MAX_DOWNLOAD_ATTEMPTS))
				if aria(self.downloadTempDir, url=url, followMetaLink=DownloaderAndExtractor.__urlIsMetalink(url)) != 0:
					print("ERROR - failed to download [{}]. Trying again in 3 seconds...".format(url))
					time.sleep(3)
					continue

				# If all extractables were valid, then we are finished with this download item
				# and can move on to the next one
				if not self.extractablesHasInvalidArchives(extractables):
					break
			else:
				# Too many attempts
				raise DownloadAndVerifyError("ERROR - Failed to download [{}] after {} attempts. Check aria2/7z in log for details. Installation Stopped".format(url, attempt + 1))

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

	def extract(self, remapPaths=lambda x,y: (x,y)):
		#type: (Callable[[str, str], Tuple[str, str]]) -> None
		"""
		This function does the following for each item downloaded earlier:
		- if the downloaded item is a .7z or .zip file, it is extracted to the destination folder
		- if the download item is any other file, it is copied to the destination folder.

		"remapPaths" argument:
		If provided, this function is used to remap the destination paths of the extracted files.
		The function should return a new destination folder/filename, where the files will be extracted to.

		:param remapPaths: This parameter is a function which takes two arguments, and returns a tuple:
		- arg1: the destination folder that the file will be extracted to
		- arg2: the destination filename that the file will be given
		- return: the new (destinationFolder, destinationFilename) as a tuple

		Note that if the file is an archive (.7z or .zip file), then you can only change the output folder
		(where it will be extracted to), not the output filename.
		"""
		if not self.downloadAndExtractionListsBuilt:
			self.buildDownloadAndExtractionList()

		# extract or copy all files from the download folder to the game directory
		for i, extractableItem in enumerate(self.extractList):
			overallPercentage = self.downloadProgressAmount + int(i*self.extractionProgressAmount/len(self.extractList))
			commandLineParser.printSeventhModStatusUpdate(overallPercentage, "Extracting {}".format(extractableItem))

			destinationFolder, destinationFileName = remapPaths(extractableItem.destinationPath, extractableItem.filename)

			extractOrCopyFile(extractableItem.filename,
			                  self.downloadTempDir,
			                  destinationFolder,
			                  destinationFileName)

	def addItemManually(self, url, extractionDir):
		"""
		Use this function to manually add a file or metalink to download and extract, with a custom extraction directory
		Items added by this function will be downloaded/extracted AFTER any already existing items in the download/extract list.
		:param url: The URL or metalink to download
		:param extractionDir: The folder where the file(s) will be extracted
		"""
		print("Querying URL: [{}]".format(url))
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

		def queryUsingCURL(queryUrl):
			if Globals.CURL_EXECUTABLE is None:
				raise Exception("URLOpen Metadata Query FAILED - No CURL executable available for fallback (URL [{}])".format(url))

			# On old SSL if we have curl use that instead
			with open(os.devnull, 'w') as os_devnull:
				# Get the header, the -X GET is required because the github download links return a 403 if you try to send a HEAD request
				headers = subprocess.check_output([Globals.CURL_EXECUTABLE, "-fILX", "GET", queryUrl],
				                                  stderr=os_devnull).decode("utf-8")
			# If there's redirects curl may print multiple headers with multiple content dispositions.  We want the last one
			contentDisposition = re.findall("Content-Disposition: (.+)", headers, re.IGNORECASE)
			contentDisposition = contentDisposition[-1].strip() if contentDisposition else None
			lengthString = re.findall("Content-Length: (.+)", headers, re.IGNORECASE)
			lengthString = lengthString[-1].strip() if lengthString else None
			remoteLastModified = re.findall("Last-Modified: (.+)", headers, re.IGNORECASE)
			remoteLastModified = remoteLastModified[-1].strip() if remoteLastModified else None
			responseURL = re.findall("Location: (.+)", headers, re.IGNORECASE)
			responseURL = responseURL[-1].strip() if responseURL else queryUrl

			return contentDisposition, remoteLastModified, responseURL, lengthString

		def queryUsingURLOpen(queryUrl):
			httpResponse = urlopen(Request(queryUrl, headers={"User-Agent": ""}))

			try:
				contentDisposition = httpResponse.getheader("Content-Disposition")  # python 3
				lengthString = httpResponse.getheader('Content-Length')
				remoteLastModified = httpResponse.getheader("Last-Modified")
			except AttributeError:
				# Python 2 handling: AttributeError causes below to be executed instead
				contentDisposition = httpResponse.info().getheader("Content-Disposition")
				if contentDisposition is not None:
					contentDisposition = contentDisposition.decode("utf-8")

				lengthString = httpResponse.info().getheader('Content-Length')
				if lengthString is not None:
					lengthString = lengthString.decode("utf-8")

				remoteLastModified = httpResponse.info().getheader("Last-Modified")
				if remoteLastModified is not None:
					remoteLastModified = remoteLastModified.decode("utf-8")

			responseURL = httpResponse.url

			return contentDisposition, remoteLastModified, responseURL, lengthString

		if Globals.URLOPEN_IS_BROKEN or (SSL_VERSION_IS_OLD and Globals.CURL_EXECUTABLE is not None):
			contentDisposition, remoteLastModified, responseURL, lengthString = queryUsingCURL(url)
		else:
			try:
				contentDisposition, remoteLastModified, responseURL, lengthString = queryUsingURLOpen(url)
			except:
				Globals.URLOPEN_IS_BROKEN = True
				print("Could not query URL {} using URLOpen! Falling back to CURL".format(url))
				traceback.print_exc()
				contentDisposition, remoteLastModified, responseURL, lengthString = queryUsingCURL(url)

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

	freeSpaceAdvisoryString = "Install requires approximately {} of free disk space at [{}] for extraction and temporary files.".format(recommendedFreeSpaceString, installPath)
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

def group_by(values, keyFunc):
	# type: (List, Callable[[Any], Any]) -> Dict
	"""
	This function groups 'values' according to the keyFunc.
	All values where keyFunc(value) is the same (called the 'key') will be grouped together.

	This function differs from itertools.groupby() in that it doesn't require the input be sorted.
	It will also preserve the order of the input values
	:return: A dict of the form keyFunc(value): List[Any], with one entry for each key paired with its grouped values
	"""
	# Don't use defaultdict as user will expect a regular dict returned
	grouped = {}

	for value in values:
		key = keyFunc(value)
		if key not in grouped:
			grouped[key] = []

		grouped[key].append(value)

	return grouped

def downloadFile(url, is_text):
	"""
	Downloads a file from the given URL.
	Will either return "bytes" if is_text = False, or a unicode string if is_text = True
	Raises an exception on error.

	:param url:
	:return:
	"""
	def downloadUsingURLOpen(download_url):
		file = urlopen(Request(download_url, headers={"User-Agent": ""}))
		data = file.read()
		file.close()
		return data

	def downloadUsingAria2c(download_url):
		# Download to a temporary file
		tempName = "temporary.tmp"

		tempDirectory = getInstallerTempDir()
		tempPath = os.path.join(tempDirectory, tempName)

		# Remove the file if it already exists, so the download does not fail
		removeFileWithCheck(tempPath)

		if aria(url=download_url, downloadDir=tempDirectory, outputFile=tempName) != 0:
			raise Exception("ERROR - could not download [{}] with aria2c".format(download_url))

		# Read out the temporary file to memory
		file = open(tempPath, 'rb')
		data = file.read()
		file.close()

		# Clean up by removing the file as it's no longer needed
		removeFileWithCheck(tempPath)
		removeFileWithCheck(tempDirectory, isEmptyFolder=True)

		return data

	try:
		if SSL_VERSION_IS_OLD or Globals.URLOPEN_IS_BROKEN:
			data = downloadUsingAria2c(url)
		else:
			data = downloadUsingURLOpen(url)
	except:
		traceback.print_exc()
		Globals.URLOPEN_IS_BROKEN = True
		data = downloadUsingAria2c(url)

	if is_text:
		data = data.decode('utf-8')

	return data

def makeThread(target):
	def _target():
		try:
			t.result = target()
		except BaseException as exc:
			t.failure = exc
	t = threading.Thread(target=_target, name=target.__name__)
	join = t.join
	def _join(timeout=None):
		join(timeout=timeout)
		print("Thread {} ".format(t.name), end='')
		if hasattr(t, "result"):
			print("finished successfully")
			return t.result
		else:
			print("failed")
			raise t.failure
	t.join = _join
	start = t.start
	def _start():
		print("Thread {} started".format(t.name))
		start()
	t.start = _start
	return t

def startAndJoinThreads(threads):
	# type: (list[threading.Thread]) -> ()
	for thread in threads:
		thread.start()

	for thread in threads:
		thread.join()

def getInstallerTempDir():
	"""Returns the path of a new, empty temporary directory. It will be located adjacent to the python script like:
	 `07th-mod_temp_dir/tmpva9f1qz7`
	 The callee is responsible for cleaning up and removing the directory afterwards."""
	common_temp_folder_path = "07th-mod_temp_dir"
	makeDirsExistOK(common_temp_folder_path)
	temp_folder_path = tempfile.mkdtemp(dir=common_temp_folder_path)

	return temp_folder_path

def removeFileWithCheck(path, isEmptyFolder=False, failOk=False):
	if not os.path.exists(path):
		return

	for i in range(5):
		try:
			if isEmptyFolder:
				os.rmdir(path)
			else:
				os.remove(path)
		except Exception as e:
			print("Attempt {} to remove {} failed: {}".format(i, path, e))

		if failOk or not os.path.exists(path):
			return

		time.sleep(1)

	raise Exception("Failed to remove file {}".format(path))


def getLatestInstallerVersion():
	""" Fetches latest installer version from Github, like "v1.1.68" """
	try:
		releases, error = getJSON('https://api.github.com/repos/07th-mod/python-patcher/releases?per_page=1', isURL=True)
		if error is not None:
			raise error

		if len(releases) == 0:
			print("getLatestInstallerVersion(): No releases found so can't check version")
			return None

		latest_release = releases[0]
		latest_release_tag = latest_release['tag_name']
		return latest_release_tag
	except Exception as e:
		print("getLatestInstallerVersion(): Failed to fetch latest release info: {}".format(e))
		return None


def ensureUnicodeOrStr(text):
	"""Converts 'text' to unicode or str type if it is bytes, leaves it alone otherwise
	Note that 'str' is treated as bytes on Python 2, that is:
	Python 2: 'bytes' or 'str' -> unicode string
	Python 3: 'bytes' -> 'str'"""
	if isinstance(text, bytes):
		return text.decode('utf-8')
	else:
		return text
