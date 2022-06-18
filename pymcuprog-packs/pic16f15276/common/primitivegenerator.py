"""
PrimitiveGenerator

Provides hardware, board and debug services using primitives
"""
from pyedbglib.primitive import primitives

from primitivebase import DebugInterface
from primitivebase import HardwareInterface
from primitivebase import BoardInterface
from primitivebase import ProgramExecInterface

class HardwareInterfacePrimitiveGenerator(HardwareInterface):
    """
    Primitive generator for hardware services
    """

    def __init__(self, target):
        self.target = target

    def set_clk(self):
        self.target.new_element(primitives.SET_CLK_HI)

    def clr_clk(self):
        self.target.new_element(primitives.SET_CLK_LO)

    def _pins(self, value):
        self.target.new_element(primitives.SET_ICSP_PINS)
        self.target.append_byte(value & 0xFF)

    def get_pins(self):
        self.target.new_element(primitives.GET_ICSP_PINS)
        result = self.target.sync(1)
        return result

    def set_mclr_high(self):
        self.target.new_element(primitives.SET_VPP_ON)

    def set_mclr_low(self):
        self.target.new_element(primitives.SET_VPP_OFF)


class BoardInterfacePrimitiveGenerator(BoardInterface):
    """
    Primitive generator for board services
    """

    def __init__(self, target):
        self.target = target

    def delay_ms(self, milli_seconds):
        self.target.new_element(primitives.DELAY_MS)
        self.target.append_le16(milli_seconds)

    def delay_us(self, micro_seconds):
        self.target.new_element(primitives.DELAY_US)
        self.target.append_le16(micro_seconds)


class DebugInterfacePrimitiveGenerator(DebugInterface):
    """
    Primitive generator for debug services
    """
    # pylint: disable=too-few-public-methods
    def __init__(self, target):
        self.target = target

    def debug_command(self, de_cmd, bytes_out, bytes_in):
        self.target.new_element(primitives.DE_COMMAND)
        self.target.append_byte(de_cmd)
        self.target.append_le16(bytes_out)
        self.target.append_le16(bytes_in)

class ProgramExecInterfacePrimitiveGenerator(ProgramExecInterface):
    """
    Primitive generator for programming executive services
    """
    def __init__(self, target):
        self.target = target

    def send_word(self, word):
        """
        Send a 16 bit word
        """
        self.target.new_element(primitives.P24_SEND_PE_WORD)
        self.target.append_le16(word)

    def send_word_buf(self):
        """
        Send a 16 bit word from the data pipe (indirect write)
        """
        self.target.new_element(primitives.P24_SEND_PE_WORD_BUF)

    def receive_word(self):
        """
        Receive a 16 bit word to the data pipe (indirect read)
        """
        self.target.new_element(primitives.P24_RECEIVE_PE_WORD)

    def handshake(self):
        """
        Wait for Programming Executive to finish executing current command
        """
        self.target.new_element(primitives.P24_PE_HANDSHAKE)