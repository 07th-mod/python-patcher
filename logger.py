import subprocess
import sys

# From https://stackoverflow.com/a/14906787/848627
# Replace with the standard "https://docs.python.org/2/library/logging.html" module later?
class Logger(object):
    def __init__(self, logPath):
        self.terminal = sys.stdout
        self.log = open(logPath, "a")

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
        #TODO: probably should flush every X seconds rather than every write
        self.log.flush()

    def flush(self):
        #this flush method is needed for python 3 compatibility.
        #this handles the flush command by doing nothing.
        #you might want to specify some extra behavior here.
        pass
