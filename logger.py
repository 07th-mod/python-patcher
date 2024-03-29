from __future__ import unicode_literals

import io
import os
import shutil
import sys
import common

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
		common.makeDirsExistOK(os.path.dirname(logPath))
		self.logFile = io.open(logPath, "a", encoding='UTF-8')
		self.secondaryLogFile = None
		self.secondaryLogFilePath = None
		self.callbacks = {}
		self.queue = queue.Queue(maxsize=100000)

	def write(self, message, runCallbacks=True, noTerminal=False):
		if common.Globals.IS_PYTHON_2 and isinstance(message, str):
			message = message.decode(encoding='UTF-8', errors='replace')

		if not noTerminal:
			self.terminal.write(message)

		if self.logFile:
			self.logFile.write(message)

		if self.secondaryLogFile is not None:
			try:
				self.secondaryLogFile.write(message)
			except:
				pass

		self._tryPutInQueue(message)

		#execute all bound callbacks
		if runCallbacks:
			for callback in self.callbacks.values():
				callback(message)

		#TODO: probably should flush every X seconds rather than every write
		if self.logFile:
			self.logFile.flush()

		if self.secondaryLogFile is not None:
			try:
				self.secondaryLogFile.flush()
			except:
				pass

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

	def trySetSecondaryLoggingPath(self, newLogFilePath):
		# type: (str) -> None
		"""
		Specify the secondary path for the log file.
		The current log file will be copied to the newLogFilePath.
		Any additional writes will go to both the existing log file and the new one.
		:param newLogFilePath: the path where the new log file will be created (and updated)
		:return: None
		"""
		# If new log file path is the same as current one, don't do anything
		if self.secondaryLogFilePath is not None:
			if os.path.normpath(self.secondaryLogFilePath) == os.path.normpath(newLogFilePath):
				return

		try:
			common.makeDirsExistOK(os.path.dirname(newLogFilePath))
			shutil.copy(self.logPath, newLogFilePath)

			if self.secondaryLogFile is not None:
				fileToClose = self.secondaryLogFile
				self.secondaryLogFile = None
				fileToClose.close()
				print("Closed log file at: [{}]".format(newLogFilePath))

			self.secondaryLogFile = io.open(newLogFilePath, "a", encoding='UTF-8')
			self.secondaryLogFilePath = newLogFilePath
			print("Successfully created secondary log file at: [{}]".format(newLogFilePath))
		except Exception as e:
			print("Couldn't create secondary log at: [{}] Error: {}".format(newLogFilePath, e))

	def close_all_logs(self):
		if self.logFile is not None:
			self.logFile.close()
			self.logFile = None
		if self.secondaryLogFile is not None:
			self.secondaryLogFile.close()
			self.secondaryLogFile = None


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

def printNoTerminal(message):
	Logger.globalLogger.write(
		"{}\n".format(message),
		noTerminal=True
	)
