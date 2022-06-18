"""

Python PIC model for device:
    pic16f1768

"""
# Import PIC device class and its stack
from common.picdevice import *


class DeviceDefinition(PicDevice):
    """
        PIC device definition
    """

    # Debugger model specifies how the Python stack interacts with the debugger over USB
    DEBUGGER_MODEL = PythonScriptedPic16Debugger
    # Programming interface specifies how the debugger tool interacts with the target device
    PROGRAMMING_INTERFACE = ProgInterfaceIcspC6D16
    # Debugging interface specifies how the debugger tool interacts with the debug executive
    DEBUGGING_INTERFACE = DebugExecApiVx

    # Flash properties for this device
    FLASH_WRITE_BYTES_PER_PAGE = 64

    # ICSP programming command-set for this device. Commands from programming spec.
    LOAD_CONFIGURATION = 0x00
    LOAD_DATA_FOR_PROGRAM_MEMORY = 0x02
    READ_DATA_FROM_PROGRAM_MEMORY = 0x04
    INCREMENT_ADDRESS = 0x06
    RESET_ADDRESS = 0x16
    BEGIN_INTERNALLY_TIMED_PROGRAMMING = 0x08
    BEGIN_EXTERNALLY_TIMED_PROGRAMMING = 0x18
    END_EXTERNALLY_TIMED_PROGRAMMING = 0x0A
    BULK_ERASE_PROGRAM_MEMORY = 0x09  # Internally timed
    ROW_ERASE_PROGRAM_MEMORY = 0x11  # Internally timed

    # Extra commands for DE access
    MAE_COMMAND = 0x0E
    MAE_IEDE = (0x63AA >> 1)

    # Delays for internally timed programming
    BULK_ERASE_DELAY_US = 5000
    ROW_ERASE_DELAY_US = 2500
    PROGRAM_MEMORY_DELAY_US = 2500
    PROGRAM_CONFIG_WORDS_DELAY_US = 5000

    # PAGE_PROGRAMMING_DELAY_US must be defined for SWBPs
    PAGE_PROGRAMMING_DELAY_US = PROGRAM_MEMORY_DELAY_US

    # Programming spec TENTH parameter
    TMOD_ENTRY_HOLD_TIME_US = 250
    # Programming spec TEXIT parameter
    TMOD_EXIT_DELAY_US = 1

    # ICSP command level timing
    TDLY_US = 1

    # Program counter/address values (byte addresses)
    USER_MEMORY_ADDRESS_B = 0x0000
    CONFIG_MEMORY_ADDRESS_B = 0x10000 # Word address: 0x8000
    ICD_INSTRUCTION_ADDRESS_B = 0x10008 # Word address: 0x8004
    DEVICE_ID_ADDRESS_B = 0x1000C # Word address: 0x8006
    DE_MEM2_B = 0x10200 # Word address: 0x8100
    # Used for data phases which are 'not used'
    DUMMY_ADDRESS = 0x3FFF

    # GOTO instruction with relative address 0x20 shifted by one to get stop bit
    ICD_INSTRUCTION = (0x2820 << 1)

    def __init__(self):
        PicDevice.__init__(self)
        # This PIC has no set_address() function available, but relies on pure increments with reset back to start
        # The last_address_b value is thus cached so that the Python model can keep track of the address in the device
        self.last_address_b = -1

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
        self.board.delay_us(self.TMOD_ENTRY_HOLD_TIME_US)

        # Send the MCHP string
        self.prog.write_string_literal('MCHP'[::-1])

        # Toggle clock once
        self.hw.set_clk()
        self.hw.clr_clk()

    def exit_tmod(self):
        """
        Exit TMOD
        """
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
        self.prog.command(self.LOAD_CONFIGURATION)
        self.prog.payload(self.DUMMY_ADDRESS)

        # Step to device ID address
        # PIC16 devices uses word adressing so only one increment per word please
        for _ in range((self.DEVICE_ID_ADDRESS_B - self.CONFIG_MEMORY_ADDRESS_B) // 2):
            self.prog.command(self.INCREMENT_ADDRESS)

        # Update address pointer
        self.last_address_b = self.DEVICE_ID_ADDRESS_B

        # Read data word
        self.prog.command(self.READ_DATA_FROM_PROGRAM_MEMORY)
        self.prog.read_data_word()


    def bulk_erase(self, byte_address):
        """
        Erase the entire flash area
        :param byte_address: address for the bulk erase, see programming spec for the target device for info on which memory sections will be erased
        TODO implement byte_address usage
        """

        # Set address to configuration space
        self.prog.command(self.LOAD_CONFIGURATION)
        self.prog.payload(self.DUMMY_ADDRESS)

        # Internally timed erase command
        self.prog.command(self.BULK_ERASE_PROGRAM_MEMORY)
        self.board.delay_us(self.BULK_ERASE_DELAY_US)

        # Invalidate address pointer
        self.last_address_b = -1

    def write_flash_page(self, byte_address, words):
        """
        Write one flash page to the PIC
        :param byte_address: start address of the page to write
        :param words: number of words to write
        Data is taken indirectly from the data buffer
        """
        # Check if the address pointer needs to move
        if self.last_address_b != byte_address or self.last_address_b > byte_address:
            # Reset to flash start
            self.prog.command(self.RESET_ADDRESS)
            # PIC16 devices takes word address
            self.last_address_b = self.USER_MEMORY_ADDRESS_B // 2

        # If needed: increment address until we get to the word we want to write
        if byte_address != self.last_address_b:
            # PIC16 devices are using word addressing so only one increment per word please
            for _ in range(byte_address // 2):
                self.prog.command(self.INCREMENT_ADDRESS)
                # Increment by 2 since the PIC16 devices uses word addressing while we use byte addressing
                self.last_address_b += 2

        # Loop through all but the last word
        for _ in range(words-1):
            self.prog.command(self.LOAD_DATA_FOR_PROGRAM_MEMORY)
            self.prog.write_data_word()
            self.prog.command(self.INCREMENT_ADDRESS)

        # Write last word in row
        self.prog.command(self.LOAD_DATA_FOR_PROGRAM_MEMORY)
        self.prog.write_data_word()

        # Timed flash programming procedure
        self.prog.command(self.BEGIN_INTERNALLY_TIMED_PROGRAMMING)
        self.board.delay_us(self.PROGRAM_MEMORY_DELAY_US)

        # Increment address for next row
        self.prog.command(self.INCREMENT_ADDRESS)

        # Update address pointer
        self.last_address_b += words * 2

    def read_flash(self, byte_address, words):
        """
        Reads a block of flash from the PIC
        :param byte_address: start address to read from
        :param words: number of words to read
        Data is sent indirectly to the data buffer
        """
        # Check if the address pointer needs to move
        if self.last_address_b != byte_address or self.last_address_b > byte_address:
            # Which range to read: user or config?
            if byte_address >= self.CONFIG_MEMORY_ADDRESS_B:
                # Reset to config
                self.prog.command(self.LOAD_CONFIGURATION)
                self.prog.payload(self.DUMMY_ADDRESS)
                self.last_address_b = self.CONFIG_MEMORY_ADDRESS_B
            else:
                # Reset to flash start
                self.prog.command(self.RESET_ADDRESS)
                self.last_address_b = self.USER_MEMORY_ADDRESS_B

        # If needed: increment address until we get to the word we want to read
        if byte_address != self.last_address_b:
            # PIC16 is word addressed so only one increment per word please
            for _ in range((byte_address - self.last_address_b) // 2):
                self.prog.command(self.INCREMENT_ADDRESS)
                # PIC16 devices uses word addressing so only one increment per word please
                self.last_address_b += 2

        # Loop through range, reading words
        for _ in range(words):
            self.prog.command(self.READ_DATA_FROM_PROGRAM_MEMORY)
            self.prog.read_data_word()
            self.prog.command(self.INCREMENT_ADDRESS)

        # Update address pointer
        self.last_address_b += words * 2

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
        # Set the address to configuration memory
        self.prog.command(self.LOAD_CONFIGURATION)
        self.prog.payload(self.DUMMY_ADDRESS)

        # Increment address until we get to the word we want to write
        # PIC16 devices uses word addressing mode so only one increment per word please
        for _ in range((byte_address - self.CONFIG_MEMORY_ADDRESS_B) // 2):
            self.prog.command(self.INCREMENT_ADDRESS)

        # Write data into NVM
        self.prog.command(self.LOAD_DATA_FOR_PROGRAM_MEMORY)
        self.prog.write_data_word()

        # Internally timed write procedure
        self.prog.command(self.BEGIN_INTERNALLY_TIMED_PROGRAMMING)
        self.board.delay_us(self.PROGRAM_CONFIG_WORDS_DELAY_US)

        # Invalidate address pointer
        self.last_address_b = -1

    def write_user_id_word(self, byte_address):
        """
        Writes one word to the user_id space
        :param byte_address: byte address to write
        :return:
        """
        # Identical to write config words
        self.write_config_word(byte_address)


    def write_debug_vector(self):
        """
        Writes the debug vector (literal)
        """

        # Enter programming mode
        self.enter_tmod()

        # Set address to configuration space
        self.prog.command(self.LOAD_CONFIGURATION)
        self.prog.payload(self.DUMMY_ADDRESS)

        # Increment address until we get to the word we want to write
        # PIC16 devices uses word addressing mode so only one increment per word please
        for _ in range((self.ICD_INSTRUCTION_ADDRESS_B - self.CONFIG_MEMORY_ADDRESS_B) // 2):
            self.prog.command(self.INCREMENT_ADDRESS)

        # Write literal
        self.prog.command(self.LOAD_DATA_FOR_PROGRAM_MEMORY)
        self.prog.payload(self.ICD_INSTRUCTION)

        # Commit to flash
        self.prog.command(self.BEGIN_INTERNALLY_TIMED_PROGRAMMING)
        self.board.delay_us(self.PROGRAM_CONFIG_WORDS_DELAY_US)

        # Invalidate address pointer
        self.last_address_b = -1

        # Leave programming mode
        self.exit_tmod()

    def enter_debug(self):
        """
        Enters DEBUG state on the PIC
        Note: The Debug Executive must be in place first!
        """
        # Put the debug vector in place
        self.write_debug_vector()

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
        # Reset to config
        self.prog.command(self.LOAD_CONFIGURATION)
        self.prog.payload(self.DUMMY_ADDRESS)

        # If needed: increment address until we get to the word we want to erase
        if byte_address != self.CONFIG_MEMORY_ADDRESS_B:
            # PIC16 devices uses word addressing mode so only one increment per word please
            for _ in range((byte_address - self.CONFIG_MEMORY_ADDRESS_B) // 2):
                self.prog.command(self.INCREMENT_ADDRESS)

        # Erase
        self.prog.command(self.BULK_ERASE_PROGRAM_MEMORY)
        self.board.delay_us(self.BULK_ERASE_DELAY_US)

        # Erase the next section?
        if byte_address + words*2 >= self.DE_MEM2_B:
            # Reset back to config
            self.prog.command(self.LOAD_CONFIGURATION)
            self.prog.payload(self.DUMMY_ADDRESS)

            # Move PC
            # PIC16 devices uses word addressing mode so only one increment per word please
            for _ in range((self.DE_MEM2_B - self.CONFIG_MEMORY_ADDRESS_B) // 2):
                self.prog.command(self.INCREMENT_ADDRESS)

            # Enable region
            self.prog.command(self.MAE_COMMAND)
            self.prog.payload(self.MAE_IEDE)

            # Erase
            self.prog.command(self.BULK_ERASE_PROGRAM_MEMORY)
            self.board.delay_us(self.BULK_ERASE_DELAY_US)

        # Invalidate address pointer
        self.last_address_b = -1

    def write_de_page(self, byte_address, words):
        """
        Write a page of the Debug Executive
        """
        # Reset to config
        self.prog.command(self.LOAD_CONFIGURATION)
        self.prog.payload(self.DUMMY_ADDRESS)

        # If needed: increment address until we get to the word we want to write
        if byte_address != self.CONFIG_MEMORY_ADDRESS_B:
            # PIC16 devices uses word addressing mode so only one increment per word please
            for _ in range((byte_address - self.CONFIG_MEMORY_ADDRESS_B) // 2):
                self.prog.command(self.INCREMENT_ADDRESS)

        if byte_address >= self.DE_MEM2_B:
            # Enable region
            self.prog.command(self.MAE_COMMAND)
            self.prog.payload(self.MAE_IEDE)

        for _ in range(words-1):
            self.prog.command(self.LOAD_DATA_FOR_PROGRAM_MEMORY)
            self.prog.write_data_word()
            self.prog.command(self.INCREMENT_ADDRESS)

        # Write last word in row
        self.prog.command(self.LOAD_DATA_FOR_PROGRAM_MEMORY)
        self.prog.write_data_word()

        # Timed flash programming procedure
        self.prog.command(self.BEGIN_INTERNALLY_TIMED_PROGRAMMING)
        self.board.delay_us(self.PROGRAM_CONFIG_WORDS_DELAY_US)

        # Increment address for next row
        self.prog.command(self.INCREMENT_ADDRESS)

        # Invalidate address pointer
        self.last_address_b = -1
