"""

Python PIC model for device:
    pic18f47k42

"""
# Import PIC device class and its stack
from common.picdevice import *


class DeviceDefinition(PicDevice):
    """
        PIC device definition
    """

    # ICSP interface clock period in nano seconds
    ICSP_CLOCK_PERIOD_NS = 200

    # Debugger model specifies how the Python stack interacts with the debugger over USB
    DEBUGGER_MODEL = PythonScriptedPic18Debugger
    # Programming interface specifies how the debugger tool interacts with the target device
    PROGRAMMING_INTERFACE = ProgInterfaceIcspC8D24
    # Debugging interface specifies how the debugger tool interacts with the debug executive
    DEBUGGING_INTERFACE = DebugExecApiPic18Vx

    # Flash properties for this device
    FLASH_WRITE_BYTES_PER_PAGE = 128

    # ICSP programming command-set for this device. Commands from programming spec.
    LOAD_PC_COMMAND = 0x80
    BULK_ERASE_COMMAND = 0x18
    ROW_ERASE_COMMAND = 0xF0
    LOAD_DATA_NVM_COMMAND = 0x00
    LOAD_DATA_NVM_INC_COMMAND = 0x02
    READ_DATA_NVM_COMMAND = 0xFC
    READ_DATA_NVM_INC_COMMAND = 0xFE
    ADDRESS_INC = 0xF8
    INTERNALLY_TIMED_PROG_COMMAND = 0xE0
    INCREMENT_ADDRESS_COMMAND = 0xF8

    # Extra commands for DE access
    MAE_COMMAND = 0xC4
    MAE_IEDE = 0x006355
    MAE_DELAY_MS = 3

    # Delays for internally timed programming
    BULK_ERASE_DELAY_US = 25200
    ROW_ERASE_DELAY_US = 2800
    PAGE_PROGRAMMING_DELAY_US = 2800
    WRITE_CONFIG_WORD_DELAY_US = 5600
    DE_ERASE_DELAY_US = 14000
    EEPROM_PROGRAMMING_DELAY_US = WRITE_CONFIG_WORD_DELAY_US
    ID_PROGRAMMING_DELAY_US = WRITE_CONFIG_WORD_DELAY_US
    WRITE_DE_PAGE_DELAY_US = WRITE_CONFIG_WORD_DELAY_US

    # ICSP command level timing
    TDLY_US = 1

    # Program counter/address values
    DEFAULT_ADDRESS_FOR_BULK_ERASE_B = 0x300000 # This will erase Flash, Configuration words, User ID and EEPROM (if EEPROM is not protected by config bits)
    DEVICE_ID_ADDRESS_B = 0x3FFFFE

    def __init__(self):
        PicDevice.__init__(self)

    def enter_tmod(self):
        """
        Enter TMOD.
        Puts the PIC device into its "Programming mode"
        """
        # MCLR high, wait
        self.hw.set_mclr_high()
        self.board.delay_ms(100)

        # ICSP pins low
        self.hw.set_all_pins_low()

        # MCLR low, wait
        self.hw.set_mclr_low()
        self.board.delay_ms(100)

        # Send the MCHP string, backwards
        self.prog.write_string_literal('MCHP'[::-1])

    def exit_tmod(self):
        # MCLR back high
        self.hw.set_mclr_high()
        # And wait
        self.board.delay_ms(100)

    def hold_in_reset(self):
        # Tristate
        self.hw.set_clk_in_data_in()
        # MCLR low
        self.hw.set_mclr_low()

    def release_from_reset(self):
        # Tristate
        self.hw.set_clk_in_data_in()
        # MCLR high
        self.hw.set_mclr_high()

    def read_id(self):
        """
        Read the device ID from the PIC
        """
        # Set address to configuration space
        self.prog.command(self.LOAD_PC_COMMAND)
        self.prog.payload(self.DEVICE_ID_ADDRESS_B)
        # Read a word from NVM
        self.prog.command(self.READ_DATA_NVM_COMMAND)
        device_id = self.prog.read_data_word()
        return device_id

    def bulk_erase(self, byte_address=None):
        """
        Bulk erase basd on given address
        :param byte_address: address for the bulk erase, see programming spec for the target device for info on which memory sections will be erased
        """
        if byte_address is None:
            byte_address=self.DEFAULT_ADDRESS_FOR_BULK_ERASE_B

        # Set address to configuration space
        self.prog.command(self.LOAD_PC_COMMAND)
        self.prog.payload(byte_address)

        # Internally timed erase command
        self.prog.command(self.BULK_ERASE_COMMAND)
        self.board.delay_us(self.BULK_ERASE_DELAY_US)

    def write_flash_page(self, byte_address, words):
        """
        Write one flash page to the PIC
        :param byte_address: start address of the page to write
        :param words: number of words to write
        Data is taken indirectly from the data buffer
        """
        self.prog.command(self.LOAD_PC_COMMAND)
        self.prog.payload(byte_address)

        # Loop through all but the last word
        for word in range(words - 1):
            self.prog.command(self.LOAD_DATA_NVM_INC_COMMAND)
            self.prog.write_data_word()

        # Write last word with no increment
        self.prog.command(self.LOAD_DATA_NVM_COMMAND)
        self.prog.write_data_word()

        # Timed flash programming procedure
        self.prog.command(self.INTERNALLY_TIMED_PROG_COMMAND)
        self.board.delay_us(self.PAGE_PROGRAMMING_DELAY_US)

    def read_flash(self, byte_address, words):
        """
        Reads a block of flash from the PIC
        :param byte_address: start address to read from
        :param words: number of words to read
        Data is sent indirectly to the data buffer
        """
        # Set the address to read from
        self.prog.command(self.LOAD_PC_COMMAND)
        self.prog.payload(byte_address)
        # Loop through range, reading words
        for word in range(words):
            self.prog.command(self.READ_DATA_NVM_INC_COMMAND)
            self.prog.read_data_word()

    def read_config_word(self, byte_address):
        """
        Reads one config word from config space.
        :param byte_address: address of the word
        :return:
        """
        self.read_flash(byte_address, 1)

    def write_config_word(self, byte_address):
        """
        Writes one word to the config space
        :param byte_address: byte address to write
        :return:
        """
        # Set the address to write to
        self.prog.command(self.LOAD_PC_COMMAND)
        self.prog.payload(byte_address)
        # Write data into NVM
        self.prog.command(self.LOAD_DATA_NVM_COMMAND)
        self.prog.write_data_word()
        # Internally timed write procedure
        self.prog.command(self.INTERNALLY_TIMED_PROG_COMMAND)
        self.board.delay_us(self.WRITE_CONFIG_WORD_DELAY_US)

    def write_user_id_word(self, byte_address):
        """
        Writes one word to the user ID space
        :param byte_address: byte address to write
        :return:
        """
        # Set the address to write to
        self.prog.command(self.LOAD_PC_COMMAND)
        self.prog.payload(byte_address)
        # Write data into NVM
        self.prog.command(self.LOAD_DATA_NVM_COMMAND)
        self.prog.write_data_word()
        # Internally timed write procedure
        self.prog.command(self.INTERNALLY_TIMED_PROG_COMMAND)
        self.board.delay_us(self.ID_PROGRAMMING_DELAY_US)

    def write_eeprom(self, byte_address, numbytes):
        """
        Writes bytes of data to EEPROM
        :param byte_address: start address to write
        :param numbytes: number of bytes to write
        """
        # Set the address to write to
        self.prog.command(self.LOAD_PC_COMMAND)
        self.prog.payload(byte_address)
        # Loop through range
        for value in range(numbytes):
            # Write byte with internally timed write
            self.prog.command(self.LOAD_DATA_NVM_COMMAND)
            self.prog.write_data_byte()
            self.prog.command(self.INTERNALLY_TIMED_PROG_COMMAND)
            self.board.delay_us(self.EEPROM_PROGRAMMING_DELAY_US)
            # Increment address
            self.prog.command(self.ADDRESS_INC)

    def read_eeprom(self, byte_address, numbytes):
        """
        Reads bytes of data from EEPROM
        :param byte_address: start address to read
        :param numbytes: number of bytes to read
        """
        # Set the address to read from
        self.prog.command(self.LOAD_PC_COMMAND)
        self.prog.payload(byte_address)
        # Loop through range, reading bytes
        for value in range(numbytes):
            self.prog.command(self.READ_DATA_NVM_INC_COMMAND)
            self.prog.read_data_byte()

    def enter_debug(self):
        """
        Enters DEBUG state on the PIC
        Note: The Debug Executive must be in place first!
        """
        # MCLR low
        self.hw.set_mclr_low()
        self.board.delay_ms(100)
        # ICSP pins low
        self.hw.set_all_pins_low()
        # MCLR high
        self.hw.set_mclr_high()
        self.board.delay_ms(100)
        # ICSP input
        self.hw.set_clk_in_data_in()
        # MCLR low
        self.hw.set_mclr_low()
        self.board.delay_ms(100)
        # MCLR high
        self.hw.set_mclr_high()
        self.board.delay_ms(100)

    def erase_de(self, byte_address, words):
        """
        Erase the Debug Executive
        """
        self.prog.command(self.LOAD_PC_COMMAND)
        self.prog.payload(byte_address)
        self.enable_de_access()

        # Internally timed erase command
        self.prog.command(self.BULK_ERASE_COMMAND)
        self.board.delay_us(self.DE_ERASE_DELAY_US)

    def enable_de_access(self):
        """
        Enable access to the Debug Executive memory
        """
        self.prog.command(self.MAE_COMMAND)
        self.prog.payload(self.MAE_IEDE)
        self.board.delay_ms(self.MAE_DELAY_MS)

    def write_de_page(self, byte_address, words):
        """
        Write a page of the Debug Executive
        """
        # Set the address to write to
        self.prog.command(self.LOAD_PC_COMMAND)
        self.prog.payload(byte_address)
        self.enable_de_access()

        # Loop through all but the last word
        for word in range(words - 1):
            self.prog.command(self.LOAD_DATA_NVM_INC_COMMAND)
            self.prog.write_data_word()

        # Write last word with no increment
        self.prog.command(self.LOAD_DATA_NVM_COMMAND)
        self.prog.write_data_word()

        # Timed flash programming procedure
        self.prog.command(self.INTERNALLY_TIMED_PROG_COMMAND)
        self.board.delay_us(self.WRITE_DE_PAGE_DELAY_US)
