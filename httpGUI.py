# see https://blog.anvileight.com/posts/simple-python-http-server/
from __future__ import print_function, unicode_literals

import itertools
import os
import json
import re
import sys
import time
import zipfile
import subprocess

import common
import traceback
import threading

import fileVersionManagement
import gameScanner
import commandLineParser
import logger
import installConfiguration
import collections

try:
	import urlparse
except ImportError:
	import urllib.parse as urlparse

try:
	import http.server as server
	from http.server import HTTPServer
except ImportError:
	import SimpleHTTPServer as server
	from BaseHTTPServer import HTTPServer

#tk is only required for the below  _askGameExeAndValidate function
try:
	from tkinter import Tk
	from tkinter import filedialog
except ImportError:
	try:
		from Tkinter import Tk
		import tkFileDialog as filedialog
	except ImportError:
		pass

try:
	from typing import List, Optional, Dict, Tuple
except ImportError:
	pass # Just needed for pycharm comments

class ExtractableItemCache:
	def __init__(self):
		self.cache = {}
		self.lock = threading.Lock()

	def cacheURLs(self, urls):
		# type: (List[str]) -> ()

		self.lock.acquire()
		try:
			# Get all the URLS not in the cache
			urlsToQuery = [url for url in urls if url not in self.cache]

			try:
				# Query URLs in parallel on Python 3
				import concurrent.futures

				def query(url):
					return url, common.DownloaderAndExtractor.getExtractableItem(url, '.')

				with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
					for url, extractableItemList in executor.map(query, urlsToQuery):
						self.cache[url] = extractableItemList

			except ImportError:
				# Fallback to querying in serial on Python 2
				for url in urlsToQuery:
					self.cache[url] = common.DownloaderAndExtractor.getExtractableItem(url, '.')
		finally:
			self.lock.release()

	def get(self, url):
		# type: (str) -> List[common.DownloaderAndExtractor.ExtractableItem]
		return self.cache[url]

extractableItemCache = ExtractableItemCache()

collapseWhiteSpaceRegex = re.compile(r"[\s\b]+")
def _TKAskPath(subMod):
	try:
		Tk
	except NameError:
		raise Exception("Tk is not installed on this system. NOTE: You can still manually copy and paste the game path into the 'Currently Chosen Path' box.")

	# TODO: on 2.7 you can use .withdraw on the root window, but on python 3 it prevents the filedialog from showing!
	# TODO: for now, put up with the root window showing when choosing path manually
	if common.Globals.IS_MAC:
		return common.ensureUnicodeOrStr(subprocess.check_output(["osascript", "-e",  "POSIX path of (choose file of type {\"com.apple.application\"} with prompt \"Please choose a game to install to\")"]).strip())
	root = Tk()

	# this creates the default option, which allows you to select all identifiers and any extras specified here.
	extensionList = ["com.apple.application"] + subMod.identifiers
	fileList = [("Game Executable", x) for x in extensionList]
	fileList.append(("Any In Game Folder", "*.*"))

	# returns empty string if user didn't select any file or folder. If a file is selected, convert it to the parent folder
	installFolder = filedialog.askopenfilename(filetypes=fileList)

	root.destroy()

	return installFolder

def askPathWindowsLauncher(subMod):
	nativeLauncherPath = common.Globals.NATIVE_LAUNCHER_PATH
	if nativeLauncherPath is None:
		raise Exception("askPathWindowsLauncher error: launcher path not set! aborting this method")

	nativeLauncherPathAbs = os.path.abspath(nativeLauncherPath)
	print("askPathWindowsLauncher: Will use launcher exe at [{}]...".format(nativeLauncherPathAbs))
	if not os.path.exists(nativeLauncherPath):
		raise Exception("Failed to open file chooser at [{}].\n\nPlease manually copy and paste the game path into the 'Currently Chosen Path' box.".format(nativeLauncherPathAbs))

	args = [
		nativeLauncherPath, "open",
		"Game Executable", ";".join(subMod.identifiers),
		"Any In Game Folder", "*.*"
	]

	print("askPathWindowsLauncher: Executing {}".format(args))
	# If there is an error or the program returns non-zero exit code,
	# this will throw an exception, which will be shown to the user
	# If the user pressed "Cancel", returns the empty string.
	return subprocess.check_output(args).decode("utf-8")


# Powershell script based on this example:
# https://4sysops.com/archives/how-to-create-an-open-file-folder-dialog-box-with-powershell/
# All properties of the OpenFileDialog object are also shown on that page
# Filter strings are described here:
# https://docs.microsoft.com/en-us/dotnet/api/system.windows.forms.filedialog.filter?view=netcore-3.1
def askPathWindowsPowerShell(subMod):
	filter_list = 'Game Executable|{}|Any In Game Folder (*.*)|*.*'.format(";".join(subMod.identifiers))

	command = [
		'powershell',
		'-noprofile',
		'-command',
		r"""Add-Type -AssemblyName System.Windows.Forms;
		$FileBrowser = New-Object System.Windows.Forms.OpenFileDialog -Property @{
			InitialDirectory = [Environment]::GetFolderPath('Desktop')
			Filter = '<<<FILTERLIST>>>'
			Title = 'Select a game exe like <<<EXE_LIST>>>'
		};
		$null = $FileBrowser.ShowDialog();
		Write-Output $FileBrowser.FileName;
		""".replace("<<<FILTERLIST>>>", filter_list).replace('<<<EXE_LIST>>>', " or ".join(subMod.identifiers))
	]

	print("askPathWindowsPowerShell: Executing [{}]".format(''.join(command)))
	path = subprocess.check_output(command).decode("utf-8").strip('\r\n')
	print("askPathWindowsPowerShell: Got result [{}]".format(path))

	return path

def askPathWindows(subMod):
	try:
		return askPathWindowsLauncher(subMod)
	except Exception as e:
		print("Failed to use Windows Launcher to open file chooser {}".format(e))
		return askPathWindowsPowerShell(subMod)

def askPath(subMod):
	if common.Globals.IS_WINDOWS:
		return askPathWindows(subMod)
	else:
		return _TKAskPath(subMod)

def _makeJSONResponse(responseType, responseDataJson):
	# type: (str, object) -> str
	return json.dumps({
		'responseType': responseType,
		'responseData': responseDataJson,
	})


def _decodeJSONRequest(jsonString):
	# type: (str) -> (str, object)
	json_compatible_dict = json.loads(common.ensureUnicodeOrStr(jsonString))
	return (json_compatible_dict['requestType'], json_compatible_dict['requestData'])

