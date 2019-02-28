# TODO: test on python 2.7
# see https://blog.anvileight.com/posts/simple-python-http-server/
import os

import common

try:
	import http.server as server
	from http.server import HTTPServer
except:
	import SimpleHTTPServer as server
	from BaseHTTPServer import HTTPServer


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
		# Python 3 has this ability built-in, but Python 2 does not.
		def translate_path(self, path):
			relative_path = os.path.relpath(os.getcwd(), server.SimpleHTTPRequestHandler.translate_path(self, path))
			return os.path.join(working_directory, relative_path)

		def list_directory(self, path):
			self.send_error(404, "No permission to list directory")
			return None

		def do_POST(self):
			content_length = int(self.headers['Content-Length'])
			body_as_string = self.rfile.read(content_length).decode('utf-8')

			path_without_slash = self.path.lstrip('/')

			try:
				response_string = post_handlers[path_without_slash](body_as_string)
			except KeyError:
				response_string = 'Error - Unknown Data given' + body_as_string
				print("Got Unknown Data - PathWithoutSlash =", path_without_slash)
				print("received " + body_as_string + "via post request")

			# print(self.headers)
			# TODO: decide to keep or remove caching. Leave in for development.
			# Add headers to prevent caching (of ALL files)
			# See: https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cache-Control#Preventing_caching
			# Only 'Cache-Control' is required, but the other two aid in backwards compatibility
			self.send_response(200)
			self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
			self.send_header('Pragma', 'no-cache')
			self.send_header('Expires', '0')
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
		import json

		def handleInstallerData(body_string):
			# type: (str) -> str
			received_object = json.loads(body_string)
			print(("Got Installer Data:", received_object))

			retObject = {'asdf': [1, 3, 4, 5, 6]}

			return json.dumps(retObject)

		# add handlers for each post URL here. currently only 'installer_data' is used.
		post_handlers = {
			'installer_data': handleInstallerData,
		}

		start_server(working_directory='httpGUI',
		             post_handlers=post_handlers,
		             serverStartedCallback=lambda: common.trySystemOpen("http://127.0.0.1:8000"))
