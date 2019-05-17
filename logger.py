import os
import sys
from common import makeDirsExistOK

try:
	import queue
except:
	import Queue as queue

class StdErrRedirector():
	"""
	Use to redirect stderr to a Logger object. You could also just do `stderr = Logger(...)`, but this way
	lets you add special behavior when stderr output is received (like logging to a special 'error' file)
	"""
	def __init__(self, attachedLogger):
		self.attachedLogger = attachedLogger

	def writeNoLog(self, message):
		self.attachedLogger.write(message)

	def write(self, message):
		self.attachedLogger.write(message)

	def flush(self):
		pass

# From https://stackoverflow.com/a/14906787/848627
# Replace with the standard "https://docs.python.org/2/library/logging.html" module later?
class Logger(object):
	globalLogger = None

	def __init__(self, logPath):
		self.logPath = logPath
		self.terminal = sys.stdout
		makeDirsExistOK(os.path.dirname(logPath))
		self.log = open(logPath, "a")
		self.callbacks = {}
		self.queue = queue.Queue(maxsize=100000)

	def writeNoLog(self, message):
		self.terminal.write(message)

	def write(self, message, runCallbacks=True):
		self.terminal.write(message)
		self.log.write(message)
		self._tryPutInQueue(message)

		#execute all bound callbacks
		if runCallbacks:
			for callback in self.callbacks.values():
				callback(message)

		#TODO: probably should flush every X seconds rather than every write
		self.log.flush()

	def flush(self):
		#this flush method is needed for python 3 compatibility.
		#this handles the flush command by doing nothing.
		#you might want to specify some extra behavior here.
		pass

	def threadSafeRead(self):
		# type: () -> str
		"""
		:return: the latest message, or None if no more data to read
		"""
		try:
			return self.queue.get_nowait()
		except queue.Empty:
			return None

	def threadSafeReadAll(self):
		# type: () -> [str]
		"""
		:return: An array of strings. If nothing to read, returns the empt ylist
		"""
		return list(iter(self.threadSafeRead, None))

	def _tryPutInQueue(self, item):
		# type: (str) -> None
		try:
			self.queue.put_nowait(item)
		except queue.Full:
			if not self.queue_full_error:
				self.queue_full_error = True
				self.terminal.write("WARNING: Install status message queue is full (possibly GUI was closed but console left open)")

def getGlobalLogger():
	# type: () -> Logger
	return Logger.globalLogger

def setGlobalLogger(logger):
	# type: (Logger) -> None
	Logger.globalLogger = logger

def registerLoggerCallback(callbackKey, callback):
	"""
	NOTE: the order in which the callbacks are executed is random!
	:param callbackKey:
	:param callback:
	:return:
	"""
	Logger.globalLogger.callbacks[callbackKey] = callback

def deregisterLoggerCallback(callbackKey):
	return Logger.globalLogger.callbacks.pop(callbackKey, None)