def _getSevenZipSubTaskDescription(message):
	# type: (str) -> Optional[str]
	# Look for a 7z line showing the file count and filename: "404 - big\bmp\background\cg\dragon_a.png"
	# Sometimes 7z emits just the file count without the filename (will appear as a line with a number on it)
	sevenZipMessage = commandLineParser.tryGetSevenZipFilecountAndFileNameString(message)
	if sevenZipMessage:
		return "Extracting - {}".format(sevenZipMessage)

	sevenZipFileCount = commandLineParser.tryGetSevenZipFileCount(message)
	if sevenZipFileCount:
		return "Extracting - {}".format(sevenZipFileCount)

	sevenZipExtractionStartedString = commandLineParser.tryGetSevenZipExtractionStarted(message)
	if sevenZipExtractionStartedString:
		return sevenZipExtractionStartedString

	sevenZipTestArchiveString = commandLineParser.tryGetSevenZipTestArchive(message)
	if sevenZipTestArchiveString:
		return sevenZipTestArchiveString

	return None

def _loggerMessageToStatusDict(message):
	# Search for an update like "<<< Status: 45% [[Extracting Umineko-Graphics-1080p.7z]] >>>"
	status = commandLineParser.tryGetOverallStatus(message)
	if status:
		return {
			"overallPercentage": status.overallPercentage,
			"overallTaskDescription": "{}".format(status.currentTask),
		}

	# Search the line for parts of a aria status update: "[#7f0d78 27MiB/910MiB(3%) CN:8 DL:4.2MiB ETA:3m27s]"
	# Searches for "#7f0d78 27MiB/910MiB(3%)" and also "ETA:3m27s" separately
	status = commandLineParser.tryGetAriaStatusUpdate(message)
	if status:
		progressType = "Verifying" if 'checksum' in message.lower() else "Downloading"
		return {
			"subTaskPercentage": status.percentCompleted,
			"subTaskDescription": "{} - [{}]) CN: {} DL: {} ETA: {}".format(progressType, status.amountCompletedString, status.numConnections, status.speed, status.ETAString),
		}

	sevenZipMessageAndPercent = {}
	subTaskDescription =  _getSevenZipSubTaskDescription(message)
	if subTaskDescription:
		sevenZipMessageAndPercent['subTaskDescription'] = subTaskDescription

	# Look for a line with just a percent on it (eg 51%)
	sevenZipPercent = commandLineParser.tryGetSevenZipPercent(message)
	if sevenZipPercent:
		sevenZipMessageAndPercent['subTaskPercentage'] = sevenZipPercent

	if sevenZipMessageAndPercent:
		if 'subTaskDescription' in sevenZipMessageAndPercent:
			sevenZipMessageAndPercent['subTaskDescription'] = collapseWhiteSpaceRegex.sub(" ", sevenZipMessageAndPercent['subTaskDescription'])

		return sevenZipMessageAndPercent

	# This variable represents the final message which will be displayed on the web console
	displayedMessage = message

	# Check for a checksum error message (when using metalinks)
	if commandLineParser.tryGetAriaChecksumError(message) is not None:
		ignoreMessage = "--- You can IGNORE this checksum error unless you repeatedly get it for the same file. ---\n"
		displayedMessage = "{}{}{}".format(ignoreMessage, message, ignoreMessage)

	# if the message is not a aria or 7zip message, just show it in the gui log window
	return {"msg": displayedMessage}

