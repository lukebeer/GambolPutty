# -*- coding: utf-8 -*-
import sys
import redis
import BaseThreadedModule
from Decorators import ModuleDocstringParser

@ModuleDocstringParser
class RedisClient(BaseThreadedModule.BaseThreadedModule):
    """
    A simple wrapper around the redis python module.

    Configuration example:

    - module: RedisClient
      configuration:
        server: redis.server    # <default: 'localhost'; type: string; is: optional>
        port: 6379              # <default: 6379; type: integer; is: optional>
        db: 0                   # <default: 0; type: integer; is: optional>
        password: None          # <default: None; type: None||string; is: optional>
        socket-timeout: 10      # <default: 10; type: integer; is: optional>
        charset: 'utf-8'        # <default: 'utf-8'; type: string; is: optional>
        errors: 'strict'        # <default: 'strict'; type: string; is: optional>
        decode-responses: False # <default: False; type: boolean; is: optional>
        unix-socket-path: ''    # <default: ''; type: string; is: optional>
    """

    def configure(self, configuration):
         # Call parent configure method
        BaseThreadedModule.BaseThreadedModule.configure(self, configuration)
        try:
            self.redis_client = redis.StrictRedis(host=self.getConfigurationValue('server'),
                                                  port=self.getConfigurationValue('port'),
                                                  db=self.getConfigurationValue('db'),
                                                  password=self.getConfigurationValue('password'),
                                                  socket_timeout=self.getConfigurationValue('socket-timeout'),
                                                  charset=self.getConfigurationValue('charset'),
                                                  errors=self.getConfigurationValue('errors'),
                                                  decode_responses=self.getConfigurationValue('decode-responses'),
                                                  unix_socket_path=self.getConfigurationValue('unix-socket-path'))
        except:
            etype, evalue, etb = sys.exc_info()
            self.logger.error("Could not connect to redis store at %s. Excpeption: %s, Error: %s." % (configuration['server'],etype, evalue))

    def getClient(self):
        return self.redis_client