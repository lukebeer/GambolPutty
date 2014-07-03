# -*- coding: utf-8 -*-
import pprint
import msgpack
import threading
import Utils
import BaseModule

# Conditional imports for python2/3
try:
    import Queue as queue
except ImportError:
    import queue

class BaseThreadedModule(BaseModule.BaseModule, threading.Thread):
    """
    Base class for all gambolputty modules. In most cases this is the class to inherit from when implementing a new module.
    It will only be started as thread when necessary. This depends on the configuration and how the modules are
    combined.

    If you happen to override one of the methods defined here, be sure to know what you
    are doing ;) You have been warned...

    Configuration example:

    - module: SomeModuleName
      id:                               # <default: ""; type: string; is: optional>
      filter:                           # <default: None; type: None||string; is: optional>
      pool_size:                        # <default: 2; type: integer; is: optional>
      queue_size:                       # <default: 20; type: integer; is: optional>
      receivers:
       - ModuleName
       - ModuleAlias
    """

    can_run_parallel = True

    def __init__(self, gp):
        BaseModule.BaseModule.__init__(self, gp)
        threading.Thread.__init__(self)
        self.input_queue = False
        self.alive = True
        self.daemon = True

    def setInputQueue(self, queue):
        self.input_queue = queue

    def getInputQueue(self):
        return self.input_queue

    def pollQueue(self, block=True, timeout=None):
        try:
            packed_data = self.input_queue.get(block, timeout)
            events = msgpack.unpackb(packed_data)
            # After msgpack.uppackb we just have a normal dict. Cast this to KeyDotNotationDict.
            for event in events:
                yield Utils.KeyDotNotationDict(event)
        except (KeyboardInterrupt, SystemExit, ValueError, OSError):
            # Keyboard interrupt is catched in GambolPuttys main run method.
            # This will take care to shutdown all running modules.
            pass

    def run(self):
        # This module will only be run as thread if an input_queue exists. This will depend on the actual configuration.
        if not self.input_queue:
            return
        if not self.receivers:
            # Only issue warning for those modules that are expected to have receivers.
            # TODO: A better solution should be implemented...
            if self.module_type not in ['stand_alone', 'output']:
                self.logger.error("%sShutting down module %s since no receivers are set.%s" % (Utils.AnsiColors.FAIL, self.__class__.__name__, Utils.AnsiColors.ENDC))
                return
        while self.alive:
            for event in self.pollQueue():
                if not event:
                    continue
                self.receiveEvent(event)

    def shutDown(self):
        # Call parent shutDown method
        BaseModule.BaseModule.shutDown(self)
        self.alive = False
