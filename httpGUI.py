# see https://blog.anvileight.com/posts/simple-python-http-server/
from __future__ import print_function, unicode_literals

import itertools
import os
import json
import re
import zipfile
import subprocess

import common
import traceback
import threading

import gameScanner
import commandLineParser
import logger
from gameScanner import SubModConfig

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
	from typing import List, Optional, Dict
except ImportError:
	pass # Just needed for pycharm comments

collapseWhiteSpaceRegex = re.compile(r"[\s\b]+")
def _TKAskPath(subMod):
	try:
		Tk
	except NameError:
		raise RuntimeError("Tk is not installed on this system")

	# TODO: on 2.7 you can use .withdraw on the root window, but on python 3 it prevents the filedialog from showing!
	# TODO: for now, put up with the root window showing when choosing path manually
	if common.Globals.IS_MAC:
		return subprocess.check_output(["osascript", "-e",  "POSIX path of (choose file of type {\"com.apple.application\"} with prompt \"Please choose a game to install to\")"]).strip().decode("utf-8")
	root = Tk()

	# this creates the default option, which allows you to select all identifiers and any extras specified here.
	extensionList = ["com.apple.application"] + subMod.identifiers
	fileList = [("Game Executable", x) for x in extensionList]
	fileList.append(("Any In Game Folder", "*.*"))

	# returns empty string if user didn't select any file or folder. If a file is selected, convert it to the parent folder
	installFolder = filedialog.askopenfilename(filetypes=fileList)

	root.destroy()

	return installFolder

def _makeJSONResponse(responseType, responseDataJson):
	# type: (str, object) -> str
	return json.dumps({
		'responseType': responseType,
		'responseData': responseDataJson,
	})


def _decodeJSONRequest(jsonString):
	# type: (str) -> (str, object)
	json_compatible_dict = json.loads(jsonString)
	return (json_compatible_dict['requestType'], json_compatible_dict['requestData'])


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
		return {
			"subTaskPercentage": status.percentCompleted,
			"subTaskDescription": "Downloading - [{}]) CN: {} DL: {} ETA: {}".format(status.amountCompletedString, status.numConnections, status.speed, status.ETAString),
		}

	sevenZipMessageAndPercent = {}

	# Look for a 7z line showing the file count and filename: "404 - big\bmp\background\cg\dragon_a.png"
	# Sometimes 7z emits just the file count without the filename (will appear as a line with a number on it)
	sevenZipMessage = commandLineParser.tryGetSevenZipFilecountAndFileNameString(message)
	if sevenZipMessage:
		sevenZipMessageAndPercent['subTaskDescription'] = "Extracting - {}".format(sevenZipMessage)
	else:
		sevenZipFileCount = commandLineParser.tryGetSevenZipFileCount(message)
		if sevenZipFileCount:
			sevenZipMessageAndPercent['subTaskDescription'] = "Extracting - {}".format(sevenZipFileCount)
		else:
			sevenZipExtractionStartedString = commandLineParser.tryGetSevenZipExtractionStarted(message)
			if sevenZipExtractionStartedString:
				sevenZipMessageAndPercent['subTaskDescription'] = sevenZipExtractionStartedString

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
	return {"msg": displayedMessage,
	        "error": True if message.startswith(common.Globals().INSTALLER_MESSAGE_ERROR_PREFIX) else False}

def start_server(working_directory, post_handlers, serverStartedCallback=lambda _: None):
	# type: (str, dict, function) -> None
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
			logger.getGlobalLogger().writeNoLog('Browser requested [{}], Trying to deliver [{}]\n'.format(self.path, path))
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
				logger.getGlobalLogger().writeNoLog('404 Error: Cant deliver [{}] - file not found!\n'.format(path))
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
			self.wfile.write(response_string.encode('utf-8'))

	# The default HTTPServer allows multiple servers on the same address without error
	# we would prefer for an error to be raised, so you know if you had multiple copies of the installer open at once
	class HTTPServerNoReuse(HTTPServer):
		allow_reuse_address = 0

	# This program is only intended to be used on a loopback (non-public facing) interface.
	# Do not modify the INTERFACE_IP variable.
	# Using Port '0' lets the OS choose an unused port
	httpd = HTTPServerNoReuse(("127.0.0.1", 0), CustomHandler)

	# note: calling the http server constructor will immediately start listening for connections,
	# however it won't give a response until "serve_forever()" is called. This allows running the
	# serverStartedCallback() before we block by calling serve_forever()
	serverStartedCallback(httpd)
	httpd.serve_forever()

