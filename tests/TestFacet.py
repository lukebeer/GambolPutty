import extendSysPath
import ModuleBaseTestCase
import mock
import time
import Utils
import RedisStore
import Facet

class TestFacet(ModuleBaseTestCase.ModuleBaseTestCase):

    def setUp(self):
        super(TestFacet, self).setUp(Facet.Facet(gp=ModuleBaseTestCase.MockGambolPutty()))

    def testInternalFacet(self):
        self.test_object.configure({'source_field': 'url',
                                    'group_by': '$(remote_ip)',
                                    'add_event_fields': ['remote_ip','user_agent'],
                                    'interval': .1})
        self.checkConfiguration()
        self.test_object.initAfterFork()
        self.test_object.receiveEvent(Utils.getDefaultEventDict({'url': 'http://www.google.com',
                                                              'remote_ip': '127.0.0.1',
                                                              'user_agent': 'Eric'}))
        self.test_object.receiveEvent(Utils.getDefaultEventDict({'url': 'http://www.gambolputty.com',
                                                              'remote_ip': '127.0.0.2',
                                                              'user_agent': 'John'}))
        self.test_object.receiveEvent(Utils.getDefaultEventDict({'url': 'http://www.johann.com',
                                                              'remote_ip': '127.0.0.1',
                                                              'user_agent': 'Graham'}))
        events = []
        # Wait for interval.
        time.sleep(.3)
        for event in self.receiver.getEvent():
            if event['gambolputty']['event_type'] != 'facet':
                continue
            events.append(event)
        self.assertEquals(len(events), 2)
        self.assertEquals(events[0]['facets'], ['http://www.gambolputty.com'])

    def testRedisFacet(self):
        rc = RedisStore.RedisStore(gp=mock.Mock())
        rc.configure({'server': 'localhost'})
        self.test_object.gp.modules = {'RedisStore': {'instances': [rc]}}
        self.test_object.configure({'source_field': 'url',
                                    'group_by': '$(remote_ip)',
                                    'add_event_fields': ['remote_ip','user_agent'],
                                    'interval': .1,
                                    'redis_store': 'RedisStore',
                                    'redis_ttl': 5})
        self.checkConfiguration()
        self.test_object.initAfterFork()
        self.test_object.receiveEvent(Utils.getDefaultEventDict({'url': 'http://www.google.com',
                                                              'remote_ip': '127.0.0.1',
                                                              'user_agent': 'Eric'}))
        self.test_object.receiveEvent(Utils.getDefaultEventDict({'url': 'http://www.johann.com',
                                                              'remote_ip': '127.0.0.1',
                                                              'user_agent': 'Graham'}))
        self.test_object.receiveEvent(Utils.getDefaultEventDict({'url': 'http://www.gambolputty.com',
                                                              'remote_ip': '127.0.0.2',
                                                              'user_agent': 'John'}))
        events = []
        # Wait for interval.
        time.sleep(.3)
        for event in self.receiver.getEvent():
            if event['gambolputty']['event_type'] != 'facet':
                continue
            events.append(event)
        self.assertEquals(len(events), 2)
        self.assertEquals(events[1]['facets'], ['http://www.gambolputty.com'])

    def tearDown(self):
        pass