def start_server(working_directory, post_handlers, installRunningLock, serverStartedCallback=lambda _: None):
	# type: (str, dict, threading.RLock, function) -> None
	"""
	Starts a http server which handles POST requests with callbacks by the given 'post_handlers' argument.

	:param working_directory: the directory to serve files from
	:param post_handlers:
		post_handlers is a dictionary of { str : function }
		the string represents the 'path/url' that the post request was sent to
		the function represents the action to take when the post request with the specified 'path/url' is received:
		- the fn takes one argument, which is the data/body of the post request, as a UTF-8 string
		- the fn should return the response in the form of a UTF-8 string

	:return: None
	:exception: see serve_forever() of the SimpleHTTPRequestHandler class. In particular, if you try to run two
				instances of this server on the same computer, you will get a:
				"OSError: [WinError 10048] Only one usage of each socket address is normally permitted"
	"""
	class CustomHandler(server.SimpleHTTPRequestHandler):
		"""
		This class inherits from SimpleHTTPRequestHandler. It acts as a webserver, which serves the files in the
		working_directory variable captured from the outer scope. On POST requests, it executes the
		function in the post_handlers dict corresponding to the POST address. The following changes were also made:
		- The subdirectory working_directory is served, instead of the current working directory
		- Trying to list a directory gives a 404 instead
		- All returned files have caching disabled
		- If an exception occurs while handling a request, the exception is passed to the browser
		"""
		def list_directory(self, path):
			""" This override function always returns a 404 when a directory listing is requested """
			self.send_error(404, "No permission to list directory")
			return None

		def send_head(self):
			"""
			Copy and pasted from  SimpleHTTPRequestHandler class because it's difficult
			to alter the headers without modifying the function directly

			Common code for GET and HEAD commands.

			This sends the response code and MIME headers.

			Return value is either a file object (which has to be copied
			to the outputfile by the caller unless the command was HEAD,
			and must be closed by the caller under all circumstances), or
			None, in which case the caller has nothing further to do.

			"""
			originalPath = self.translate_path(self.path)
			# --------- THE FOLLOWING WAS ADDED ---------
			# Python 3 has the ability to change web directory built-in, but Python 2 does not.
			relativePath = os.path.relpath(originalPath, os.getcwd())
			path = os.path.join(working_directory, relativePath) # working_directory is captured from outer scope!
			logger.printNoTerminal('Browser requested [{}], Trying to deliver [{}]'.format(self.path, path))
			# --------- END ADDED SECTION ---------
			f = None
			if os.path.isdir(path):
				parts = urlparse.urlsplit(self.path)
				if not parts.path.endswith('/'):
					# redirect browser - doing basically what apache does
					self.send_response(301)
					new_parts = (parts[0], parts[1], parts[2] + '/',
					             parts[3], parts[4])
					new_url = urlparse.urlunsplit(new_parts)
					self.send_header("Location", new_url)
					self.end_headers()
					return None
				for index in "index.html", "index.htm":
					index = os.path.join(path, index)
					if os.path.exists(index):
						path = index
						break
				else:
					return self.list_directory(path)
			ctype = self.guess_type(path)
			try:
				# Always read in binary mode. Opening files in text mode may cause
				# newline translations, making the actual size of the content
				# transmitted *less* than the content-length!
				f = open(path, 'rb')
			except IOError:
				self.send_error(404, "File not found")
				logger.printNoTerminal('404 Error: Cant deliver [{}] - file not found!\n'.format(path))
				return None
			try:
				self.send_response(200)
				self.send_header("Content-type", ctype)
				fs = os.fstat(f.fileno())
				self.send_header("Content-Length", str(fs[6]))
				self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
				# --------- THE FOLLOWING WAS ADDED ---------
				self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
				self.send_header('Pragma', 'no-cache')
				self.send_header('Expires', '0')
				# --------- END ADDED SECTION ---------
				self.end_headers()
				return f
			except:
				f.close()
				raise

		# Suppress log requests - use own logging. Errors logged with "log_error" will still be printed.
		def log_request(self, code='-', size='-'):
			pass

		def do_POST(self):
			content_length = int(self.headers['Content-Length'])
			body_as_string = self.rfile.read(content_length).decode('utf-8')

			path_without_slash = self.path.lstrip('/')

			try:
				response_function = post_handlers[path_without_slash]
				try:
					response_string = response_function(body_as_string)
				except:
					errorMessage = traceback.format_exc()
					response = 'Exception @ POSTPath: [{}] Data: [{}]\n\n{}'.format(path_without_slash, body_as_string, errorMessage)
					response_string = _makeJSONResponse('error', response)
					traceback.print_exc()
			except KeyError:
				response = 'Error @ POSTPath: [{}] Data: [{}]'.format(path_without_slash, body_as_string)
				print(response)
				response_string = _makeJSONResponse('error', response)

			# TODO: decide to keep or remove caching. Leave in for development.
			# Add headers to prevent caching (of ALL files)
			# See: https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cache-Control#Preventing_caching
			# Only 'Cache-Control' is required, but the other two aid in backwards compatibility
			self.send_response(200)
			self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
			self.send_header('Pragma', 'no-cache')
			self.send_header('Expires', '0')
			# For now, assume all data sent back is JSON
			self.send_header('Content-Type', 'application/json')
			self.end_headers()
			try:
				self.wfile.write(response_string.encode('utf-8'))
			except ConnectionAbortedError:
				print("Info: Browser aborted a connection - probably not a problem")

	# Prefer to use ThreadingHTTPServer, as some web browsers will deadlock if the server can only
	# handle one connection at a time:
	# > This class is identical to HTTPServer but uses threads to handle requests by using the ThreadingMixIn.
	# > This is useful to handle web browsers pre-opening sockets, on which HTTPServer would wait indefinitely.
	if sys.version_info >= (3, 7):
		import http
		httpServerType = http.server.ThreadingHTTPServer
	else:
		httpServerType = HTTPServer
		print('WARNING: Python version < 3.7 found - you may need to refresh the web GUI if it does not load, on Chrome and other browsers!')

	# The default HTTPServer allows multiple servers on the same address without error
	# we would prefer for an error to be raised, so you know if you had multiple copies of the installer open at once
	class HTTPServerNoReuse(httpServerType):
		allow_reuse_address = 0

	# This program is only intended to be used on a loopback (non-public facing) interface.
	# Do not modify the INTERFACE_IP variable.
	# Using Port '0' lets the OS choose an unused port
	error = Exception("Developer: Please define at last one port in the port list")
	for port in [8000, 8080, 8081, 8082, 8083, 8084, 8085, 8086, 8087, 8088, 8089, 8090, 0]:
		try:
			httpd = HTTPServerNoReuse(("127.0.0.1", port), CustomHandler)
			break
		except Exception as e:
			error = e
			print("Couldn't open server on port {}: {}\n".format(port, e))
	else:
		raise error

	# Spawn a thread to cause a shutdown of the server if lock is released
	def shutdownThread():
		print("Shutdown thread started")
		installRunningLock.acquire()
		print("Lock released - initiating shutdown")
		httpd.shutdown()

	threading.Thread(target=shutdownThread).start()

	# note: calling the http server constructor will immediately start listening for connections,
	# however it won't give a response until "serve_forever()" is called. This allows running the
	# serverStartedCallback() before we block by calling serve_forever()
	serverStartedCallback(httpd)
	httpd.serve_forever()

def modOptionsToWebFormat(modOptions):
	# type: (List[installConfiguration.ModOption]) -> List[Dict]
	"""
	Returns a list of dicts of the following format, to be used in the web interface:
	[{
		'name': str - name of the group
		'radio': List[{'name': str, 'id': str , 'description': str}] - a list of options to be displayed. the id is the unique id of each option
		'checkBox': List[{'name': str, 'id': str, 'description': str}] - a list of options to be displayed. the id is the unique id of each option
		'selectedCheckBoxes': List[str] - Sent to web interface as the empty list. The web interface should fill this with checkbox IDs which have been ticked.
		'selectedRadio': Optional[str] - Sent to web interface as 'None'. The web interface should set this to the ID of the radio button which has been selected
	}]

	:param modOptions: List[modOption] - a list of mod options to be converted to web format
	:return: a list of dicts in the above format
	"""
	def convertOptionToHTTPFormat(opt):
		return {'name': opt.name, 'id': opt.id, 'description': opt.description}

	httpFormattedOptions = []

	# Group mod options by name, while preserving order
	modOptionsGroupedByGroupName = collections.OrderedDict()
	for modOption in modOptions:
		if modOption.group in modOptionsGroupedByGroupName:
			modOptionsGroupedByGroupName[modOption.group].append(modOption)
		else:
			modOptionsGroupedByGroupName[modOption.group] = [modOption]

	# Convert the grouped options to a format the web-based frontend can use
	for groupName, groupOptions in modOptionsGroupedByGroupName.items():
		radioOptions = [convertOptionToHTTPFormat(o) for o in groupOptions if o.isRadio]
		checkBoxOptions = [convertOptionToHTTPFormat(o) for o in groupOptions if not o.isRadio]
		# Get the ids of all the checkboxes which are selected
		selectedCheckBoxes = [o.id for o in groupOptions if not o.isRadio and o.value]

		# Get the ids of all the radios which have been selected (which should only ever be one or zero),
		# then take the first one
		# The ID is of the form "BGM Options-Old BGM" - see definition of ModOption
		selectedRadio = [o.id for o in groupOptions if o.isRadio and o.value]
		if selectedRadio:
			selectedRadio = selectedRadio[0]
		else:
			selectedRadio = None

		httpFormattedOptions.append({
			'name': groupName,
			'radio': radioOptions,
			'checkBox': checkBoxOptions,
			# these two variables are provided to be filled in by the webpage.
			'selectedCheckBoxes': selectedCheckBoxes,
			'selectedRadio': selectedRadio,
		})

	return httpFormattedOptions