def modOptionsToWebFormat(modOptions):
	# type: (List[gameScanner.ModOption]) -> List[Dict]
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
	for groupName, groupOptionsIterator in itertools.groupby(modOptions, key=lambda x: x.group):
		groupOptions = list(groupOptionsIterator)
		radioOptions = [convertOptionToHTTPFormat(o) for o in groupOptions if o.isRadio]
		checkBoxOptions = [convertOptionToHTTPFormat(o) for o in groupOptions if not o.isRadio]
		httpFormattedOptions.append({
			'name': groupName,
			'radio': radioOptions,
			'checkBox': checkBoxOptions,
			# these two variables are provided to be filled in by the webpage.
			'selectedCheckBoxes': [],
			'selectedRadio': None if not radioOptions else radioOptions[0]['id'], #note: the ID is of the form "BGM Options-Old BGM" - see definition of ModOption
		})

	return httpFormattedOptions

def updateModOptionsFromWebFormat(modOptionsToUpdate, webFormatModOptions):
	modOptions = dict((modOption.id, modOption) for modOption in modOptionsToUpdate)

	for modOptionGroup in webFormatModOptions:
		selectedRadioID = modOptionGroup['selectedRadio']
		if selectedRadioID is not None:
			modOptions[selectedRadioID].value = True

		for checkBoxID in modOptionGroup['selectedCheckBoxes']:
			modOptions[checkBoxID].value = True

class InstallerGUIException(Exception):
	def __init__(self, errorReason):
		# type: (str) -> None
		self.errorReason = errorReason  # type: str

	def __str__(self):
		return self.errorReason

