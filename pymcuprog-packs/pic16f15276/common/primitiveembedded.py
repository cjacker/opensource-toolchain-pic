"""
    primitiveembedded.py

    Provides support for running primitive sequences on embedded hosts
    For example Python on Raspberry Pi
"""
import time
from proginterfaceprovider import ProgInterfaceIcspC8D24
from proginterfaceprovider import ProgInterfaceIcspC6D16

from primitivebase import PrimitiveFunction
from primitivebase import PrimitiveResourceProvider
from primitivebase import DebugInterface
from primitivebase import BoardInterface
from primitivebase import HardwareInterface
from primitiveproxy import PrimitiveEmbeddedProxy

from pyedbglib.primitive import primitives



class PrimitiveResourceProviderEmbedded(PrimitiveResourceProvider):
    """
    Resource provider for Embedded
    """

    def __init__(self, host):
        self.host = host

    def programming_interface(self, variant):
        """
        Selects the programming interface variant
        Only 8-bit command; 24-bit data is currently supported
        """
        if variant == ProgInterfaceIcspC8D24:
            return ProgInterfaceIcspC8D24Embedded(self.host)
        raise Exception("Invalid ICSP variant requested.")

    def debug_interface(self, family):
        return DebugInterfaceEmbedded(self.host)

    def board_interface(self):
        return BoardInterfaceEmbedded(self.host)

    def pin_driver(self):
        return HardwareInterfaceEmbedded(self.host)


class PrimitiveFunctionEmbedded(PrimitiveFunction):
    """
    Function provider for host output
    """

    def __init__(self, model_object):
        PrimitiveFunction.__init__(self, model_object)
        self.logger.info("Using host primitives")
        self.proxy = PrimitiveEmbeddedProxy()
        provider = PrimitiveResourceProviderEmbedded(self.proxy)
        self.model_object.initialise(provider)

    def invoke(self, method, **kwargs):
        """
        Invokes a method and returns the result immediately
        """
        return method(self.model_object, **kwargs)

    def invoke_read(self, bytes_to_read, method, **kwargs):
        """
        Invokes a method and returns data from the data pipe
        """
        self.invoke(method, **kwargs)
        return self.proxy.get_data_buffer(0, bytes_to_read)

    def invoke_write(self, data_to_write, method, **kwargs):
        """
        Invokes a method after putting data in the data pipe
        """
        self.proxy.set_data_buffer(0, data_to_write)
        return self.invoke(method, **kwargs)


class ProgInterfaceIcspC8D24Embedded(ProgInterfaceIcspC8D24):
    """
    Embedded programming interface
    """

    def __init__(self, host):
        ProgInterfaceIcspC8D24.__init__(self)
        self.host = host

    # MSB-first 4 character string literal
    def write_string_literal(self, characters):
        """
        Write string literal chatacters to the target
        Typically "MCHP" for enter tmod
        """
        if len(characters) != 4:
            raise Exception("Invalid string length")
        value = 0
        for char in characters[::-1]:
            value <<= 8
            value += ord(char)

        self.write_32bit_literal(value)

    def write_32bit_literal(self, value):
        """
        Write 32-bit literal value
        """
        command = bytearray([primitives.WRITE_BITS_LITERAL_MSB, 32])
        command.extend([value & 0xFF])
        command.extend([(value >> 8) & 0xFF])
        command.extend([(value >> 16) & 0xFF])
        command.extend([(value >> 24) & 0xFF])
        self.host.execute(command)

    def write_command_literal(self, value):
        """
        Write literal 8-bit command
        """
        command = bytearray([primitives.WRITE_BITS_LITERAL_MSB, 8])
        command.extend([value & 0xFF])
        command.extend([(value >> 8) & 0xFF])
        command.extend([(value >> 16) & 0xFF])
        command.extend([(value >> 24) & 0xFF])
        self.host.execute(command)

    def write_payload_literal(self, value):
        """
        Write literal 24-bit payload (data)
        """
        command = bytearray([primitives.P16ENV3_WRITE_PAYLOAD_LITERAL, 24])
        command.extend([value & 0xFF])
        command.extend([(value >> 8) & 0xFF])
        command.extend([(value >> 16) & 0xFF])
        command.extend([(value >> 24) & 0xFF])
        self.host.execute(command)

    def write_data_word(self):
        """
        Indirect write of data word (comes from data pipe)
        """
        self.host.execute([primitives.P16ENV3_WRITE_BUFFER])

    def write_data_byte(self):
        """
        Indirect write of data byte (comes from data pipe)
        """
        self.host.execute([primitives.P16ENV3_WRITE_BUFFER_DFM])

    def read_data_word(self):
        """
        Indirect read of data word (goes to data pipe)
        """
        self.host.execute([primitives.P16ENV3_READ_PAYLOAD_PFM])

    def read_data_byte(self):
        """
        Indirect read of data byte (goes to data pipe)
        """
        self.host.execute([primitives.P16ENV3_READ_PAYLOAD_DFM])


class DebugInterfaceEmbedded(DebugInterface):
    """
    Embedded debugging interface
    """

    def __init__(self, host):
        self.host = host

    def debug_command(self, de_cmd, bytes_out, bytes_in):
        raise Exception("Debug not supported")


class HardwareInterfaceEmbedded(HardwareInterface):
    """
    Embedded hardware service
    """

    def __init__(self, host):
        self.host = host

    def set_clk(self):
        self.host.execute([primitives.SET_CLK_HI])

    def clr_clk(self):
        self.host.execute([primitives.SET_CLK_LO])

    def _pins(self, value):
        self.host.execute([primitives.SET_ICSP_PINS, value & 0xFF])

    def get_pins(self):
        self.host.execute([primitives.GET_ICSP_PINS])
        print("TODO: get pins should return a value!")
        # TODO - get value
        return 0

    def set_mclr_high(self):
        self.host.execute([primitives.SET_VPP_ON])

    def set_mclr_low(self):
        self.host.execute([primitives.SET_VPP_OFF])


class BoardInterfaceEmbedded(BoardInterface):
    """
    Embedded board service
    """

    def __init__(self, host):
        self.host = host

    def delay_ms(self, milli_seconds):
        time.sleep(milli_seconds * 0.001)

    def delay_us(self, micro_seconds):
        time.sleep(micro_seconds * 0.000001)
