# -*- coding: utf-8 -*-
import collections
import logging
from cStringIO import StringIO
import pywebhdfs
from pywebhdfs.webhdfs import PyWebHdfsClient
import BaseMultiProcessModule
import multiprocessing
import Decorators
import Utils
import time
import sys

@Decorators.ModuleDocstringParser
class WebHdfsSink(BaseMultiProcessModule.BaseMultiProcessModule):
    """
    Store events in hdfs via webhdfs.

    server: webhdfs/https node
    user: Username for webhdfs.
    path: Path to logfiles. String my contain any of pythons strtime directives.
    name_pattern: Filename pattern. String my conatain pythons strtime directives and event fields.
    format: Which event fields to send on, e.g. '%(@timestamp)s - %(url)s - %(country_code)s'. If not set the whole event dict is send.
    store_interval_in_secs: Send data to webhdfs in x seconds intervals.
    batch_size: Send data to webhdfs if event count is above, even if store_interval_in_secs is not reached.
    backlog_size: Maximum count of events waiting for transmission. Events above count will be dropped.
    compress: Compress output as gzip file. For this to be effective, the chunk size should not be too small.

    Configuration example:

    - WebHdfsSink:
        server:                               # <default: 'localhost:14000'; type: string; is: optional>
        user:                                 # <type: string; is: required>
        path:                                 # <type: string; is: required>
        name_pattern:                         # <type: string; is: required>
        format:                               # <type: string; is: required>
        store_interval_in_secs:               # <default: 10; type: integer; is: optional>
        batch_size:                           # <default: 1000; type: integer; is: optional>
        backlog_size:                         # <default: 5000; type: integer; is: optional>
        compress:                             # <default: None; type: None||string; values: [None,'gzip','snappy']; is: optional>
    """

    module_type = "output"
    """Set module type"""
    can_run_parallel = True

    def configure(self, configuration):
         # Call parent configure method
        BaseMultiProcessModule.BaseMultiProcessModule.configure(self, configuration)
        # Make urllib3s logging less verbose.
        urllib3_logger = logging.getLogger('requests.packages.urllib3.connectionpool')
        urllib3_logger.setLevel(logging.CRITICAL)
        self.server, self.port = self.getConfigurationValue('server').split(':')
        self.user = self.getConfigurationValue('user')
        self.events_container = []
        self.batch_size = self.getConfigurationValue('batch_size')
        self.backlog_size = self.getConfigurationValue('backlog_size')
        self.path = self.getConfigurationValue('path')
        self.name_pattern = self.getConfigurationValue('name_pattern')
        self.format = self.getConfigurationValue('format')
        self.compress = self.getConfigurationValue('compress')
        if self.compress == 'gzip':
            try:
                import gzip
            except ImportError:
                self.logger.error('%sGzip compression selected but gzip module could not be loaded.%s' % (Utils.AnsiColors.FAIL, Utils.AnsiColors.ENDC))
                self.gp.shutDown()
        if self.compress == 'snappy':
            try:
                import snappy
            except ImportError:
                self.logger.error('%sSnappy compression selected but snappy module could not be loaded.%s' % (Utils.AnsiColors.FAIL, Utils.AnsiColors.ENDC))
                self.gp.shutDown()
        self.is_storing = False
        self.lock = multiprocessing.Lock()
        self.timed_store_func = self.getTimedStoreFunc()

    def getHdfsClient(self):
        try:
            hdfs = PyWebHdfsClient(host=self.server, port=self.port, user_name=self.user)
        except:
            etype, evalue, etb = sys.exc_info()
            self.logger.error('%sCould not connect to webfs service on %s. Excpeption: %s, Error: %s.%s' % (Utils.AnsiColors.FAIL, self.getConfigurationValue('server'), etype, evalue, Utils.AnsiColors.ENDC))
            return None
        return hdfs

    def getTimedStoreFunc(self):
        @Decorators.setInterval(self.getConfigurationValue('store_interval_in_secs'))
        def timedStoreEvents():
            if self.is_storing or self.lock._semlock._is_mine():
                return
            self.storeEvents(self.events_container)
        return timedStoreEvents

    def ensureFileExists(self, path):
        try:
            self.hdfs.get_file_dir_status(path)
            success = True
        except pywebhdfs.errors.FileNotFound:
            success = self.createFile(path)
        return success

    def ensureDirExists(self, path):
        try:
            self.hdfs.get_file_dir_status(path)
            success = True
        except pywebhdfs.errors.FileNotFound:
            success = self.createDir(path)
        return success

    def createDir(self, path, recursive=True):
        try:
            self.hdfs.make_dir(path)
        except:
            etype, evalue, etb = sys.exc_info()
            self.logger.error('%sCould not create directory %s. Exception: %s, Error: %s.%s' % (Utils.AnsiColors.FAIL, path, etype, evalue, Utils.AnsiColors.ENDC))
            return False
        return True

    def createFile(self, path):
        try:
            data = ''
            if self.compress == 'snappy':
                data = self.getSnappyHeader()
            self.hdfs.create_file(path, data)
        except:
            etype, evalue, etb = sys.exc_info()
            self.logger.error('%sCould not create file %s. Exception: %s, Error: %s.%s' % (Utils.AnsiColors.FAIL, path, etype, evalue, Utils.AnsiColors.ENDC))
            return False
        return True

    def run(self):
        self.hdfs = self.getHdfsClient()
        Utils.TimedFunctionManager.startTimedFunction(self.timed_store_func)
        # Call parent run method
        BaseMultiProcessModule.BaseMultiProcessModule.run(self)

    def handleEvent(self, event):
        # Wait till a running store is finished to avoid strange race conditions while manipulating self.events_container.
        while self.is_storing:
            time.sleep(.0001)
        while len(self.events_container) > self.backlog_size:
            self.logger.warning("%sMaximum number of items (%s) in buffer reached. Waiting for flush.%s" % (AnsiColors.WARNING, self.maxsize, AnsiColors.ENDC))
            time.sleep(1)
        self.events_container.append(event)
        if len(self.events_container) == self.batch_size:
            self.storeEvents(self.events_container)
        yield event

    def storeEvents(self, events):
        """
        As a sidenote: synchronizing multiple processes with a lock to ensure only one process will write to a given
        file, seems not to work as expected. webhdfs does not directly free a lease on a file after appending.
        A better approach seems to be to retry the write a number of times before failing.
        """
        if len(events) == 0:
            return
        self.is_storing = True
        path = time.strftime(self.path)
        self.ensureDirExists(path)
        write_data = collections.defaultdict(str)
        for event in events:
            filename = time.strftime(self.getConfigurationValue('name_pattern'))
            filename = filename % event
            line = Utils.mapDynamicValue(self.format, event)
            write_data[filename] += line
        write_tries = 0
        retry_sleep_time = .4
        for filename, lines in write_data.items():
            if self.compress == 'gzip':
                filename += ".gz"
                lines = self.compressGzip(lines)
            elif self.compress == 'snappy':
                filename += ".snappy"
                lines = self.compressSnappy(lines)
            while write_tries < 10:
                try:
                    self.ensureFileExists('%s/%s' % (path, filename))
                    self.hdfs.append_file('%s/%s' % (path, filename), lines)
                    break
                except KeyError:
                    etype, evalue, etb = sys.exc_info()
                    self.logger.error('%sCould no log event %s. The format key %s was not present in event.%s' % (Utils.AnsiColors.FAIL, event, evalue, Utils.AnsiColors.ENDC))
                except pywebhdfs.errors.PyWebHdfsException:
                    write_tries += 1
                    # Retry max_retry times. This can solve problems like leases beeing hold by another process.
                    if write_tries < 10:
                        time.sleep(retry_sleep_time * write_tries)
                        continue
                    # Issue error after max retries.
                    etype, evalue, etb = sys.exc_info()
                    self.logger.error('%sMax write retries reached. Could no log event %s. Exception: %s, Error: %s.%s' % (Utils.AnsiColors.FAIL, event, etype, evalue, Utils.AnsiColors.ENDC))
        self.events_container = []
        self.is_storing = False

    def compressGzip(self, data):
        buffer = StringIO()
        compressor = gzip.GzipFile(mode='wb', fileobj=buffer)
        try:
            compressor.write(data)
        finally:
            compressor.close()
        return buffer.getvalue()

    def compressSnappy(self, data):
        compressed = snappy.compress(data)
        return compressed