def updateModOptionsFromWebFormat(modOptionsToUpdate, webFormatModOptions, currentSubModFamily, allSubModConfigs):
	#type: (List[installConfiguration.ModOption], List[Dict], str, List[installConfiguration.SubModConfig]) -> None

	modOptions = dict((modOption.id, modOption) for modOption in modOptionsToUpdate)
	# Clear all mod options to "off" before enabling the ones which the user set.
	for modOption in modOptions.values():
		modOption.value = False

	for modOptionGroup in webFormatModOptions:
		selectedRadioID = modOptionGroup['selectedRadio']
		if selectedRadioID is not None:
			modOptions[selectedRadioID].value = True

		for checkBoxID in modOptionGroup['selectedCheckBoxes']:
			modOptions[checkBoxID].value = True

	# Copy the value of any global options in this submod to all other submods (copy to those with same id)
	for subModConfig in allSubModConfigs:
		for modOptionToUpdate in subModConfig.modOptions:
			if (modOptionToUpdate.isGlobal or currentSubModFamily == subModConfig.family) and modOptionToUpdate.id in modOptions:
				modOptionToUpdate.value = modOptions[modOptionToUpdate.id].value


class DownloadItem:
	def __init__(self, modFileID, url, isOption):
		# type: (str, str, bool) -> None
		self.modFileID = modFileID  # type: str
		self.url = url  # type: str
		self.isOption = isOption  # type: bool
		self.extractableItemList = []  # type: List[common.DownloaderAndExtractor.ExtractableItem]


class DownloadPreviewFactory:
	def __init__(self, fileVersionManager):
		# type: (fileVersionManagement.VersionManager) -> None
		self.downloadItems = []  #type: List[DownloadItem]
		self.fileVersionManager = fileVersionManager #type: fileVersionManagement.VersionManager
		self.scriptNeedsUpdate = False  #type: bool
		self.totalDownload = 0  #type: int

	def addPreviewRow(self, modFileID, url, isOption):
		# type: (str, str, bool) -> None
		self.downloadItems.append(DownloadItem(modFileID, url, isOption))

	def getPreviewAsDict(self, downloadFolder, downloadManually):
		# type: (str, bool) -> Dict
		MANUAL_DOWNLOAD_STATUS_NEED_DOWNLOAD = """You need to download this file

<a href="{}" target="_blank" rel="noopener" style="word-break: break-all">{}</a>"""

		MANUAL_DOWNLOAD_STATUS_WRONG_SIZE = """File exists but is the wrong size.
Please make sure the download has finished, and check you've got the latest version of the file.
Otherwise, re-download the file from

<a href="{}" target="_blank" rel="noopener" style="word-break: break-all">{}</a>"""

		manualDownloadIncomplete = False

		# Query each download to determine the filename (and also for metalinks,
		# there may be more than one file per metalink)
		if downloadManually:
			common.makeDirsExistOK(downloadFolder)
			extractableItemCache.cacheURLs([item.url for item in self.downloadItems])

			for item in self.downloadItems:
				item.extractableItemList = extractableItemCache.get(item.url)

		previewList = []
		for item in self.downloadItems:
			fileSizeBytes = common.Globals.URL_FILE_SIZE_LOOKUP_TABLE.get(item.url)

			if item.isOption:
				updateNeeded, updateReason = True, 'Mod options are always downloaded'
				if fileSizeBytes is not None:
					self.totalDownload += fileSizeBytes
			else:
				updateNeeded, updateReason = self.fileVersionManager.updatesRequiredDict[item.modFileID]
				if updateNeeded and fileSizeBytes:
					self.totalDownload += fileSizeBytes
				if 'script' in item.modFileID and updateNeeded:
					self.scriptNeedsUpdate = True

			if not item.extractableItemList:
				previewList.append(
					{
						"id": item.modFileID,
						"fileSize": 'N/A' if fileSizeBytes is None else common.prettyPrintFileSize(fileSizeBytes),
						"rowClass": "active" if updateNeeded else "inactive",
						"updateReason": updateReason,
						"url": item.url,
						"manualDownloadStatus": None,
						"fileName": None,
					}
				)
			else:
				for extractableItem in item.extractableItemList:
					expectedDownloadPath = os.path.join(downloadFolder, extractableItem.filename)
					existsOnDisk = os.path.exists(expectedDownloadPath)

					# Check that the downloaded file has the correct file size
					correctFileSize = extractableItem.length == os.path.getsize(expectedDownloadPath) if existsOnDisk else None

					# Tell the user what they have to do to download each file (and if it's already downloaded)
					# Also visually differentiate if the row needs action (eg the user needs to download the file)
					# by setting the class of the html row
					if updateNeeded:
						if existsOnDisk:
							if correctFileSize:
								manualDownloadStatus = "OK - [{}] is already downloaded".format(extractableItem.filename)
								rowClass = "active"
							else:
								manualDownloadStatus = MANUAL_DOWNLOAD_STATUS_WRONG_SIZE.format(extractableItem.fileURL, extractableItem.fileURL)
								rowClass = "warning"
								manualDownloadIncomplete = True
						else:
							manualDownloadStatus = MANUAL_DOWNLOAD_STATUS_NEED_DOWNLOAD.format(extractableItem.fileURL, extractableItem.fileURL)
							rowClass = "warning"
							manualDownloadIncomplete = True
					else:
						manualDownloadStatus = "--"
						rowClass = "inactive"

					previewList.append(
						{
							"id": item.modFileID,
							"fileSize": 'N/A' if fileSizeBytes is None else common.prettyPrintFileSize(fileSizeBytes),
							"rowClass": rowClass,
							"updateReason": updateReason,
							"url": extractableItem.fileURL,
							"manualDownloadStatus": manualDownloadStatus,
							"fileName": extractableItem.filename,
						}
					)

		return {
			"downloadItems": previewList,
			"totalDownload": common.prettyPrintFileSize(self.totalDownload),
			"downloadManually": downloadManually,
			"manualDownloadIncomplete": manualDownloadIncomplete,
			"downloadFolder": os.path.abspath(downloadFolder),
			"updateTypeDescription": 'Update Type: {}'.format('Full Update' if self.fileVersionManager.fullUpdateRequired() else 'Partial Update'),
		}


