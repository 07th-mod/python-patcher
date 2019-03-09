# TODO: test on python 2.7
# see https://blog.anvileight.com/posts/simple-python-http-server/
from __future__ import print_function

import os
import json
import common
import traceback

import gameScanner
import commandLineParser
import logger

try:
	import urlparse
except:
	import urllib.parse as urlparse

try:
	import http.server as server
	from http.server import HTTPServer
except:
	import SimpleHTTPServer as server
	from BaseHTTPServer import HTTPServer

#tk is only required for the below  _askGameExeAndValidate function
try:
	from tkinter import Tk
	from tkinter import filedialog
except ImportError:
	from Tkinter import Tk
	import tkFileDialog as filedialog

def _TKAskGameExe(subMod):
	# TODO: on 2.7 you can use .withdraw on the root window, but on python 3 it prevents the filedialog from showing!
	# TODO: for now, put up with the root window showing when choosing path manually
	root = Tk()

	# this creates the default option, which allows you to select all identifiers and any extras specified here.
	extensionList = ["com.apple.application"] + subMod.identifiers
	fileList = [("Game Executable", x) for x in extensionList]
	fileList.append(("Any In Game Folder", "*.*"))

	# returns empty string if user didn't select any file or folder. If a file is selected, convert it to the parent folder
	installFolder = filedialog.askopenfilename(filetypes=fileList)
	if os.path.isfile(installFolder):
		installFolder = os.path.normpath(os.path.join(installFolder, os.pardir))

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
			"overallTaskDescription": "Task: {}".format(status.currentTask),
		}

	# Search the line for parts of a aria status update: "[#7f0d78 27MiB/910MiB(3%) CN:8 DL:4.2MiB ETA:3m27s]"
	# Searches for "#7f0d78 27MiB/910MiB(3%)" and also "ETA:3m27s" separately
	status = commandLineParser.tryGetAriaStatusUpdate(message)
	if status:
		return {
			"subTaskPercentage": status.percentCompleted,
			"subTaskDescription": "Downloading - [{}]) ETA: {}".format(status.amountCompletedString, status.ETAString),
		}

	# Look for a 7z line showing the file count and filename: "404 - big\bmp\background\cg\dragon_a.png"
	sevenZipMessage = commandLineParser.tryGetSevenZipFilecountAndFileNameString(message)
	if sevenZipMessage:
		# installStatusWidget.threadsafe_notify_text("Extracting - {}".format(sevenZipMessage))
		return {"subTaskDescription": "Extracting - {}".format(sevenZipMessage)}

	# Look for a line with just a percent on it (eg 51%)
	sevenZipPercent = commandLineParser.tryGetSevenZipPercent(message)
	if sevenZipPercent:
		# installStatusWidget.threadsafe_set_subtask_progress(sevenZipPercent)
		return {"subTaskPercentage": sevenZipPercent}

	# Sometimes 7z emits just the file count without the filename (will appear as a line with a number on it)
	sevenZipFileCount = commandLineParser.tryGetSevenZipFileCount(message)
	if sevenZipFileCount:
		return {"subTaskDescription": "Extracting - {}".format(sevenZipFileCount)}

	# if the message is not a aria or 7zip message, just show it in the gui log window
	return {"msg": message}

def start_server(working_directory, post_handlers, serverStartedCallback=lambda: None):
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
			print('Browser requested [{}], Delivered [{}]'.format(originalPath, path))
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
	PORT = 8000
	INTERFACE_IP = "127.0.0.1"
	SERVER_ADDRESS = (INTERFACE_IP, PORT)

	# run the server
	print("Started HTTP Server GUI @ [{}:{}]".format(INTERFACE_IP, PORT))
	httpd = HTTPServerNoReuse(SERVER_ADDRESS, CustomHandler)

	# note: calling the http server constructor will immediately start listening for connections,
	# however it won't give a response until "serve_forever()" is called. This allows running the
	# serverStartedCallback() before we block by calling serve_forever()
	serverStartedCallback()
	httpd.serve_forever()


