"""
PrimitiveProxy
A set of proxy objects for processing primitive sequences in various ways
"""
import logging

from primitiveutils import enclose_as_lambda
from primitiveutils import flatten_tree
from pyedbglib.primitive.primitivecontroller import PrimitiveControllerCommand


class PrimitiveProxy(object):
    """
    Base class for all proxy objects
    """
    # pylint: disable=too-few-public-methods
    def __init__(self):
        pass


class PrimitiveEmbeddedProxy(PrimitiveProxy):
    """
    Proxy object for Embedded Python
    """

    def __init__(self):
        PrimitiveProxy.__init__(self)
        self.logger = logging.getLogger(__name__)
        self.logger.info("Creating ICSP IO driver connection")
        from icspio import IcspIo
        self.icsp = IcspIo()

    def execute(self, primitives):
        """
        Execute function on icsp driver
        :param primitives: primitive string to execute
        """
        return self.icsp.execute(primitives)

    def set_data_buffer(self, buffer_id, values):
        """
        Puts data into the fifo for icsp driver
        :param buffer_id: <not used>
        :param values: byte array of values
        """
        return self.icsp.set_data_buffer(buffer_id, values)

    def get_data_buffer(self, buffer_id, numbytes):
        """
        Gets data from the fifo for icsp driver
        :param buffer_id: <not used>
        :param numbytes: number of bytes to retrieve
        """
        return self.icsp.get_data_buffer(buffer_id, numbytes)


class PrimitivePrinterProxy(PrimitiveProxy):
    """
    Proxy object for printer output
    """

    def __init__(self):
        PrimitiveProxy.__init__(self)
        self._content = None
        self.reset()

    def reset(self):
        """
        Clears content (string accumulator)
        """
        self._content = ""

    def append(self, printstring):
        """
        Append content (to string accumulator)
        """
        self._content += "\n" + printstring

    def get_content(self):
        """
        Retrieve content (from string accumulator)
        """
        return self._content


class PrimitiveAccumulatorProxy(PrimitiveProxy):
    """
    Proxy object for accumulating primitive sequences
    """

    def __init__(self):
        PrimitiveProxy.__init__(self)
        self.logger = logging.getLogger(__name__)
        self._content = None
        self._tokens = None
        self.reset()

    def sync(self, numbytes):
        """
        Synchronisation point
        Does nothing on this proxy object since synchronisation is not required
        """
        pass

    def reset(self):
        """
        Resets contents and tokens
        """
        self._content = []
        self._tokens = []

    def new_element(self, element):
        """
        Add a new element (ie: primitive construct)
        :param element: ID (first byte) of primitive
        """
        self._content.append([element])

    def append_byte(self, value):
        """
        Append a byte to a primitive construct
        """
        self._content[-1].extend([value & 0xFF])

    def append_le16(self, value):
        """
        Append a 16-bit little endian value to a primitive construct
        """
        self._content[-1].extend([value & 0xFF])
        self._content[-1].extend([(value >> 8) & 0xFF])

    def append_le32(self, value):
        """
        Append a 32-bit little endian value to a primitive construct
        """
        self._content[-1].extend([value & 0xFF])
        self._content[-1].extend([(value >> 8) & 0xFF])
        self._content[-1].extend([(value >> 16) & 0xFF])
        self._content[-1].extend([(value >> 24) & 0xFF])

    def add_token(self, token):
        """
        Insert a token in a primitive construct
        """
        self.logger.debug("Adding token")
        self._content[-1].extend([token])

    def mark(self, data):
        """
        Mark a location and add a token
        """
        token = {
            'offset': len(self._content),
            'bytes': data
        }
        self._tokens.append(token)

    def get_tokens(self):
        """
        Retrieve all tokens
        """
        return self._tokens

    def get_content(self):
        """
        Retrieve all primitive constructs
        """
        return self._content


class PrimitiveExecuterProxy(PrimitiveAccumulatorProxy):
    """
    Proxy object for executing primitive sequences
    """

    def __init__(self, controller):
        PrimitiveAccumulatorProxy.__init__(self)
        self.transportproxy = TransportProxy(controller, 64)  # todo - correct size
        self._result_accumulator = None
        self.clear_accumulated_results()

    def new_element(self, element):
        """
        Add a new element
        """
        # Is something in the pipe?
        if self._content:
            self.transportproxy.send_block(self._content[0])
            self.reset()
        # Add
        PrimitiveAccumulatorProxy.new_element(self, element)

    def sync(self, numbytes):
        """
        Sync point.
        If a primitive sequence is already loaded, execute it remotely and retrieve the result
        """
        if self._content:
            self.transportproxy.send_block(self._content[0])
            result = self.transportproxy.sync()
            self._result_accumulator.extend(result[0:numbytes])
            self.reset()
            return result
        return 0

    def finalise(self):
        """
        Executes primitive sequence remotely by syncing with no data required
        """
        self.sync(0)

    def clear_accumulated_results(self):
        """
        Clear the result accumulator
        """
        self._result_accumulator = bytearray()

    def get_accumulated_results(self):
        """
        Retrieve accumulated results
        """
        results = self._result_accumulator
        self.clear_accumulated_results()
        return results


class TransportProxy(object):
    """
    Proxy object for a transport layer.
    This object accumulates sequences up to a given blocksize, and then executes them as a block.
    Sync points also force execution, for example when a result is required before execution can continue
    """

    def __init__(self, transport, blocksize):
        self.logger = logging.getLogger(__name__)
        self.transport = transport
        self.blocksize = blocksize
        self.content = None
        self.length = None
        self.reset()

    def reset(self):
        """
        Reset and clear content
        """
        self.content = []
        self.length = 0

    def send_block(self, content):
        """
        Adds a block of content.
        If no space is available in the current frame, it is flushed (executed)
        :param content: block of content to add
        """
        self.logger.debug("Sending block:")
        self.logger.debug(content)
        if self.length + len(content) > self.blocksize:
            # No space, flush to hardware first
            self.logger.debug("Full flush!")
            self._flush()

        self.content.append(content)
        self.length += len(content)

    def sync(self):
        """
        Sync point
        Flushes (executes) content and returns values
        """
        self.logger.debug("Sync flush")
        return self._flush()

    def _flush(self):
        """
        Executes the primitive sequence remotely
        """
        commands = []
        for i in range(len(self.content)):

            lamb = enclose_as_lambda([self.content[i]])
            section = flatten_tree(lamb)[0]
            ati_command = PrimitiveControllerCommand(section)
            commands.append(ati_command.generate_bytestream())

        self.logger.debug("Execute")
        results = self.transport.execute(commands)
        self.reset()
        # Ditch all but the last result.  Sync points are used for retrieving useful results
        result = results[-1]
        return result
