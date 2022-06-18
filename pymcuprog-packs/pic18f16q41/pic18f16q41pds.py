"""

Python PIC model for device:
    pic18f16q41

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
    READ_DATA_NVM_COMMAND = 0xFC
    READ_DATA_NVM_INC_COMMAND = 0xFE
    WRITE_DATA_NVM_COMMAND = 0xC0
    WRITE_DATA_NVM_INC_COMMAND = 0xE0
    INCREMENT_ADDRESS_COMMAND = 0xF8

    # Extra commands for DE access
    MAE_COMMAND = 0xC4
    MAE_IEDE = 0x006355

    # Delays for internally timed programming
    BULK_ERASE_DELAY_US = 11000
    ROW_ERASE_DELAY_US = 11000
    WRITE_EEPROM_DELAY_US = 11000
    WRITE_CONFIG_DELAY_US = WRITE_EEPROM_DELAY_US
    WRITE_PROGRAM_DELAY_US = 75
    WRITE_USER_ID_DELAY_US = WRITE_PROGRAM_DELAY_US
    WRITE_DE_DELAY_US = WRITE_PROGRAM_DELAY_US

    # ICSP command level timing
    TDLY_US = 1

    # Program counter/address values
    DEVICE_ID_ADDRESS_B = 0x3FFFFE

    # Bulk erase bitfields
    EEPROM_MEMORY = 0x01
    PROGRAM_MEMORY = 0x02
    USER_ID_MEMORY = 0x04
    CONFIG_MEMORY = 0x08
    ICD_MEMORY = 0x10

    def __init__(self):
        PicDevice.__init__(self)

    def enter_tmod(self):
        """
        Enter TMOD.
        Puts the PIC device into its "Programming mode"
        """
        # MCLR high, wait
        self.hw.set_mclr_high()
        self.board.delay_ms(1)

        # ICSP pins low
        self.hw.set_all_pins_low()

        # MCLR low, wait
        self.hw.set_mclr_low()
        self.board.delay_ms(1)

        # Send the MCHP string, backwards
        self.prog.write_string_literal('MCHP'[::-1])
        self.board.delay_ms(1)

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
        Bulk erase
        Erases EEPROM, program memory, config memory and user ID memory
        :param byte_address: not used but kept for API compatibility
        """
        # Set address to configuration space
        self.prog.command(self.BULK_ERASE_COMMAND)
        self.prog.payload(self.EEPROM_MEMORY | self.PROGRAM_MEMORY | self.CONFIG_MEMORY | self.USER_ID_MEMORY)

        # Internally timed erase command
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

        for word in range(words):
            self.prog.command(self.WRITE_DATA_NVM_INC_COMMAND)
            self.prog.write_data_word()
            self.board.delay_us(self.WRITE_PROGRAM_DELAY_US)

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
        self.prog.command(self.WRITE_DATA_NVM_INC_COMMAND)
        self.prog.write_data_byte()
        # Internally timed write procedure
        self.board.delay_us(self.WRITE_CONFIG_DELAY_US)
        # Write data into NVM
        self.prog.command(self.WRITE_DATA_NVM_COMMAND)
        self.prog.write_data_byte()
        self.board.delay_us(self.WRITE_CONFIG_DELAY_US)

    def read_config_word(self, byte_address):
        """
        Reads one config word from config space. This device has byte access
        to the config memory so two byte reads will be done to get the word.
        :param byte_address: address of the word
        :return:
        """
        # Set the address
        self.prog.command(self.LOAD_PC_COMMAND)
        self.prog.payload(byte_address)
        # Read first byte
        self.prog.command(self.READ_DATA_NVM_INC_COMMAND)
        self.prog.read_data_byte()
        # Read second byte
        self.prog.command(self.READ_DATA_NVM_COMMAND)
        self.prog.read_data_byte()

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
        self.prog.command(self.WRITE_DATA_NVM_COMMAND)
        self.prog.write_data_word()
        # Internally timed write procedure
        self.board.delay_us(self.WRITE_USER_ID_DELAY_US)

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
            # Write data into NVM
            self.prog.command(self.WRITE_DATA_NVM_INC_COMMAND)
            self.prog.write_data_byte()
            # Internally timed write procedure
            self.board.delay_us(self.WRITE_EEPROM_DELAY_US)

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
        self.enable_de_access()

        # Internally timed erase command
        self.prog.command(self.BULK_ERASE_COMMAND)
        self.prog.payload(self.ICD_MEMORY)
        self.board.delay_us(self.BULK_ERASE_DELAY_US)

    def enable_de_access(self):
        """
        Enable access to the Debug Executive memory
        """
        self.prog.command(self.MAE_COMMAND)
        self.prog.payload(self.MAE_IEDE)

    def write_de_page(self, byte_address, words):
        """
        Write a page of the Debug Executive
        """
        # Set the address to write to
        self.prog.command(self.LOAD_PC_COMMAND)
        self.prog.payload(byte_address)

        for word in range(words):
            self.enable_de_access()
            self.prog.command(self.WRITE_DATA_NVM_INC_COMMAND)
            self.prog.write_data_word()
            self.board.delay_us(self.WRITE_DE_DELAY_US)