def getDownloadPreview(fullInstallConfig, verbosePrinting=True):
	#type: (installConfiguration.FullInstallConfiguration, bool) -> Any
	####### Preview which files are going to be downloaded #######

	# Higurashi installer needs datadirectory set to determine unity version
	dataDirectory = ""
	if fullInstallConfig.subModConfig.family == 'higurashi':
		if common.Globals.IS_MAC:
			dataDirectory = os.path.join(fullInstallConfig.installPath, "Contents/Resources/Data")
		else:
			dataDirectory = os.path.join(fullInstallConfig.installPath, fullInstallConfig.subModConfig.dataName)

	modFileList = fullInstallConfig.buildFileListSorted(
		datadir=dataDirectory,
		verbosePrinting=verbosePrinting)  # type: List[installConfiguration.ModFile]
	fileVersionManager = fileVersionManagement.VersionManager(
		fullInstallConfiguration=fullInstallConfig,
		modFileList=modFileList,
		localVersionFolder=fullInstallConfig.installPath,
		verbosePrinting=False,
		datadir=dataDirectory)

	# Check for partial re-install (see https://github.com/07th-mod/python-patcher/issues/93)
	if fullInstallConfig.subModConfig.family == 'higurashi':
		installTimeProbePath = os.path.join(dataDirectory, 'Managed', 'UnityEngine.dll')
	elif fullInstallConfig.subModConfig.family == 'umineko':
		installTimeProbePath = os.path.join(fullInstallConfig.installPath, 'fonts', 'oldface0.ttf')
	else:
		installTimeProbePath = None

	if installTimeProbePath is None:
		partialReinstallDetected = False
	else:
		partialReinstallDetected = fileVersionManager.userDidPartialReinstall(installTimeProbePath)

	factory = DownloadPreviewFactory(fileVersionManager)

	# Generate preview rows for the mod files
	for modFile in modFileList:
		factory.addPreviewRow(modFile.id, modFile.url, isOption=False)

	# Generate preview rows for the mod options
	parser = installConfiguration.ModOptionParser(fullInstallConfig)
	for option in parser.downloadAndExtractOptionsByPriority:
		factory.addPreviewRow(option.name, option.url, isOption=True)

	preview = factory.getPreviewAsDict(
		downloadFolder=fullInstallConfig.subModConfig.modName + " Downloads",
		downloadManually=parser.downloadManually
	)

	return preview, factory.totalDownload, fileVersionManager.numUpdatesRequired, fileVersionManager.fullUpdateRequired(), partialReinstallDetected, factory.scriptNeedsUpdate

class InstallerGUIException(Exception):
	def __init__(self, errorReason):
		# type: (str) -> None
		self.errorReason = errorReason  # type: str

	def __str__(self):
		return self.errorReason

