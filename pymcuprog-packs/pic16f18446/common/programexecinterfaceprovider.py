"""
ProgramExecInterfaceProvider

Provides Programming Executive (PE) interface using primitives
"""
import logging

# primitiveutils
from primitiveutils import PrimitiveException

from gen4scriptwrapper import pic24_decompact, pic24_compact

# Data type helpers
from pyedbglib.util import binary

class ProgExecInterfacePic24(object):
    """
    PIC 16-bit Programming Executive variant
    """

    # Useful Programming Executive commands
    PE_COMMAND_SCHECK = 0x0 # Sanity check
    PE_COMMAND_READC = 0x1 # Read 8-bit word from Configuration register or Device ID register
    PE_COMMAND_READP = 0x2 # Read N 24-bit instruction words
    PE_COMMAND_PROGP = 0x5 # Program and verify flash page
    PE_COMMAND_ERASEB = 0x7 # Chip erase
    PE_COMMAND_QVER = 0xB # Query PE version

    # Programming Executive response statuses
    PE_STATUS_PASS = 0x1
    PE_STATUS_FAIL = 0x2
    PE_STATUS_NACK = 0x3

    # Programming Executive error codes
    PE_ERROR_NONE = 0x0
    PE_ERROR_VERIFY_FAILED = 0x1
    PE_ERROR_UNKNOWN = 0x2

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.pe_proxy = None
        self.hw = None
        self.board = None

    def initialise(self, resourceprovider):
        """
        Creates objects using the resourceprovider given
        """
        self.pe_proxy = resourceprovider.program_exec_interface()
        self.hw = resourceprovider.pin_driver()
        self.board = resourceprovider.board_interface()

    @staticmethod
    def _pe_command(command, length):
        """
        Header generator for PE command
        """
        return ((command << 12) & 0xF000) + (length & 0x0FFF)

    def _sanity_check_proxy_command(self):
        """
        Run sanity check agains Programming Executive (PE) o check that PE communication is functioning
        """
        self.pe_proxy.send_word(self._pe_command(self.PE_COMMAND_SCHECK, 1))
        # Delay to make sure PE has time to turn around and set the data line high to indicate
        # it is busy (P8/Tdly3 in progspec)
        self.board.delay_us(12)
        self.pe_proxy.handshake()
        self.pe_proxy.receive_word()
        self.pe_proxy.receive_word()

    def _get_pe_version_proxy_command(self):
        """
        Reads out the Programming Executive version
        """
        self.pe_proxy.send_word(self._pe_command(self.PE_COMMAND_QVER, 1))
        # Delay to make sure PE has time to turn around and set the data line high to indicate
        # it is busy (P8/Tdly3 in progspec)
        self.board.delay_us(12)
        self.pe_proxy.handshake()
        self.pe_proxy.receive_word()
        self.pe_proxy.receive_word()

    def _read_flash_proxy_command(self, byte_address, numbytes):
        """
        Reads 24-bit instruction words from flash
        :param byte_address start address
        :numbytes Number of bytes to read (including the upper byte of each instruction word that is not implemented and
            always read as 0x00, see PIC24 prog spec). Note that the unimplemented bytes are left out from the data
            returned.

        :return
            [0x1200] (two bytes)
            [Number of 16-bit words returned including this word] (two bytes)
                (2 + 3 * N/2 if N is even,
                4 + 3 * (N - 1) / 2 if N is odd,
                where N is number of instruction words to be read
            [Data] Data is packed (see format below)

            Packed Data format:
            [   LSW1    ]
            [MSB2 | MSB1]
            [   LSW2    ]
            LSWx: Least significant 16 bits of instruction word
            MSBx: Most significant byte of instruction word

            When number of instruction words transferred is odd, MSB2 is zero and LSW2 is not transmitted
        """
        # PIC24 is word addressed (16-bit word, not instruction word)
        word_address = byte_address // 2

        # Each PIC24 instruction is 24 bits wide, but there is an extra byte so total number of bytes per
        # instruction word is 4
        num_instructionwords = numbytes // 4
        if num_instructionwords > 32768:
            raise PrimitiveException("PE does not support reading more than 32768 instruction words in one operation")
        if num_instructionwords % 2:
            # Odd number of instruction words to be read LSW2 is omitted (see comment block above)
            num16bitwords = 2 + 3 * (num_instructionwords - 1) // 2
        else:
            # Even number of instruction words to be read
            num16bitwords = 3 * num_instructionwords // 2
        self.pe_proxy.send_word(self._pe_command(self.PE_COMMAND_READP, 4))
        self.pe_proxy.send_word(num_instructionwords)
        self.pe_proxy.send_word((word_address >> 16) & 0x00FF)
        self.pe_proxy.send_word(word_address & 0xFFFF)
        # Delay to make sure PE has time to turn around and set the data line high to indicate
        # it is busy (P8/Tdly3 in progspec)
        self.board.delay_us(12)
        self.pe_proxy.handshake()
        self.pe_proxy.receive_word()
        self.pe_proxy.receive_word()
        while num16bitwords:
            self.pe_proxy.receive_word()
            num16bitwords -= 1


    def _write_flash_page_proxy_command(self, byte_address, numbytes):
        """
        Writes complete pages to flash
        :param byte_address start address
        :numbytes Number of bytes to write (including the upper byte of each instruction word that
            is not implemented, see PIC24 prog spec). Note however that the data sent in should be
            packed and not contain any data for the unimplmented bytes

            Packed Data format:
            [   LSW1    ]
            [MSB2 | MSB1]
            [   LSW2    ]
            LSWx: Least significant 16 bits of instruction word
            MSBx: Most significant byte of instruction word

            When number of instruction words transferred is odd, MSB2 is zero and LSW2 is not transmitted
        """
        # PIC24 is word addressed (16-bit word, not instruction word)
        word_address = byte_address // 2

        # Each PIC24 instruction is 24 bits wide, but there is an extra byte so total number of bytes per
        # instruction word is 4
        num_instructionwords = numbytes // 4
        num16bitwords = 3 * num_instructionwords // 2

        self.pe_proxy.send_word(self._pe_command(self.PE_COMMAND_PROGP, 3+num16bitwords))
        self.pe_proxy.send_word((word_address >> 16) & 0x00FF)
        self.pe_proxy.send_word(word_address & 0xFFFF)
        while num16bitwords:
            self.pe_proxy.send_word_buf()
            num16bitwords -= 1
        # Delay to make sure PE has time to turn around and set the data line high to indicate
        # it is busy (P8/Tdly3 in progspec)
        self.board.delay_us(12)
        self.pe_proxy.handshake()
        self.pe_proxy.receive_word()
        self.pe_proxy.receive_word()

    def _memory_read_bytes_expected_from_pe(self, read_numbytes):
        """
        Calculates the number of bytes that will be received from the Programming Executive based on the number of bytes requested to be read
        :param read_numbytes: Number of data bytes requested for the read
        :return number of bytes the Programming Executive response will contain
        """
        # PIC24 PE will return 4 extra header bytes in addition to that data is packed
        if (read_numbytes // 4) % 2:
            # Odd number of instruction words, PE will read 2 16-bit words for last instruction word, i.e. last word in double instruction is not read
            bytes_from_tool = 8 + (3 * (read_numbytes - 4) // 4)
        else:
            # Even number of instruction words
            bytes_from_tool = 4 + (3 * read_numbytes) // 4

        return bytes_from_tool

    def _check_pe_response(self, cmd, databytes, response):
        """
        Extract the header from a Programming Executive response and analyze the status information
        If the response contains data it will be decompacted
        :param cmd: The command byte that generated the response (4-bits really)
        :param databytes: Number of databytes expected from the response (decompacted data bytes)
        :param response: Complete response packet from Programming Executive
        :return data: Decompacted data extracted from the response (see PIC24 programming spec for compacting algorithm)
        """
        self.logger.debug("Checking PE response")
        # Uppper nibble of second byte is the status opcode
        status = ((response[1] & 0xF0) >> 4) & 0x0F

        # First byte is the error code for non-query commands
        errorcode = response[0]
        if errorcode == self.PE_ERROR_NONE:
            error_msg = "Error code: No error"
        elif errorcode == self.PE_ERROR_VERIFY_FAILED:
            error_msg = "Error code: Verify error"
        elif errorcode == self.PE_ERROR_UNKNOWN:
            error_msg = "Error code: Unknown error"
        else:
            error_msg = "Undefined error code"


        if status == self.PE_STATUS_PASS:
            self.logger.debug("Response status: PASS")
            self.logger.debug(error_msg)
        elif status == self.PE_STATUS_FAIL:
            raise PrimitiveException("PE command faild, response status: FAIL, {}".format(error_msg))
        elif status == self.PE_STATUS_NACK:
            raise PrimitiveException("PE command faild, response status: NACK, {}".format(error_msg))

        # Lower nibble of the second byte is an echo of the command
        cmd_echo = response[1] & 0x0F

        if cmd_echo != cmd:
            raise PrimitiveException("Unexpected command echo in response: {}, expected: {}".format(cmd_echo, cmd))

        # 3rd and 4th byte in response is the length field (number of 16-bit words in the response including header)
        response_length = binary.unpack_le16(response[2:4])
        response_length_bytes = response_length * 2

        # Response should contain a header of 4 bytes in addition to
        # data that is packed (3 bytes packed data becomes 4 bytes of unpacked data)
        response_length_expected = (databytes * 3) // 4 + 4
        if response_length_bytes != response_length_expected:
            raise PrimitiveException("Unexpected number of bytes returned: {}, expected: {}".format(response_length_bytes, response_length_expected))

        decompacted_data = pic24_decompact(response[4:])

        decompacted_numbytes = len(decompacted_data)
        if decompacted_numbytes != databytes:
            raise PrimitiveException("Response did not contain the expected number of bytes, expected: {}, actual: {}".format(databytes, decompacted_numbytes))

        return decompacted_data

    def read_flash_by_proxy(self, proxy, byte_address, numbytes):
        """
        Invoke flash read command by proxy
        :param proxy: Proxy to use for invoking the read_flash command
        :param byte_address: Start address for the read
        :param numbytes: Number of bytes to read (decompacted data, i.e. including "phantom bytes")
        :return Data uncompacted (including "phantom bytes", i.e. 4 bytes per 24-bit instruction word)
        """
        bytes_from_tool = self._memory_read_bytes_expected_from_pe(numbytes)

        response = proxy.invoke_read(bytes_to_read=bytes_from_tool, method=ProgExecInterfacePic24._read_flash_proxy_command,
                                 byte_address=int(byte_address), numbytes=numbytes)

        return self._check_pe_response(self.PE_COMMAND_READP, numbytes, response)

    def write_flash_page_by_proxy(self, proxy, byte_address, data):
        """
        Invoke flash page write command by proxy
        :param proxy: Proxy to use for invoking the write_flash_page command
        :param byte_address: Start address for the write
        :param data: Data to be written (including "phantom bytes", i.e. 4 bytes per 24-bit instruction word)
        """
        packed_data = pic24_compact(data)

        response = proxy.invoke_write_read(data_to_write=packed_data, bytes_to_read=4,
                                           method=ProgExecInterfacePic24._write_flash_page_proxy_command,
                                           byte_address=int(byte_address), numbytes=len(data))

        self._check_pe_response(self.PE_COMMAND_PROGP, 0, response)

    def check_pe_connection_by_proxy(self, proxy):
        """
        Check that the Programming Executive is operative and can be contacted
        :param proxy: Proxy to use for invoking PE commands
        :return PE version (major and minor version as one byte, upper nibble is major version, lower nibble is minor version)
        """
        self.logger.info("Checking PE connection")

        sanity_check_response = proxy.invoke_read(bytes_to_read=4, method=ProgExecInterfacePic24._sanity_check_proxy_command)
        self._check_pe_response(self.PE_COMMAND_SCHECK, 0, sanity_check_response)

        pe_version_response = proxy.invoke_read(bytes_to_read=4, method=ProgExecInterfacePic24._get_pe_version_proxy_command)
        self._check_pe_response(self.PE_COMMAND_QVER, 0, pe_version_response)

        self.logger.info("PE version: %d.%d", (pe_version_response[0] >> 4) & 0x0F, pe_version_response[0] & 0x0F)

        return pe_version_response[0]
