"""
DebugInterfaceProvider

Provides services for interacting with a debug executive variant
"""
import logging

# Primitive definitions
from pyedbglib.primitive import primitives

# ICSP pin value defintions
ICSP_CLK_DIR_ID = 0
ICSP_DATA_DIR_ID = 1
ICSP_CLK_VALUE_ID = 2
ICSP_DATA_VALUE_ID = 3


class PicDebugInterface(object):
    """
    Base class for PIC debug interface (interfacing with the debug executive)
    """

    # pylint: disable=too-few-public-methods
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.debug_proxy = None
        self.hw = None
        self.board = None

    def initialise(self, resourceprovider):
        """
        Creates objects using the resourceprovider given
        """
        self.debug_proxy = resourceprovider.debug_interface(self)
        self.hw = resourceprovider.pin_driver()
        self.board = resourceprovider.board_interface()

class DebugExecApiPic24Vx(PicDebugInterface):
    """
    Interaction with this particular implementation of the debug executive
    """
    # Useful Debug Executive commands
    DE_COMMAND_READ_VERSION = 0x02
    DE_COMMAND_READ_DATA = 0x03
    DE_COMMAND_WRITE_DATA = 0x04
    DE_COMMAND_READ_FLASH = 0x07
    DE_COMMAND_WRITE_FLASH = 0x08
    DE_COMMAND_READ_PC = 0x0D
    DE_COMMAND_RUN = 0x19
    DE_COMMAND_STEP = 0x1A
    DE_COMMAND_READ_EMU = 0x1C
    DE_COMMAND_WRITE_EMU = 0x1D

    def __init__(self):
        PicDebugInterface.__init__(self)

    @staticmethod
    def _de_command_3_2(param1, param2):
        """
        Header generator for a two parameter command
        """
        return bytearray([param1 & 0xFF, (param1 >> 8) & 0xFF, (param1 >> 16) & 0xFF, param2 & 0xFF, (param2 >> 8) & 0xFF])

    @staticmethod
    def _de_command_4_2(param1, param2):
        """
        Header generator for a two parameter command
        """
        return bytearray([param1 & 0xFF, (param1 >> 8) & 0xFF, (param1 >> 16) & 0xFF, (param1 >> 24) & 0xFF, param2 & 0xFF, (param2 >> 8) & 0xFF])

    def de_command_memory24_write(self, address, length):
        """
        Header generator for a memory write command
        """
        return self._de_command_3_2(address, length)

    def de_command_memory24_read(self, address, length):
        """
        Header generator for a memory read command
        """
        return self._de_command_3_2(address, length)

    def de_command_memory32_write(self, address, length):
        """
        Header generator for a memory write command
        """
        return self._de_command_4_2(address, length)

    def de_command_memory32_read(self, address, length):
        """
        Header generator for a memory read command
        """
        return self._de_command_4_2(address, length)

    def de_command_read_flash(self, address, numbytes):
        """
        Read flash: chunks of n bytes
        """
        return self.de_command_memory32_read(address, int(numbytes // self.de_read_flash_pack_size()))

    def de_read_flash_pack_size(self):
        """
        Read package size for flash is 12 bytes
        """
        return 12

    def read_de_version(self):
        """
        DE execute, no bytes in, 3 bytes back out
        Version format: major, minor, revision
        """
        self.debug_proxy.debug_command(self.DE_COMMAND_READ_VERSION, 0, 3)

    def read_ram(self, numbytes):
        """
        DE execute, 6 meta-data bytes sent, 0 bytes received)
        Meta-data bytes: addrL0, addrL1, addrH0, addrH1, bytesL, bytesH
        """
        self.debug_proxy.debug_command(self.DE_COMMAND_READ_DATA, 6, numbytes)

    def write_ram(self, numbytes):
        """
        DE execute, 6 meta-data bytes + n bytes sent, 0 bytes received)
        Meta-data bytes: addrL0, addrL1, addrH0, addrH1, bytesL, bytesH
        """
        self.debug_proxy.debug_command(self.DE_COMMAND_WRITE_DATA, numbytes + 6, 0)

    def read_emulation(self, numbytes):
        """
        DE execute, 5 meta-data bytes sent, 0 bytes received)
        Meta-data bytes: addrL0, addrL1, addrH0, wordsL, wordsH
        """
        self.debug_proxy.debug_command(self.DE_COMMAND_READ_EMU, 5, numbytes)

    def write_emulation(self, numbytes):
        """
        DE execute, 5 meta-data bytes + n bytes sent, 0 bytes received)
        Meta-data bytes: addrL0, addrL1, addrH0, wordsL, wordsH
        """
        self.debug_proxy.debug_command(self.DE_COMMAND_WRITE_EMU, numbytes + 5, 0)

    def debug_read_flash(self, numbytes):
        """
        DE execute, 6 meta-data bytes sent, n bytes received)
        Meta-data bytes: addrL0, addrL1, addrH0, addrH1, wordsL, wordsH
        """
        self.debug_proxy.debug_command(self.DE_COMMAND_READ_FLASH, 6, numbytes)

    def debug_write_flash(self, numbytes, delay):
        """
        DE execute, 4 meta-data bytes, 0 bytes received)
        Meta-data bytes: addrL0, addrL1, addrH0, addrH1
        """
        self.debug_proxy.debug_command(self.DE_COMMAND_WRITE_FLASH, 4, 0)
        # Delay while the page is erased
        self.board.delay_us(delay)
        # Write more data without command
        self.debug_proxy.debug_command(0, 576, 0)
        # Commit delay
        self.board.delay_us(delay)

    def read_pc(self):
        """
        DE execute, no data in, 3 bytes out
        Data out: PCL0, PCL1, PCH
        """
        self.debug_proxy.debug_command(self.DE_COMMAND_READ_PC, 0, 3)

    def step(self):
        """
        DE execute, no data
        """
        self.debug_proxy.debug_command(self.DE_COMMAND_STEP, 0, 0)

    def run(self):
        """
        DE execute, no data
        """
        self.debug_proxy.debug_command(self.DE_COMMAND_RUN, 0, 0)

    def get_run_state(self):
        """
        Get target run/stop state.
        Indirect return.
        """
        # First put pins to input
        self.hw.set_clk_in_data_in()
        # Read back pin values
        self.hw.get_pins()

    def halt(self):
        """
        HALT the target
        """
        # Drive low on clock and data
        self.hw.set_all_pins_low()
        # Bring clock high
        self.hw.set_clk_high_data_low()
        # Wait
        self.board.delay_us(100)
        # Drive low on clock and data
        self.hw.set_all_pins_low()
        # Both to input
        self.hw.set_clk_in_data_in()
        # Wait
        self.board.delay_us(100)

class DebugExecApiPic18Vx(PicDebugInterface):
    """
    Interaction with this particular implementation of the debug executive
    """
    # Useful Debug Executive commands
    DE_COMMAND_READ_VERSION = 0x01
    DE_COMMAND_READ_MEM = 0x02
    DE_COMMAND_WRITE_MEM = 0x03
    DE_COMMAND_READ_PC = 0x04
    DE_COMMAND_RUN = 0x05
    DE_COMMAND_STEP = 0x06
    DE_COMMAND_WRITE_EMU = 0x07
    DE_COMMAND_READ_EMU = 0x08
    # This Debug Executive version does not support the following commands:
    # DE_COMMAND_READ_FLASH = 0x09
    # DE_COMMAND_WRITE_FLASH = 0x0A
    # DE_COMMAND_READ_EEPROM = 0x0C
    # DE_COMMAND_WRITE_EEPROM = 0x0D
    # DE_COMMAND_READ_TEST = 0x0F
    # DE_COMMAND_WRITE_TEST = 0x10
    # DE_COMMAND_SET_PC = 0x11
    # DE_COMMAND_ERASE_PAGE = 0x0B

    def __init__(self):
        PicDebugInterface.__init__(self)

    @staticmethod
    def _de_command_1(param):
        """
        Header generator for a single parameter command
        """
        return bytearray([param & 0xFF, (param >> 8) & 0xFF])

    @staticmethod
    def _de_command_2(param1, param2):
        """
        Header generator for a two parameter command
        """
        return bytearray([param1 & 0xFF, (param1 >> 8) & 0xFF, param2 & 0xFF, (param2 >> 8) & 0xFF])

    def de_command_erase(self, address):
        """
        Header generator for an erase command
        """
        return self._de_command_1(address)

    def de_command_memory_write(self, address, length):
        """
        Header generator for a memory write command
        """
        return self._de_command_2(address, length)

    def de_command_memory_read(self, address, length):
        """
        Header generator for a memory read command
        """
        return self._de_command_2(address, length)

    def read_pc(self):
        """
        DE execute, no data in, 3 bytes out
        Data out: PCL, PCH
        """
        self.debug_proxy.debug_command(self.DE_COMMAND_READ_PC, 0, 3)

    def set_pc(self):
        """
        DE execute, 3 bytes data, 0 bytes back out
        Data bytes: PCL, PCH
        """
        self.debug_proxy.debug_command(self.DE_COMMAND_SET_PC, 3, 0)

    def read_mem(self, numbytes):
        """
        DE execute, 4 meta-data bytes sent, 0 bytes received)
        Meta-data bytes: addrL, addrH, bytesL, bytesH
        """
        self.debug_proxy.debug_command(self.DE_COMMAND_READ_MEM, 4, numbytes)

    def write_mem(self, numbytes):
        """
        DE execute, 4 meta-data bytes + n bytes sent, 0 bytes received)
        Meta-data bytes: addrL, addrH, bytesL, bytesH
        """
        self.debug_proxy.debug_command(self.DE_COMMAND_WRITE_MEM, numbytes + 4, 0)

    def read_de_version(self):
        """
        DE execute, no bytes in, 4 bytes back out
        Version format: FW_AP, major, minor, revision
        """
        self.debug_proxy.debug_command(self.DE_COMMAND_READ_VERSION, 0, 4)

    def read_emulation(self, numbytes):
        """
        DE execute, 4 meta-data bytes sent, 0 bytes received)
        Meta-data bytes: addrL, addrH, bytesL, bytesH
        """
        self.debug_proxy.debug_command(self.DE_COMMAND_READ_EMU, 4, numbytes)

    def write_emulation(self, numbytes):
        """
        DE execute, 4 meta-data bytes + n bytes sent, 0 bytes received)
        Meta-data bytes: addrL, addrH, bytesL, bytesH
        """
        self.debug_proxy.debug_command(self.DE_COMMAND_WRITE_EMU, numbytes + 4, 0)

    def step(self):
        """
        DE execute, no data
        """
        self.debug_proxy.debug_command(self.DE_COMMAND_STEP, 0, 0)

    def run(self):
        """
        DE execute, no data
        """
        self.debug_proxy.debug_command(self.DE_COMMAND_RUN, 0, 0)
        self.board.delay_ms(100)

    def halt(self):
        """
        HALT the target
        """
        # Drive low on clock and data
        self.hw.set_all_pins_low()
        # Bring clock high
        self.hw.set_clk_high_data_low()
        # Wait
        self.board.delay_us(100)
        # Drive low on clock and data
        self.hw.set_all_pins_low()
        # Both to input
        self.hw.set_clk_in_data_in()
        # Wait
        self.board.delay_us(100)

    def get_run_state(self):
        """
        Get target run/stop state.
        Indirect return.
        """
        # First put pins to input
        self.hw.set_clk_in_data_in()
        # Read back pin values
        self.hw.get_pins()

    def is_halted(self):
        """
        Is the target halted.
        Boolean return
        """
        self.hw.set_clk_in_data_in()
        # Check the pin status
        status = self.hw.get_pins()
        if status & (1 << ICSP_CLK_VALUE_ID):
            return True
        return False

class DebugExecApiVx(PicDebugInterface):
    """
    Interaction with this particular implementation of the debug executive
    """
    # Useful Debug Executive commands
    DE_COMMAND_READ_VERSION = 0x01
    DE_COMMAND_READ_MEM = 0x02
    DE_COMMAND_WRITE_MEM = 0x03
    DE_COMMAND_READ_PC = 0x04
    DE_COMMAND_RUN = 0x05
    DE_COMMAND_STEP = 0x06
    DE_COMMAND_READ_FLASH = 0x09
    DE_COMMAND_WRITE_FLASH = 0x0A
    DE_COMMAND_READ_EEPROM = 0x0C
    DE_COMMAND_WRITE_EEPROM = 0x0D
    DE_COMMAND_READ_TEST = 0x0F
    DE_COMMAND_WRITE_TEST = 0x10
    DE_COMMAND_SET_PC = 0x11
    DE_COMMAND_ERASE_PAGE = 0x0B

    def __init__(self):
        PicDebugInterface.__init__(self)

    @staticmethod
    def _de_command_1(param):
        """
        Header generator for a single parameter command
        """
        return bytearray([param & 0xFF, (param >> 8) & 0xFF])

    @staticmethod
    def _de_command_2(param1, param2):
        """
        Header generator for a two parameter command
        """
        return bytearray([param1 & 0xFF, (param1 >> 8) & 0xFF, param2 & 0xFF, (param2 >> 8) & 0xFF])

    def de_command_set_pc(self, pc):
        """
        Header generator for a set PC command
        """
        return self._de_command_1(pc)

    def de_command_erase(self, address):
        """
        Header generator for an erase command
        """
        return self._de_command_1(address)

    def de_command_memory_write(self, address, length):
        """
        Header generator for a memory write command
        """
        return self._de_command_2(address, length)

    def de_command_memory_read(self, address, length):
        """
        Header generator for a memory read command
        """
        return self._de_command_2(address, length)

    def read_pc(self):
        """
        DE execute, no data in, 2 bytes out
        Data out: PCL, PCH
        """
        self.debug_proxy.debug_command(self.DE_COMMAND_READ_PC, 0, 2)

    def set_pc(self):
        """
        DE execute, 2 bytes data, 0 bytes back out
        Data bytes: PCL, PCH
        """
        self.debug_proxy.debug_command(self.DE_COMMAND_SET_PC, 2, 0)

    def read_mem(self, numbytes):
        """
        DE execute, 4 meta-data bytes sent, 0 bytes received)
        Meta-data bytes: addrL, addrH, bytesL, bytesH
        """
        self.debug_proxy.debug_command(self.DE_COMMAND_READ_MEM, 4, numbytes)

    def write_mem(self, numbytes):
        """
        DE execute, 4 meta-data bytes + n bytes sent, 0 bytes received)
        Meta-data bytes: addrL, addrH, bytesL, bytesH
        """
        self.debug_proxy.debug_command(self.DE_COMMAND_WRITE_MEM, numbytes + 4, 0)

    def read_de_version(self):
        """
        DE execute, no bytes in, 4 bytes back out
        Version format: FW_AP, major, minor, revision
        """
        self.debug_proxy.debug_command(self.DE_COMMAND_READ_VERSION, 0, 4)

    def debug_erase_page(self, delay):
        """
        DE execute, 2 meta-data bytes sent, 0 bytes received
        Meta-data bytes: addrL, addrH
        """
        self.debug_proxy.debug_command(self.DE_COMMAND_ERASE_PAGE, 2, 0)
        self.board.delay_us(delay)

    def debug_read_flash(self, numbytes):
        """
        DE execute, 4 meta-data bytes sent, n bytes received)
        Meta-data bytes: addrL, addrH, bytesL, bytesH
        """
        self.debug_proxy.debug_command(self.DE_COMMAND_READ_FLASH, 4, numbytes)

    def debug_read_test(self, numbytes):
        """
        DE execute, 4 meta-data bytes sent, n bytes received)
        Meta-data bytes: addrL, addrH, bytesL, bytesH
        """
        self.debug_proxy.debug_command(self.DE_COMMAND_READ_TEST, 4, numbytes)

    def debug_read_eeprom(self, numbytes):
        """
        DE execute, 4 meta-data bytes sent, n bytes received)
        Meta-data bytes: addrL, addrH, bytesL, bytesH
        """
        self.debug_proxy.debug_command(self.DE_COMMAND_READ_EEPROM, 4, numbytes)

    def debug_write_flash(self, numbytes, delay):
        """
        DE execute, 4 meta-data bytes + n bytes sent, 0 bytes received)
        Meta-data bytes: addrL, addrH, bytesL, bytesH
        """
        self.debug_proxy.debug_command(self.DE_COMMAND_WRITE_FLASH, numbytes + 4, 0)
        # Delay while the page is written
        self.board.delay_us(delay)

    def step(self):
        """
        DE execute, no data
        """
        self.debug_proxy.debug_command(self.DE_COMMAND_STEP, 0, 0)

    def run(self):
        """
        DE execute, no data
        """
        self.debug_proxy.debug_command(self.DE_COMMAND_RUN, 0, 0)
        self.board.delay_ms(100)

    def halt(self):
        """
        HALT the target
        """
        # Drive low on clock and data
        self.hw.set_all_pins_low()
        # Bring clock high
        self.hw.set_clk_high_data_low()
        # Wait
        self.board.delay_us(100)
        # Drive low on clock and data
        self.hw.set_all_pins_low()
        # Both to input
        self.hw.set_clk_in_data_in()
        # Wait
        self.board.delay_us(100)

    def get_run_state(self):
        """
        Get target run/stop state.
        Indirect return.
        """
        # First put pins to input
        self.hw.set_clk_in_data_in()
        # Read back pin values
        self.hw.get_pins()

    def is_halted(self):
        """
        Is the target halted.
        Boolean return
        """
        self.hw.set_clk_in_data_in()
        # Check the pin status
        status = self.hw.get_pins()
        if status & (1 << ICSP_CLK_VALUE_ID):
            return True
        return False