class InstallerGUI:
	def __init__(self):
		"""
		:param allSubModList: a list of SubModConfigs derived from the json file (should contain ALL submods in the file)
		"""
		# These two variables are set in setSubModconfigs().
		self.allSubModConfigs = None # type: List[installConfiguration.SubModConfig]
		self.idToSubMod = None # type: Dict[int, installConfiguration.SubModConfig]
		self.initCompleted = False # type: bool # true if config loaded/init finished, false otherwise
		self.initException = None # type: Optional[Exception] # None if no error, else is the exception that occured during init
		self.initTraceback = '' #type: str

		self.messageBuffer = []
		self.threadHandle = None # type: Optional[threading.Thread]
		self.threadException = None # type: Optional[Exception]
		self.selectedModName = None # type: Optional[str] # user sets this while navigating the website

		self.donationMonthsRemaining = ""
		self.donationProgressPercent = ""

		self.lastInstallPath = "" #type: str
		self.lastSubModID = 0 #type: int

		self.installRunningLock = threading.Lock()
		self.installRunningLock.acquire()

		# This caches the self.try_start_install(...) function, only used for install previews
		self.cachedFullInstallConfigs = {}  # type: Dict[str, Tuple[bool, installConfiguration.FullInstallConfiguration]]

	def shutdown(self):
		self.installRunningLock.release()

	def loadDonationStatus(self):
		self.donationMonthsRemaining, self.donationProgressPercent = common.getDonationStatus()

	def setSubModconfigs(self, allSubModConfigs):
		"""
		Set the submodconfigs to be used for the install.
		This also allows the browser to proceed from the loading screen.
		"""
		self.allSubModConfigs = allSubModConfigs # type: List[installConfiguration.SubModConfig]
		self.idToSubMod = {subMod.id: subMod for subMod in self.allSubModConfigs} # type: Dict[int, installConfiguration.SubModConfig]
		self.initCompleted = True

	def setInitError(self, error, errorTraceback):
		#type: (Exception, str) -> None
		"""
		Use to indicate an error occured during initialization.
		The error message will cleared the next time the browser checks retrieves the init status
		"""
		self.initException = error
		self.initTraceback = errorTraceback

	def installAlreadyInProgress(self):
		return self.threadHandle and self.threadHandle.is_alive()

	# TODO: this function should return an error message describing why the install couldn't be started
	def try_start_install(self, subMod, installPath, validateOnly):
		#type: (installConfiguration.SubModConfig, str, bool) -> (bool, installConfiguration.FullInstallConfiguration)
		import higurashiInstaller
		import uminekoInstaller
		import uminekoNScripterInstaller

		# Create the download folder now, even if it's not used, in case the user wants to view it
		common.makeDirsExistOK(os.path.abspath(subMod.modName + " Downloads"))

		fullInstallConfigs = None

		if os.path.isdir(installPath):
			fullInstallConfigs, _ = gameScanner.scanForFullInstallConfigs([subMod], possiblePaths=[installPath])

		# If normal scan fails, then scan the path using the more in-depth 'scanUserSelectedPath(...)' function
		if not fullInstallConfigs:
			fullInstallConfigs, errorMessage = gameScanner.scanUserSelectedPath([subMod], installPath)
			print(errorMessage)

		if validateOnly:
			gameIsUnsupported, identifier = gameScanner.gameIsUnsupported(subMod, installPath)
			if gameIsUnsupported:
				raise Exception("You have selected an old or unsupported version of Higurashi or Umineko\n"
				                "You need the NEW Steam/Mangagamer/GOG Version of the game for the mod to work correctly.\n"
				                "Reason: found [{}] at game path [{}]".format(identifier, installPath))

			# The below if statement should only trigger if the user manually selects a partially uninstalled path
			# The auto path detection should skip partially uninstalled paths
			if gameScanner.gamePathIsPartiallyUninstalled(installPath):
				raise Exception("The game at '{}' is missing important files / was only partially uninstalled and may interfere with the installer.\n\nPlease click 'OK', then read the 'Action Required' error message in red.".format(installPath))

			return (True, fullInstallConfigs[0]) if fullInstallConfigs else (False, '')
		else:
			if not fullInstallConfigs:
				raise Exception("Can't start install - No game found for mod [{}] at [{}]".format(subMod.modName, installPath))

		fullInstallSettings = fullInstallConfigs[0]

		installerFunction = {
			"higurashi": higurashiInstaller.main,
			"umineko": uminekoInstaller.mainUmineko,
			"umineko_nscripter": uminekoNScripterInstaller.main
		}.get(fullInstallSettings.subModConfig.family, None)

		if not installerFunction:
			raise Exception("Error - Unknown Game Family - I don't know how to install [{}] family of games. Please notify 07th-mod developers.".format(fullInstallSettings.subModConfig.family))

		# Prevent accidentally starting two installations at once
		if self.installAlreadyInProgress():
			raise Exception("Can't start install - installer already running.")

		def errorPrintingInstaller(args):
			try:
				installerFunction(args)
			except Exception as e:
				self.threadException = e

				raise
			common.tryDeleteLockFile()

		# Save the install path and submod.id in case the web UI refreshes the install page and forgets it
		self.lastInstallPath = installPath
		self.lastSubModID = fullInstallSettings.subModConfig.id

		# This lock file allows the installer to detect if there is already an install in progress in a different instance of the program
		# This lock file method is not foolproof, but should handle most cases
		# It is cleaned up when the install finishes (even if the install was unsuccessful), but is NOT cleaned up
		# if the program was force closed.
		common.tryCreateLockFile()

		self.threadException = None
		self.threadHandle = threading.Thread(target=errorPrintingInstaller, args=(fullInstallSettings,))
		self.threadHandle.setDaemon(True)  # Use setter for compatability with Python 2
		self.threadHandle.start()

		return (True, fullInstallSettings)

	# An example of how this class can be used.
	def server_test(self):
		# the directory where files will be served from
		workingDirectory = 'httpGUI'

		def handleInstallerData(body_string):
			# type: (str) -> str
			requestType, requestData = _decodeJSONRequest(body_string)
			if requestType not in ['statusUpdate', 'getInitStatus', 'startInstall']:
				logger.printNoTerminal('Got Request [{}] Data [{}]'.format(requestType, requestData))

			# requestData: set which game the user selected by specifying the mods->name field from the json, eg "Onikakushi Ch.1"
			# responseData: a dictionary indicating if it's a valid selection (true, false)
			def setModName(requestData):
				modNames = [config.modName for config in self.allSubModConfigs]

				# Changing the selected mod while install is in progress is not allowed
				if self.installAlreadyInProgress():
					return {'valid': True, 'modNames': modNames}

				userSelectedModToInstall = requestData['modName']
				modNameValid = userSelectedModToInstall in modNames
				if modNameValid:
					self.selectedModName = userSelectedModToInstall

				return { 'valid': modNameValid, 'modNames': modNames }

			# requestData: leave as null. will be ignored.
			# responseData: A dictionary containing basic information about each subModConfig, along with it's index.
			#               Most important is the index, which must be submitted in the 'getGamePaths' request.
			def getSubModHandlesRequestHandler(requestData):
				# a list of 'handles' to each submod.
				# This contains just enough information about each submod so that the python script knows
				# which config was chosen, and which
				subModHandles = []
				for subModConfig in self.allSubModConfigs:
					subModHandles.append(
						{
							'id': subModConfig.id,
							'modName': subModConfig.modName,
							'subModName': subModConfig.subModName,
							'descriptionID' : subModConfig.descriptionID,
							'modOptionGroups': modOptionsToWebFormat(subModConfig.modOptions),
							'family': subModConfig.family,
							'identifiers': subModConfig.identifiers,
						}
					)

				return {'selectedMod' : self.selectedModName,
						'subModHandles' : subModHandles,
						'logFilePath': os.path.abspath(common.Globals.LOG_FILE_PATH),
						'metaInfo': {
							'buildInfo': common.Globals.BUILD_INFO, # Installer Build Version and Date
							'installerIsLatest': common.Globals.INSTALLER_IS_LATEST, # 2- Tuple of whether installer is latest, and description of version information
							'lockFileExists': common.lockFileExists(), # This indicates if a install is already running in a different instance, or a previous install was killed while running
							'operatingSystem': common.Globals.OS_STRING, # The operating system - either 'windows', 'linux', or 'mac'
							'installAlreadyInProgress': self.installAlreadyInProgress(), # This is true if the install is currently running. Use to resume displaying an ongoing installation if the user accidentally closed the browser tab.
							'lastInstallPath': self.lastInstallPath, # The last path installed to - only valid if an install is currently running.
							'lastSubModID': self.lastSubModID, # The ID of the last submod installed to - only valid if an install is currently running.
							'donationMonthsRemaining': self.donationMonthsRemaining, # How many months the server can be paid for with current funding
							'donationProgressPercent': self.donationProgressPercent, # How close funding is to the 12 month donation goal, in percent
							},
						}

			# requestData: A dictionary, which contains a field 'id' containing the ID of the subMod to install, or None to get ALL possible games
			# responseData: A dictionary containing basic information about each fullConfig. Most important is the path
			#               which must be submitted in the final install step.
			# NOTE: the idOfSubMod is not unique in the returned list. You must supply both a submod ID
			#       and a path to the next stage
			def getGamePathsHandler(requestData):
				id = requestData['id']
				selectedSubMods = [self.idToSubMod[id]] if id is not None else self.allSubModConfigs
				fullInstallConfigs, partiallyUninstalledPaths = gameScanner.scanForFullInstallConfigs(selectedSubMods)
				fullInstallConfigHandles = []
				for fullConfig in fullInstallConfigs:
					fullInstallConfigHandles.append(
						{
							'id' : fullConfig.subModConfig.id,
							'modName': fullConfig.subModConfig.modName,
							'subModName': fullConfig.subModConfig.subModName,
							'path' : fullConfig.installPath,
							'isSteam' : fullConfig.isSteam,
						}
					)

				return {
					'fullInstallConfigHandles': fullInstallConfigHandles,
					'partiallyUninstalledPaths': partiallyUninstalledPaths, # Game installs which have been partially uninstalled via Steam, but where some mod files still exist on disk
				}

			#TODO: for security reasons, can't get full path from browser. Either need to copy paste, or open a
			# tk window . Adding a tk window would then require tk dependencies (no problem except requring tk on linux)

			# requestData: The submod ID and install path. If the install path is not specified, then the tkinter
			#               window chooser will be used
			# responseData: If the path is valid:
			#               If the path is invalid: null is returned
			def startInstallHandler(requestData):
				# this is not a 'proper' submod - just a handle returned form getSubModHandlesRequestHandler()
				webSubModHandle = requestData['subMod']
				webModOptionGroups = webSubModHandle['modOptionGroups']
				id = webSubModHandle['id']
				validateOnly = requestData.get('validateOnly', False)
				deleteVersionInformation = requestData.get('deleteVersionInformation', False)
				allowCache = requestData.get('allowCache', False)

				subMod = self.idToSubMod[id]


				updateModOptionsFromWebFormat(subMod.modOptions, webModOptionGroups, subMod.family, self.allSubModConfigs)

				if not validateOnly:
					logger.printNoTerminal("\nUser selected options for install:")
					for modOption in subMod.modOptions:
						logger.printNoTerminal(modOption)

				installPath = requestData.get('installPath', None)

				# Try to use the cached value, if allowed
				if allowCache and validateOnly:
					cached_result = self.cachedFullInstallConfigs.get("{}-{}".format(subMod.id, installPath), None)
				else:
					cached_result = None

				# If no cached result or caching not allowed, load from scratch
				if cached_result:
					installValid, fullInstallConfiguration = cached_result
				else:
					installValid, fullInstallConfiguration = self.try_start_install(subMod, installPath, validateOnly)

				# Overwrite or store the value in cache if the install would be valid
				if installValid:
					self.cachedFullInstallConfigs["{}-{}".format(subMod.id, installPath)] = (installValid, fullInstallConfiguration)

				retval = { 'installStarted': installValid }
				if installValid:
					if deleteVersionInformation:
						fileVersionManagement.VersionManager.deleteLocalVersionFileIfExists(fullInstallConfiguration.installPath)

					downloadItemsPreview, totalDownloadSize, numUpdatesRequired, fullUpdateRequired, partialReinstallDetected, scriptNeedsUpdate = getDownloadPreview(fullInstallConfiguration, verbosePrinting=not allowCache)
					haveEnoughFreeSpace, freeSpaceAdvisoryString = common.checkFreeSpace(
						installPath = fullInstallConfiguration.installPath,
						downloadSize=totalDownloadSize
					)
					CWDHaveEnoughFreeSpaceInstallerPath, CWDFreeSpaceAdvisoryStringInstallerPath = common.checkFreeSpace(
						installPath = os.getcwd(),
						downloadSize=totalDownloadSize
					)

					retval['validatedInstallPath'] = fullInstallConfiguration.installPath
					retval['haveEnoughFreeSpace'] = haveEnoughFreeSpace
					retval['freeSpaceAdvisoryString'] = freeSpaceAdvisoryString
					retval['CWDHaveEnoughFreeSpace'] = CWDHaveEnoughFreeSpaceInstallerPath
					retval['CWDFreeSpaceAdvisoryString'] = CWDFreeSpaceAdvisoryStringInstallerPath
					retval['downloadItemsPreview'] = downloadItemsPreview
					retval['numUpdatesRequired'] = numUpdatesRequired
					retval['fullUpdateRequired'] = fullUpdateRequired
					retval['partialReinstallDetected'] = partialReinstallDetected
					retval['scriptNeedsUpdate'] = scriptNeedsUpdate
					retval['isWine'] = fullInstallConfiguration.isWine
					retval['isSteam'] = fullInstallConfiguration.isSteam
				return retval

			# requestData: Not necessary - will be ignored
			# responseData: Returns a list of dictionaries. Each dictionary may have different fields depending on the
			#               type of status returned.
			#               Please check the _loggerMessageToStatusDict() function for a full list of fields.
			def statusUpdate(requestData):
				# If there was an exception on the installer thread, re-raise it on this main thread to display it.
				if self.threadException:
					e = self.threadException
					self.threadException = None
					raise e

				return [_loggerMessageToStatusDict(x) for x in logger.getGlobalLogger().threadSafeReadAll()]

			# This causes a TKInter window to open allowing the user to choose a game path.
			# The request data should be the submod ID.
			# This is required so that the correct file filter can be applied to the tkinter file chooser.
			# The function returns None (Javascript null) if the user failed to select a path by pressing 'cancel'.
			def showFileChooser(requestDataSubModID):
				subMod = self.idToSubMod[requestDataSubModID]
				selectedPath = askPath(subMod)
				return { 'path': selectedPath if selectedPath else None }

			def unknownRequestHandler(requestData):
				return 'Invalid request type [{}]. Should be one of [{}]'.format(requestType, requestTypeToRequestHandlers.items())

			# This function takes identical arguments to 'startInstallHandler(...)'
			# TODO: Add correct paths for Linux and Mac
			def troubleshoot(requestData):
				action = requestData['action']

				subMod = None
				if requestData.get('subMod', None) is not None:
					id = requestData['subMod']['id']
					subMod = self.idToSubMod[id]

				def _getInstallPath():
					return requestData.get('installPath', None)

				if action == 'getLogsZip':
					higurashi_log_file_name = 'output_log.txt'
					gameLogExists = False
					gameLogPath = None
					if subMod is not None and _getInstallPath() is not None:
						installPath = _getInstallPath()
						gameLogPath = os.path.join(installPath, subMod.dataName, higurashi_log_file_name)
						gameLogExists = os.path.exists(gameLogPath)

					# It's possible for zlib not to be available causing ZIP_DEFLATED to fail, so try both methods
					zipSuccess = False
					logsZipDiskPath = os.path.join(workingDirectory, common.Globals.LOGS_ZIP_FILE_PATH)
					for compressionType in [zipfile.ZIP_DEFLATED, zipfile.ZIP_STORED]:
						try:
							with zipfile.ZipFile(logsZipDiskPath, 'w', compression=compressionType) as myzip:
								for filename in os.listdir(common.Globals.LOG_FOLDER):
									path = os.path.join(common.Globals.LOG_FOLDER, filename)
									myzip.write(path, os.path.basename(path))

								if gameLogExists:
									myzip.write(gameLogPath, higurashi_log_file_name)

							zipSuccess = True
							break
						except Exception as e:
							print("Failed to compress with compression type {}: {}".format(compressionType, e))

					print('Game Log [{}] {}'.format(gameLogPath, "was found" if gameLogExists else "WAS NOT FOUND"))

					filePath = None
					if zipSuccess and os.path.exists(logsZipDiskPath):
						filePath = common.Globals.LOGS_ZIP_FILE_PATH

					return {
						'filePath' : filePath,
						'gameLogFound' : gameLogExists
					}
				elif action == 'showLogs':
					installPath = _getInstallPath()

					logsPath = installPath

					if subMod.family == 'higurashi':
						if common.Globals.IS_MAC:
							logsPath = os.path.join(installPath, "Contents/Resources/Data")
						else:
							logsPath = os.path.join(installPath, subMod.dataName)

					if os.path.exists(logsPath):
						print('Trying to open [{}]'.format(logsPath))
						common.trySystemOpen(logsPath, normalizePath=True)
					else:
						return {'error': 'Cant open Logs Folder [{}] as it doesnt exist!'.format(logsPath)}

					return {}
				elif action == 'openSaveFolder':
					if subMod.family == 'higurashi':
						result = re.findall(r'\d\d', subMod.dataName)
						if result:
							saveFolderName = os.path.expandvars(r'%appdata%\Mangagamer\higurashi' + result[0])
						else:
							return {'error': 'Sorry, cant figure out higurashi episode number :('}
					elif subMod.family == 'umineko':
						saveFolderName = os.path.join(_getInstallPath(), 'mysav')
					elif subMod.family == 'umineko_nscripter':
						# For now just open the all users profile folder
						# The actual save folder will be set according to the ';gameid' defined at the top of the script file
						saveFolderName = os.path.expandvars('%AllUsersProfile%')
					else:
						return {'error': 'Cant open save folder: Unknown game family {}'.format(subMod.family)}

					if os.path.exists(saveFolderName):
						print('Trying to open [{}]'.format(saveFolderName))
						common.trySystemOpen(saveFolderName, normalizePath=True)
					else:
						return {'error': 'Save Folder [{}] doesnt exist! Have you made any saves yet?'.format(saveFolderName)}

					return {}

			def getInitStatus(requestData):
				return { 'initCompleted': self.initCompleted,
				         'consoleLines': logger.getGlobalLogger().threadSafeReadAll()}

			def showInFileBrowser(requestData):
				common.tryShowInFileBrowser(requestData)
				return {}

			def shutdown(_requestData):
				self.shutdown()
				return {}

			def clearLatestInstallerWarning(_requestData):
				common.Globals.INSTALLER_IS_LATEST = (True, "")
				return {}

			requestTypeToRequestHandlers = {
				'setModName' : setModName,
				'subModHandles' : getSubModHandlesRequestHandler,
				'gamePaths' : getGamePathsHandler,
				'startInstall' : startInstallHandler,
				'statusUpdate' : statusUpdate,
				'troubleshoot' : troubleshoot,
				'showFileChooser' : showFileChooser,
				'getInitStatus': getInitStatus,
				'showInFileBrowser': showInFileBrowser,
				'shutdown': shutdown,
				'clearLatestInstallerWarning': clearLatestInstallerWarning,
			}

			requestHandler = requestTypeToRequestHandlers.get(requestType, None)

			# Check for unknown request
			if not requestHandler:
				return _makeJSONResponse('unknownRequest', unknownRequestHandler(requestData))

			def getExceptionAsJSON(exception, traceback):
				errorReason = ''

				if 'WinError 5' in str(exception):
					errorReason += common.Globals.PERMISSON_DENIED_ERROR_MESSAGE

				if isinstance(exception, common.SevenZipException):
					errorReason += 'SevenZip Extraction Failed - See Details'

				if isinstance(exception, common.DownloadAndVerifyError):
					errorReason += 'Download and Verify stage Failed - See Details'

				errorReason += "\n{}".format(exception)

				return _makeJSONResponse('error', {
					'errorReason': errorReason,
					'detailedExceptionInformation': "Exception while handling [{}] request:\n{}".format(requestType, traceback)
				})

			# Try and execute the request. If an exception is thrown, display the reason to the user on the web GUI
			try:
				responseDataJson = requestHandler(requestData)
			except Exception as exception:
				print('Exception Thrown handling request {}: {}'.format(requestType, exception))
				traceback.print_exc()
				return getExceptionAsJSON(exception, traceback.format_exc())

			if self.initException is not None:
				tempException = self.initException
				return getExceptionAsJSON(tempException, self.initTraceback)

			return _makeJSONResponse(responseType=requestType, responseDataJson=responseDataJson)

		# add handlers for each post URL here. currently only 'installer_data' is used.
		post_handlers = {
			'installer_data': handleInstallerData,
		}

		def on_server_started(web_server):
			page = 'loading_screen.html'
			web_server_url = 'http://{}:{}/{}'.format(web_server.server_address[0], web_server.server_address[1], page)
			print("If the web page did not open, you can manually navigate to {} in your browser.".format(web_server_url))
			if common.Globals.LAUNCH_BROWSER:
				common.openURLInBrowser(web_server_url)
			else:
				try:
					serverInfoPath = 'server-info.json'
					print("NOTE: Launching browser from Python script is disabled. Server started at {}, info written to {}".format(web_server_url, serverInfoPath))
					with open(serverInfoPath, 'w') as serverInfo:
						serverInfo.write(json.dumps({
							'ip': web_server.server_address[0],
							'port': web_server.server_address[1],
							'page': page,
						}))
				except Exception as e:
					print("Failed to write server info: {}".format(e))

		start_server(working_directory=workingDirectory,
		             post_handlers=post_handlers,
		             installRunningLock=self.installRunningLock,
		             serverStartedCallback=on_server_started)