class InstallerGUI:
	def __init__(self, allSubModConfigs):
		"""
		:param allSubModList: a list of SubModConfigs derived from the json file (should contain ALL submods in the file)
		"""
		self.allSubModConfigs = allSubModConfigs # type: List[SubModConfig]
		self.idToSubMod = {subMod.id: subMod for subMod in self.allSubModConfigs} # type: Dict[int, SubModConfig]
		self.messageBuffer = []
		self.threadHandle = None # type: Optional[threading.Thread]
		self.selectedModName = None # type: Optional[str] # user sets this while navigating the website

	def installAlreadyInProgress(self):
		return self.threadHandle and self.threadHandle.is_alive()

	# TODO: this function should return an error message describing why the install couldn't be started
	def try_start_install(self, subMod, installPath, validateOnly):
		#type: (SubModConfig, str, bool) -> (bool, gameScanner.FullInstallConfiguration)
		import higurashiInstaller
		import uminekoInstaller

		fullInstallConfigs = None
		if os.path.isdir(installPath):
			fullInstallConfigs = gameScanner.scanForFullInstallConfigs([subMod], possiblePaths=[installPath])

		# If normal scan fails, then scan the path using the more in-depth 'scanUserSelectedPath(...)' function
		if not fullInstallConfigs:
			fullInstallConfigs, errorMessage = gameScanner.scanUserSelectedPath([subMod], installPath)
			print(errorMessage)

		if validateOnly:
			return (True, fullInstallConfigs[0]) if fullInstallConfigs else (False, '')
		else:
			if not fullInstallConfigs:
				raise Exception("Can't start install - No game found for mod [{}] at [{}]".format(subMod.modName, installPath))

		fullInstallSettings = fullInstallConfigs[0]

		installerFunction = {
			"higurashi": higurashiInstaller.main,
			"umineko": uminekoInstaller.mainUmineko
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
				print('{}{}'.format(common.Globals().INSTALLER_MESSAGE_ERROR_PREFIX, e))
				raise
			common.tryDeleteLockFile()

		# This lock file allows the installer to detect if there is already an install in progress in a different instance of the program
		# This lock file method is not foolproof, but should handle most cases
		# It is cleaned up when the install finishes (even if the install was unsuccessful), but is NOT cleaned up
		# if the program was force closed.
		common.tryCreateLockFile()

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
			if requestType != 'statusUpdate':
				print('Got Request [{}] Data [{}]\n'.format(requestType, requestData))

			# requestData: set which game the user selected by specifying the mods->name field from the json, eg "Onikakushi Ch.1"
			# responseData: a dictionary indicating if it's a valid selection (true, false)
			def setModName(requestData):
				userSelectedModToInstall = requestData['modName']
				modNames = [config.modName for config in self.allSubModConfigs]
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
							'downloadSize': common.prettyPrintFileSize(subModConfig.downloadSize),
						}
					)

				return {'selectedMod' : self.selectedModName,
						'subModHandles' : subModHandles,
						'logFilePath': os.path.abspath(common.Globals.LOG_FILE_PATH),
						'os' : common.Globals.OS_STRING,
						}

			# requestData: A dictionary, which contains a field 'id' containing the ID of the subMod to install, or None to get ALL possible games
			# responseData: A dictionary containing basic information about each fullConfig. Most important is the path
			#               which must be submitted in the final install step.
			# NOTE: the idOfSubMod is not unique in the returned list. You must supply both a submod ID
			#       and a path to the next stage
			def getGamePathsHandler(requestData):
				id = requestData['id']
				selectedSubMods = [self.idToSubMod[id]] if id is not None else self.allSubModConfigs
				fullInstallConfigs = gameScanner.scanForFullInstallConfigs(selectedSubMods)
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
				return fullInstallConfigHandles

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

				subMod = self.idToSubMod[id]

				updateModOptionsFromWebFormat(subMod.modOptions, webModOptionGroups)
				print("\nUser selected options for install:")
				for modOption in subMod.modOptions:
					print(modOption)

				installPath = requestData.get('installPath', None)
				installValid, fullInstallConfiguration = self.try_start_install(subMod, installPath, validateOnly)
				retval = { 'installStarted': installValid }
				if installValid:
					retval['validatedInstallPath'] = fullInstallConfiguration.installPath
					retval['haveEnoughFreeSpace'], retval['freeSpaceAdvisoryString'] = common.checkFreeSpace(
						installPath = fullInstallConfiguration.installPath,
						recommendedFreeSpaceBytes = 2.5 * subMod.downloadSize
					)
				return retval

			# requestData: Not necessary - will be ignored
			# responseData: Returns a list of dictionaries. Each dictionary may have different fields depending on the
			#               type of status returned.
			#               Please check the _loggerMessageToStatusDict() function for a full list of fields.
			def statusUpdate(requestData):
				return [_loggerMessageToStatusDict(x) for x in logger.getGlobalLogger().threadSafeReadAll()]

			def getNews(requestData):
				return common.tryGetRemoteNews(requestData)

			def getDonationStatus(requestData):
				monthsRemaining, progressPercent = common.getDonationStatus()
				return  {
					'monthsRemaining': monthsRemaining,
					'progressPercent': progressPercent,
				}

			def getInstallerMetaInfo(requestData):
				return {
					'buildInfo': common.Globals.BUILD_INFO,
					'lockFileExists': common.lockFileExists(), # Indicate if it looks like install already in progress
					'operatingSystem': common.Globals.OS_STRING,
					'installAlreadyInProgress': self.installAlreadyInProgress(),
				}

			# This causes a TKInter window to open allowing the user to choose a game path.
			# The request data should be the submod ID.
			# This is required so that the correct file filter can be applied to the tkinter file chooser.
			# The function returns None (Javascript null) if the user failed to select a path by pressing 'cancel'.
			def showFileChooser(requestDataSubModID):
				subMod = self.idToSubMod[requestDataSubModID]
				selectedPath = _TKAskPath(subMod)
				return { 'path': selectedPath if selectedPath else None }

			def unknownRequestHandler(requestData):
				return 'Invalid request type [{}]. Should be one of [{}]'.format(requestType, requestTypeToRequestHandlers.items())

			# This function takes identical arguments to 'startInstallHandler(...)'
			# TODO: Add correct paths for Linux and Mac
			def troubleshoot(requestData):
				action = requestData['action']

				id = requestData['subMod']['id']
				subMod = self.idToSubMod[id]

				# If the requestData included the install path, use that. Otherwise, open a dialog to choose the path
				# returns the empty string if user cancels selecting a path
				def _getInstallPath():
					_installPath = requestData.get('installPath', None)
					if _installPath is None:
						userSelectedPath = os.path.dirname(_TKAskPath(subMod))
						fullInstallConfigs, errorMessage = gameScanner.scanUserSelectedPath([subMod], userSelectedPath)
						_installPath = '' if not fullInstallConfigs else fullInstallConfigs[0].installPath
					return _installPath

				if action == 'getLogsZip':
					installPath = _getInstallPath()
					higurashi_log_file_name = 'output_log.txt'
					gameLogPath = os.path.join(installPath, subMod.dataName, higurashi_log_file_name)
					gameLogExists = os.path.exists(gameLogPath)
					with zipfile.ZipFile(os.path.join(workingDirectory, common.Globals.LOGS_ZIP_FILE_PATH), 'w') as myzip:
						for filename in os.listdir(common.Globals.LOG_FOLDER):
							path = os.path.join(common.Globals.LOG_FOLDER, filename)
							myzip.write(path, os.path.basename(path))

						if gameLogExists:
							myzip.write(gameLogPath, higurashi_log_file_name)

					print('Game Log [{}] {}'.format(gameLogPath, "was found" if gameLogExists else "WAS NOT FOUND"))

					return {
						'filePath' : common.Globals.LOGS_ZIP_FILE_PATH,
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
							saveFolderName = os.path.expandvars('%appdata%\Mangagamer\higurashi' + result[0])
						else:
							return {'error': 'Sorry, cant figure out higurashi episode number :('}
					elif subMod.family == 'umineko':
						saveFolderName = os.path.join(_getInstallPath(), 'mysav')
					else:
						return {'error': 'Cant open save folder: Unknown game family {}'.format(subMod.family)}

					if os.path.exists(saveFolderName):
						print('Trying to open [{}]'.format(saveFolderName))
						common.trySystemOpen(saveFolderName, normalizePath=True)
					else:
						return {'error': 'Save Folder [{}] doesnt exist! Have you made any saves yet?'.format(saveFolderName)}

					return {}


			requestTypeToRequestHandlers = {
				'setModName' : setModName,
				'subModHandles' : getSubModHandlesRequestHandler,
				'gamePaths' : getGamePathsHandler,
				'startInstall' : startInstallHandler,
				'statusUpdate' : statusUpdate,
				'getNews' : getNews,
				'getDonationStatus' : getDonationStatus,
				'troubleshoot' : troubleshoot,
				'showFileChooser' : showFileChooser,
				'getInstallerMetaInfo': getInstallerMetaInfo,
			}

			requestHandler = requestTypeToRequestHandlers.get(requestType, None)

			# Check for unknown request
			if not requestHandler:
				return _makeJSONResponse('unknownRequest', unknownRequestHandler(requestData))

			# Try and execute the request. If an exception is thrown, display the reason to the user on the web GUI
			try:
				responseDataJson = requestHandler(requestData)
			except Exception as exception:
				print('Exception Thrown handling request {}: {}'.format(requestType, exception))
				traceback.print_exc()
				return _makeJSONResponse('error', {
					'errorReason': 'Exception handling [{}] request: {}'.format(requestType, traceback.format_exc())
				})

			return _makeJSONResponse(responseType=requestType, responseDataJson=responseDataJson)

		# add handlers for each post URL here. currently only 'installer_data' is used.
		post_handlers = {
			'installer_data': handleInstallerData,
		}

		def on_server_started(web_server):
			web_server_url = 'http://{}:{}'.format(*web_server.server_address)
			common.trySystemOpen(web_server_url)
			print("Please open {} in your browser if it didn't open automatically".format(web_server_url))

		start_server(working_directory=workingDirectory,
		             post_handlers=post_handlers,
		             serverStartedCallback=on_server_started)
