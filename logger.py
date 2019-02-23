import sys

# From https://stackoverflow.com/a/14906787/848627
# Replace with the standard "https://docs.python.org/2/library/logging.html" module later?
class Logger(object):
	globalLogger = None

	def __init__(self, logPath):
		self.logPath = logPath
		self.terminal = sys.stdout
		self.log = open(logPath, "a")
		self.callbacks = {}

	def write(self, message, runCallbacks=True):
		self.terminal.write(message)
		self.log.write(message)

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
