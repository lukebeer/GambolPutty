# -*- coding: utf-8 -*-
import pprint
import sys
import types
import msgpack
import BaseThreadedModule
import Decorators


@Decorators.ModuleDocstringParser
class MsgPackParser(BaseThreadedModule.BaseThreadedModule):
    """
    Decode:
     It will parse the msgpack data and create or replace fields in the internal data dictionary with
     the corresponding json fields.
    Encode:
     Encode selected fields or all to msgpack format.

    Configuration template:

    - MsgPackParser:
        action:                                 # <default: 'decode'; type: string; values: ['decode','encode']; is: optional>
        mode:                                   # <default: 'line'; type: string; values: ['line','stream']; is: optional>
        source_fields:                          # <default: 'data'; type: string||list; is: optional>
        target_field:                           # <default: None; type: None||string; is: optional>
        keep_original:                          # <default: False; type: boolean; is: optional>
        receivers:
          - NextModule
    """

    module_type = "parser"
    """Set module type"""

    def configure(self, configuration):
        # Call parent configure method
        BaseThreadedModule.BaseThreadedModule.configure(self, configuration)
        self.source_fields = self.getConfigurationValue('source_fields')
        # Allow single string as well.
        if isinstance(self.source_fields, types.StringTypes):
            self.source_fields = [self.source_fields]
        self.target_field = self.getConfigurationValue('target_field')
        self.drop_original = not self.getConfigurationValue('keep_original')
        if self.getConfigurationValue('action') == 'decode':
            if self.getConfigurationValue('mode') == 'line':
                self.handleEvent = self.decodeEventLine
            else:
                self.unpacker = msgpack.Unpacker()
                self.handleEvent = self.decodeEventStream
        else:
            self.handleEvent = self.encodeEvent

    def decodeEventStream(self, event):
        for source_field in self.source_fields:
            if source_field not in event:
                continue
            self.unpacker.feed(event[source_field])
            for decoded_data in self.unpacker:
                if self.drop_original:
                    event.pop(source_field, None)
                if self.target_field:
                    event.update({self.target_field: decoded_data})
                else:
                    try:
                        event.update(decoded_data)
                    except:
                        etype, evalue, etb = sys.exc_info()
                        self.logger.warning("Could not update event with msgpack data: %s. Exception: %s, Error: %s." % (decoded_data, etype, evalue))
                yield event

    def decodeEventLine(self, event):
        for source_field in self.source_fields:
            if source_field not in event:
                continue
            try:
                decoded_data = msgpack.unpackb(event[source_field])
            except:
                etype, evalue, etb = sys.exc_info()
                self.logger.warning("Could not parse msgpack event data: %s. Exception: %s, Error: %s." % (event[source_field], etype, evalue))
                continue
            if self.drop_original:
                event.pop(source_field, None)
            if self.target_field:
                event.update({self.target_field: decoded_data})
            else:
                try:
                    event.update(decoded_data)
                except:
                    etype, evalue, etb = sys.exc_info()
                    self.logger.warning("Could not update event with msgpack data: %s. Exception: %s, Error: %s." % (decoded_data, etype, evalue))
        yield event

    def encodeEvent(self, event):
        if self.source_fields == ['all']:
            encode_data = event
        else:
            encode_data = []
            for source_field in self.source_fields:
                if source_field not in event:
                    continue
                encode_data.append({source_field: event[source_field]})
                if self.drop_original:
                    event.pop(source_field, None)
        try:
            encode_data = msgpack.packb(encode_data)
        except:
            etype, evalue, etb = sys.exc_info()
            self.logger.warning("Could not msgpack encode event data: %s. Exception: %s, Error: %s." % (event, etype, evalue))
            yield event
            return
        if self.source_fields == ['all']:
            event = encode_data
        else:
            event.update({self.target_field: encode_data})
        yield event