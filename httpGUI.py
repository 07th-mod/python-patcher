# TODO: test on python 2.7
# see https://blog.anvileight.com/posts/simple-python-http-server/
from __future__ import print_function

import os
import json
import urlparse

import common
import traceback

try:
	import http.server as server
	from http.server import HTTPServer
except:
	import SimpleHTTPServer as server
	from BaseHTTPServer import HTTPServer


def _makeJSONResponse(responseType, json_compatible_object):
	# type: (str, object) -> str
	return json.dumps({
		'responseType': responseType,
		'responseData': json_compatible_object,
	})


def _decodeJSONRequest(jsonString):
	# type: (str) -> (str, object)
	json_compatible_dict = json.loads(jsonString)
	return (json_compatible_dict['requestType'], json_compatible_dict['requestData'])


def start_server(working_directory, post_handlers, serverStartedCallback=lambda: None):
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
	:exception: see serve_forever() of the TCPServer class. In particular, if you try to run two instances of this
				server on the same computer, you will get a:
				"OSError: [WinError 10048] Only one usage of each socket address is normally permitted"
	"""

	# use BaseHTTPRequestHandler if you don't want to auto-serve files
	# use SimpleHTTPRequestHandler to auto serve files from the current dir
	class CustomHandler(server.SimpleHTTPRequestHandler):
		# Uncomment this if using BaseHTTPRequestHandler
		# def do_GET(self):
		# self.send_response(200)
		# self.end_headers()
		#
		# with open('index.html', 'rb') as indexFile:
		# self.wfile.write(indexFile.read())

		# Override the translate_path function to serve files from a specified directory



		def list_directory(self, path):
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
			path = os.path.join(working_directory, relativePath)
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
					response = 'Exception @ POSTPath: [{}] Data: [{}] - See Terminal'.format(path_without_slash, body_as_string)
					response_string = _makeJSONResponse('error', response)
					print(response)
					traceback.print_exc()
			except KeyError:
				response = 'Error @ POSTPath: [{}] Data: [{}]'.format(path_without_slash, body_as_string)
				print(response)
				response_string = _makeJSONResponse('error', response)

			# print(self.headers)
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

	# An example of how this class can be used.
	def server_test(self):
		def handleInstallerData(body_string):
			# type: (str) -> str
			requestType, requestData = _decodeJSONRequest(body_string)
			print('Got Request [{}] Data [{}]'.format(requestType, requestData))

			# a list of 'handles' to each submod.
			# This contains just enough information about each submod so that the python script knows
			# which config was chosen, and which
			subModHandles = []
			for i, subModConfig in enumerate(self.allSubModConfigs):
				subModHandles.append(
					{
						'index' : i,
						'modName' : subModConfig.modName,
						'subModName' : subModConfig.subModName,
					}
				)

			return _makeJSONResponse('subModHandles', subModHandles)

		# add handlers for each post URL here. currently only 'installer_data' is used.
		post_handlers = {
			'installer_data': handleInstallerData,
		}

		start_server(working_directory='httpGUI',
		             post_handlers=post_handlers,
		             serverStartedCallback=lambda: common.trySystemOpen('http://127.0.0.1:8000'))