class InstallerGUI:
	def __init__(self, allSubModConfigs):
		"""
		:param allSubModList: a list of SubModConfigs derived from the json file (should contain ALL submods in the file)
		"""
		self.allSubModConfigs = allSubModConfigs
		self.idToSubMod = {subMod.id: subMod for subMod in self.allSubModConfigs}
		self.messageBuffer = []
		self.threadHandle = None

	def try_start_install(self, subMod, installPath):
		import higurashiInstaller
		import uminekoInstaller
		import threading

		fullInstallConfigs = gameScanner.scanForFullInstallConfigs([subMod], possiblePaths=[installPath])
		if not fullInstallConfigs:
			return False

		fullInstallSettings = fullInstallConfigs[0]

		installerFunction = {
			"higurashi": higurashiInstaller.main,
			"umineko": uminekoInstaller.mainUmineko
		}.get(fullInstallSettings.subModConfig.family, None)

		if not installerFunction:
			raise Exception("Error - Unknown Game Family - I don't know how to install [{}] family of games. Please notify 07th-mod developers.".format(fullInstallSettings.subModConfig.family))

		# Prevent accidentally starting two installations at once
		if self.threadHandle and self.threadHandle.is_alive():
			return False

		self.threadHandle = threading.Thread(target=installerFunction, args=(fullInstallSettings,))
		self.threadHandle.setDaemon(True)  # Use setter for compatability with Python 2
		self.threadHandle.start()

		return True

	# An example of how this class can be used.
	def server_test(self):
		def handleInstallerData(body_string):
			# type: (str) -> str
			requestType, requestData = _decodeJSONRequest(body_string)
			logger.getGlobalLogger().writeNoLog('Got Request [{}] Data [{}]'.format(requestType, requestData))

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
						}
					)

				return subModHandles

			# requestData: A dictionary, which contains a field 'id' containing the ID of the subMod to install
			# responseData: A dictionary containing basic information about each fullConfig. Most important is the path
			#               which must be submitted in the final install step.
			# NOTE: the idOfSubMod is not unique in the returned list. You must supply both a submod ID
			#       and a path to the next stage
			def getGamePathsHandler(requestData):
				id = requestData['id']
				selectedSubMod = self.idToSubMod[id]
				fullInstallConfigs = gameScanner.scanForFullInstallConfigs([selectedSubMod])
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
				id = requestData['id']
				subMod = self.idToSubMod[id]
				installPath = requestData.get('installPath', None)
				if installPath is None:
					installPath = _TKAskGameExe(subMod)

				return { 'installStarted' : self.try_start_install(subMod, installPath) }

			# requestData: Not necessary - will be ignored
			# responseData: Returns a list of dictionaries. Each dictionary may have different fields depending on the
			#               type of status returned.
			#               Please check the _loggerMessageToStatusDict() function for a full list of fields.
			def statusUpdate(requestData):
				return [_loggerMessageToStatusDict(x) for x in logger.getGlobalLogger().threadSafeReadAll()]

			def unknownRequestHandler(requestData):
				return 'Invalid request type [{}]. Should be one of [{}]'.format(requestType, requestTypeToRequestHandlers.items())

			requestTypeToRequestHandlers = {
				'subModHandles' : getSubModHandlesRequestHandler,
				'gamePaths' : getGamePathsHandler,
				'startInstall' : startInstallHandler,
				'statusUpdate' : statusUpdate,
			}

			requestHandler = requestTypeToRequestHandlers.get(requestType, None)
			if requestHandler:
				return _makeJSONResponse(responseType=requestType, responseDataJson=requestHandler(requestData))
			else:
				return _makeJSONResponse('error', unknownRequestHandler(requestData))

		# add handlers for each post URL here. currently only 'installer_data' is used.
		post_handlers = {
			'installer_data': handleInstallerData,
		}

		start_server(working_directory='httpGUI',
		             post_handlers=post_handlers,
		             serverStartedCallback=lambda: common.trySystemOpen('http://127.0.0.1:8000'))
