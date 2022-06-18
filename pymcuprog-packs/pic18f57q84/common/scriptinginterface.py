"""
Scripted debugger controller
"""
import logging

# Primitive controller takes primitive sequences over USB and executes them
from pyedbglib.primitive.primitivecontroller import PrimitiveController

# Data type helpers
from pyedbglib.util import binary

from debuggerbase import CmsisAtiPicDebugger

from primitiveembedded import PrimitiveFunctionEmbedded
from primitiveaccumulator import PrimitiveFunctionAccumulatorExecuter

from debugprovider import ConfigGeneratorTool
from debugprovider import EmbeddedTool
from debugprovider import PrinterTool

from pyedbglib.hidtransport.hidtransportbase import HidTransportBase
from pyedbglib.mplabtransport.mplabtransport import MpLabTransport

def is_blank(data):
    """
    Checks if a block of flash memory in an array is 'blank'
    """
    for d in range(0, len(data), 2):
        if not data[d] == 0xFF:
            return False
        if not data[d + 1] == 0x3F:
            # TODO: flash width should depend on the target
            return False
    return True


class PythonScriptedPicDebugger(CmsisAtiPicDebugger):
    """
    Wrapper for a python-based debugger
    """

    def __init__(self, device_name):
        self.logger = logging.getLogger(__name__)
        CmsisAtiPicDebugger.__init__(self, device_name)
        self.logger.info("Creating nEDBG scripting wrapper")

    def setup_session(self, tool, options):
        """
        Takes transport and options and propagates them down the stack
        :param tool: tool AKA transport (HID or MPLAB)
        :param options: dictionary of session options

        NB: transport object passed in is either:
        - MPLAB-transport from within MPLAB Jython
        - HIDAPI-transport from standalone Python
        The MPLAB transport gets wrapped in a HID-API API equivalent wrapper to become self.transport before use
        """
        CmsisAtiPicDebugger.setup_session(self, tool, options)

        # NB: Use self.transport only after setup session

        # Raspberry Pi etc
        if isinstance(tool, EmbeddedTool):
            # Use this mode to execute primitives locally on an embedded python engine
            self.logger.debug("Embedded Tool")
            self.device_proxy = PrimitiveFunctionEmbedded(self.device_object)

        elif isinstance(tool, PrinterTool):
            # Use this mode to display primitive strings
            self.logger.debug("Printer Tool")
            from primitiveprinter import PrimitiveFunctionPrinter
            self.device_proxy = PrimitiveFunctionPrinter(self.device_object)

            self.debug_executive_model = self.device_model.DEBUGGING_INTERFACE
            self.debug_executive_object = self.device_model.DEBUGGING_INTERFACE()

            self.debug_executive_proxy = PrimitiveFunctionPrinter(self.debug_executive_object)

        elif isinstance(tool, ConfigGeneratorTool):
            # Use this mode to generate XML output
            self.logger.debug("Config Tool")
            from primitiveprinter import PrimitiveFunctionXmlGenerator
            self.device_proxy = PrimitiveFunctionXmlGenerator(self.device_object, tool)

        else:
            # Pre-initialised HID transport, see notes above
            self.logger.debug("HID Tool")
            # Controller object for interfacing with the debugger tool
            self.logger.info("Creating primitive controller")
            self.controller = PrimitiveController(self.transport)

            # Use this mode to accumulate primitives, compress them, then execute them on a remote USB host
            self.device_proxy = PrimitiveFunctionAccumulatorExecuter(self.device_object, self.controller)

            # Instantiate the debug executive driver
            # Debug is currently only available when using remote USB primitive execution (ie: transport exists)
            self.debug_executive_model = self.device_model.DEBUGGING_INTERFACE
            self.debug_executive_object = self.device_model.DEBUGGING_INTERFACE()

            self.debug_executive_proxy = PrimitiveFunctionAccumulatorExecuter(self.debug_executive_object,
                                                                          self.controller)

    def set_debug_exec(self, byte_address, data):
        """
        Store the debug exec for later use
        """
        self.logger.info("Storing debug exec address: 0x%X", byte_address)
        self.debug_exec_address = byte_address
        self.debug_exec_data = data

    def enter_tmod(self):
        """
        Enter TMOD (programming mode)
        """
        # Already in?
        if self._in_tmod:
            return

        # Set ICSP clock frequency
        self.device_proxy.invoke(self.device_model.set_speed)

        # Enter TMOD
        self.device_proxy.invoke(self.device_model.enter_tmod)

        # Read ID for good measure
        result = self.device_proxy.invoke_read(bytes_to_read=2, method=self.device_model.read_id)
        device_id = binary.unpack_le16(result)

        self.logger.info("Device ID read: {0:04X}".format(device_id & 0xFFFF))
        if device_id == 0x0000 or device_id == 0xFFFF:
            self.logger.error("Suspect device ID read")
        self._in_tmod = True

    def read_id(self):
        """
        Reads the device ID
        :return: device ID
        """
        # Read device ID
        result = self.device_proxy.invoke_read(bytes_to_read=2, method=self.device_model.read_id)
        device_id = binary.unpack_le16(result)
        self.logger.info("Device ID read: {0:04X}".format(device_id & 0xFFFF))
        if device_id == 0x0000 or device_id == 0xFFFF:
            self.logger.error("Suspect device ID read")
        return device_id

    def exit_tmod(self):
        """
        Exit TMOD (programming mode)
        """
        # Already out?
        if not self._in_tmod:
            return

        # Exit TMOD
        self.device_proxy.invoke(self.device_model.exit_tmod)

        self._in_tmod = False

    def read_flash_memory(self, byte_address, numbytes):
        """
        Read flash memory
        :param byte_address: start address
        :param numbytes: number of bytes
        """
        # Gather chunks
        result = bytearray()

        # TODO - read granularity from tool
        chunk_size = 0x100

        # Loop until done
        while numbytes > 0:
            # Handle leftovers
            if chunk_size > numbytes:
                chunk_size = numbytes
            # Read
            chunk = self._read_flash_block(byte_address, chunk_size)
            # Word address increment
            byte_address += chunk_size
            numbytes -= chunk_size
            # Append to results
            result.extend(chunk)

        return result

    def read_config_memory(self, byte_address, numbytes):
        """
        Read config memory
        :param byte_address: start address
        :param numbytes: number of bytes
        """
        # Gather chunks
        result = bytearray()

        # Word count, make sure we read the complete word(s) in case somebody asks for an odd number of bytes
        words = (numbytes + 1) // 2
        # Loop until done
        while words > 0:
            self.logger.info("Read config word ({0:d} bytes) at 0x{1:02X}".format(numbytes, byte_address))
            # Invoke read by proxy, reading one word at a time
            chunk = self.device_proxy.invoke_read(bytes_to_read=2, method=self.device_model.read_config_word,
                                                  byte_address=int(byte_address))
            words -= 1
            byte_address += 2
            # Append to results
            result.extend(chunk)

        # Did anyone ask for an odd number of bytes? Remove the excess byte
        if numbytes%2 == 1:
            del result[-1]

        return result

    def read_eeprom_memory(self, byte_address, numbytes):
        """
        Read eeprom memory
        :param byte_address: start address
        :param numbytes: number of bytes
        """
        # Gather chunks
        result = bytearray()

        # TODO - read granularity from tool
        chunk_size = 0x100

        # Loop until done
        while numbytes > 0:
            # Handle leftovers
            if chunk_size > numbytes:
                chunk_size = numbytes
            # Read
            chunk = self._read_eeprom_block(byte_address, chunk_size)
            # Word address increment
            byte_address += chunk_size
            numbytes -= chunk_size
            # Append to results
            result.extend(chunk)

        return result

    def _read_flash_block(self, byte_address, numbytes):
        """
        Read flash block
        """
        self.logger.info("Read flash block ({0:d} bytes) at 0x{1:02X}".format(numbytes, byte_address))
        # Word count, make sure we read the complete word in case somebody asks for an odd number of bytes
        words = (numbytes + 1) // 2

        # Invoke read by proxy
        data = self.device_proxy.invoke_read(bytes_to_read=numbytes, method=self.device_model.read_flash,
                                             byte_address=int(byte_address), words=int(words))
        return data

    def _read_eeprom_block(self, byte_address, numbytes):
        """
        Read eeprom block
        """
        self.logger.info("Read eeprom block ({0:d} bytes) at 0x{1:02X}".format(numbytes, byte_address))

        # Invoke read by proxy
        data = self.device_proxy.invoke_read(bytes_to_read=numbytes, method=self.device_model.read_eeprom,
                                             byte_address=int(byte_address), numbytes=int(numbytes))
        return data

    def write_eeprom_memory(self, byte_address, data):
        """
        Write eeprom memory
        :param byte_address: start address (byte address)
        :param data: data to write
        """

        # ATI chunk is 512
        # TODO: read out from ATI
        chunk_size = 512

        bytes_left = len(data)

        index = 0
        # Loop until done
        while bytes_left > 0:
            # Handle leftovers
            if chunk_size > bytes_left:
                chunk_size = bytes_left
            # Write
            self._write_eeprom_block(byte_address, data[index:index + chunk_size])
            # Address increment
            byte_address += chunk_size
            bytes_left -= chunk_size
            index += chunk_size

        # TODO - check result

    def _write_eeprom_block(self, byte_address, data):
        """
        Write eeprom block
        :param byte_address: start address (byte address)
        :param data: data to write
        """
        self.logger.info("Writing EEPROM block of %d bytes at 0x%02X", len(data), int(byte_address))

        # Invoke write by proxy
        self.device_proxy.invoke_write(data_to_write=data, method=self.device_model.write_eeprom,
                                       byte_address=byte_address, numbytes=int(len(data)))
        # TODO - check result

    def write_flash_memory(self, byte_address, data):
        """
        Write flash memory
        :param byte_address: start address (byte address)
        :param data: data to write
        """
        if self.options['overlapped_usb_access']:
            self._write_flash_block_overlapped(byte_address, data)
        else:
            self._write_flash_block(byte_address, data)

    def _write_flash_block_overlapped(self, byte_address, data):
        self.logger.info("Flash block write (overlapped)")
        chunk_size = self.device_object.get_flash_write_row_size_bytes()

        numbytes = len(data)
        data_buf_id = 0
        if numbytes < chunk_size:
            chunk_size = numbytes

        # Send first data first
        self.controller.write_data_buffer(data_buf_id, data[0:chunk_size])
        # Start first page write
        self.device_proxy.trigger_write(data_buffer_id=data_buf_id, method=self.device_model.write_flash_page,
                                        byte_address=int(byte_address), words=chunk_size // 2)

        # Shrink data
        data = data[chunk_size:]
        byte_address += chunk_size

        # Loop
        while data:
            # Handle leftovers
            if len(data) < chunk_size:
                chunk_size = len(data)

            # Buffer ID flip
            data_buf_id = (data_buf_id + 1) % 2

            # Write next page's data
            self.controller.write_data_buffer(data_buf_id, data[0:chunk_size])

            # Block while first one completes
            self.device_proxy.wait_write_done()

            # Trigger next
            self.device_proxy.trigger_write(data_buffer_id=data_buf_id, method=self.device_model.write_flash_page,
                                            byte_address=int(byte_address), words=chunk_size // 2)

            # TODO - check results
            # if function_retval[0] != 0x01:
            #    logging.error("Flash write FAILED! Return value was not True")
            #    sys.exit(1)

            # Increment byte address
            byte_address += chunk_size

            # Shrink data
            data = data[chunk_size:]

        # Wait for last chunk
        self.device_proxy.wait_write_done()

    @staticmethod
    def chunks(data, chunk_size):
        """
        Yield successive chunk_size-sized chunks from data
        """
        for i in range(0, len(data), chunk_size):
            yield data[i:i + chunk_size]

    def _write_flash_block(self, byte_address, data):
        """
        Writes flash
        :param byte_address:    byte address to start writing from
        :param data:            data to write
        """
        self.logger.info("Flash block write")
        pagebytes = self.device_object.get_flash_write_row_size_bytes()

        skip_blank_pages = self.options['skip_blank_pages']
        for chunk in self.chunks(data, pagebytes):
            # TODO: not all PICs can just skip pages by leaving them out.
            if not skip_blank_pages or not is_blank(chunk):
                self.logger.info("Writing a page at byte address 0x%04X", int(byte_address))
                self._write_flash_page(byte_address, chunk)
            else:
                self.logger.info("Skipping a page at byte address 0x%04X", byte_address)
            # Increment address
            byte_address += pagebytes

    def _write_flash_page(self, byte_address, data):
        """
        Write a single flash page
        :param byte_address:    page start byte address
        :param data:            data bytearray to program
        """
        self.logger.debug("Flash page write")

        # Word count
        words = len(data) // 2

        # Invoke write by proxy
        self.device_proxy.invoke_write(data_to_write=data, method=self.device_model.write_flash_page,
                                       byte_address=byte_address, words=int(words))
        # TODO - check result

    def _write_de_page(self, byte_address, data):
        """
        Write a single flash page
        :param byte_address:    page start byte address
        :param data:            data bytearray to program
        """
        self.logger.debug("DE page write")

        # Word count
        words = len(data) // 2

        # Invoke write by proxy
        self.device_proxy.invoke_write(data_to_write=data, method=self.device_model.write_de_page,
                                       byte_address=int(byte_address), words=int(words))

        # TODO - result check

    def _write_de_block(self, byte_address, data):
        """
        Writes flash
        :param byte_address:    byte address to start writing from
        :param data:            data to write
        """
        self.logger.info("DE block write")
        pagebytes = self.device_object.get_flash_write_row_size_bytes()

        for chunk in self.chunks(data, pagebytes):
            self.logger.info("Writing a page at byte address 0x%04X", byte_address)
            self._write_de_page(byte_address, chunk)
            # Increment address
            byte_address += pagebytes

    def _verify_flash_block(self, byte_address, data, silent_early_exit=False):
        """
        Verify Block
        """
        self.logger.info("Reading flash (%d bytes from byte address 0x%04X)", len(data), byte_address)
        read_back = self.read_flash_memory(byte_address, len(data))

        self.logger.info("Verifying flash")
        numerrors = 0
        for i in range(len(data)):
            if data[i] != read_back[i]:
                if silent_early_exit:
                    # This path is used when a verify failure has an immediate remedy (like checking if the PE is there)
                    # Bothering the user with errors and then fixing them silently is not polite.
                    return False
                numerrors += 1
                if numerrors <= 5:
                    self.logger.error("Flash verify error at 0x%04X (wrote 0x%02X; read 0x%02X)", (byte_address + i),
                                 data[i], read_back[i])
        if numerrors > 0:
            self.logger.error("%d verification errors", numerrors)
            return False
        return True

    def _write_config_word(self, byte_address, data):
        """
        Write config words
        """
        self.logger.debug("Writing config word")
        self.device_proxy.invoke_write(data_to_write=data, method=self.device_model.write_config_word,
                                       byte_address=byte_address)

    def _write_user_id_word(self, byte_address, data):
        """
        Write user_id word
        """
        self.logger.debug("Writing user_id word")
        self.device_proxy.invoke_write(data_to_write=data, method=self.device_model.write_user_id_word,
                                       byte_address=byte_address)

    def erase(self, byte_address=None):
        """
        Erase the device
        :param byte_address: address for the (bulk) erase, see programming spec for the target device for info on which
        memory sections will be erased
        """
        # Use address if provided
        self.device_proxy.invoke(self.device_model.bulk_erase, byte_address=byte_address)

    def erase_de_memory(self, address, words):
        """
        Erase the Debug Executive
        :param address: start address
        :param words: number of words
        """
        # Generate a command to execute
        self.logger.debug("Erase DE at address 0x%X", address)
        self.device_proxy.invoke(self.device_model.erase_de, byte_address=int(address), words=int(words))

    def write_config_memory(self, byte_address, data):
        """
        Write config memory
        :param byte_address: start address (byte address)
        :param data: data to write
        """
        for i in range(len(data) // 2):
            values = data[i * 2:i * 2 + 2]
            self.logger.info("Writing one config word at 0x{:02X}".format(byte_address + i * 2))
            self.logger.info("0x{:02X} 0x{:02X}".format(values[0], values[1]))
            self._write_config_word(byte_address + i * 2, values)

    def write_user_id_memory(self, byte_address, data):
        """
        Write user_id memory
        :param byte_address: start address (byte address)
        :param data: data to write
        """
        for i in range(len(data) // 2):
            values = data[i * 2:i * 2 + 2]
            self.logger.info("Writing one user id word at 0x{:02X}".format(byte_address + i * 2))
            self.logger.info("0x{:02X} 0x{:02X}".format(values[0], values[1]))
            self._write_user_id_word(byte_address + i * 2, values)

    def start_programming_operation(self):
        """
        Start programming
        """
        self.enter_tmod()

    def end_of_operations(self):
        """
        Done programming
        """
        self.exit_tmod()

    def init_debug_session(self, program_de=True):
        """
        Start a debug session
        """
        self.logger.info("Entering debug mode")

        # Program the DE
        if program_de:
            if self.debug_exec_address is None:
                self.logger.warning("Debug Executive not set!")
            else:
                self.enter_tmod()
                self.logger.info("Checking DE")
                status = True
                if self._verify_flash_block(self.debug_exec_address, self.debug_exec_data, silent_early_exit=True):
                    self.logger.info("DE OK")
                else:
                    self.logger.info("Erasing DE")
                    self.erase_de_memory(self.debug_exec_address, len(self.debug_exec_data))
                    self.logger.info("Writing DE")
                    self._write_de_block(self.debug_exec_address, self.debug_exec_data)
                    self.logger.info("Verifying DE")
                    status = self._verify_flash_block(self.debug_exec_address, self.debug_exec_data)
                self.exit_tmod()
                if not status:
                    self.logger.error("DE verification failed!")
                    raise Exception("Error writing debug executive! Unable to start debug session.")

        self.logger.info("Launch")
        self.device_proxy.invoke(self.device_model.enter_debug)

        # Try to read the DE version to check that things are ok
        # If unable to communicate with the DE an exception will be raised and will have to be handled further up the stack.
        de_version = self.debug_read_de_version()

        # Reset state
        self._is_running = False
        self._in_tmod = False

    def end_debug_session(self):
        """
        End debug session
        """
        self.logger.info("Ending debug session")
        self._is_running = False

    @staticmethod
    def _check_de_response(result):
        """
        Checks the DE response
        :param result: raw response
        :return:
        """
        status = binary.unpack_le32(result)
        if status != 0:
            msg = "Fatal errror communicating with the debug executive. Error code {0:04X}.".format(status & 0xFFFF)
            raise Exception(msg)

    def debug_read_memory(self, byte_address, length):
        """
        Read memory in debug mode
        :param byte_address: start address (byte)
        :param length: number of locations to read
        :return:
        """
        self.logger.debug("Read mem of %d byte(s) from byte address %d", length, byte_address)

        # Setup read request
        de_command = self.debug_executive_object.de_command_memory_read(byte_address, length)

        # Execute via proxy
        return self.debug_executive_proxy.invoke_write_read(de_command, length, self.debug_executive_model.read_mem,
                                                            numbytes=int(length))

    def debug_write_memory(self, address, data, length):
        """
        Write memory in debug mode
        :param address: start address
        :param data: data to write
        :param length: number of locations to write
        :return:
        """
        self.logger.debug("Write mem of %d locations to address %d", length, address)

        # Setup write request
        de_command = self.debug_executive_object.de_command_memory_write(address, length)

        # Add data
        de_command.extend(data)

        result = self.debug_executive_proxy.invoke_write(data_to_write=de_command,
                                                         method=self.debug_executive_model.write_mem,
                                                         numbytes=int(length))
        self._check_de_response(result)

    def debug_erase(self, byte_address):
        """
        Erase flash memory in debug mode
        :param byte_address: page start address
        :return:
        """
        self.logger.info("Erase mem at byte address %d", byte_address)

        word_address = byte_address // 2

        # Setup erase request
        de_command = self.debug_executive_object.de_command_erase(word_address)

        # Execute
        result = self.debug_executive_proxy.invoke_write(data_to_write=de_command,
                                                         method=self.debug_executive_model.debug_erase_page,
                                                         delay=self.device_object.ROW_ERASE_DELAY_US)

        self._check_de_response(result)

    def is_running(self):
        """
        State query
        """
        # Poll
        resp = self.debug_executive_proxy.invoke(self.debug_executive_model.get_run_state)
        if resp[0] & (1 << 2):
            self._is_running = False
        else:
            self._is_running = True

        return self._is_running

    def get_pc(self):
        """
        Read the PC
        """
        self.logger.debug("Read PC")
        resp = self.debug_executive_proxy.invoke(self.debug_executive_model.read_pc)

        # Mask out to 2 bytes
        pc = binary.unpack_le32(resp) & 0xFFFF
        self.logger.debug("PC read as:")
        self.logger.debug(pc)
        return pc

    def set_pc(self, pc):
        """
        Write the PC
        :param pc: PC value
        """
        self.logger.info("Write PC to address %d", pc)

        # Send data
        de_command = self.debug_executive_object.de_command_set_pc(pc)

        # Execute
        result = self.debug_executive_proxy.invoke_write(data_to_write=de_command,
                                                         method=self.debug_executive_model.set_pc)
        self._check_de_response(result)

    def run(self):
        """
        Put the device in RUN mode
        """
        if self._is_running:
            self.logger.info("Already running!")
        else:
            result = self.debug_executive_proxy.invoke(self.debug_executive_model.run)
            self._check_de_response(result)
            self._is_running = True

    def halt(self):
        """
        HALT the device
        """
        if not self._is_running:
            self.logger.info("Already halted!")
        else:
            result = self.debug_executive_proxy.invoke(self.debug_executive_model.halt)
            self._check_de_response(result)
            self._is_running = False

    def step(self):
        """
        Single step and halt
        """
        if self._is_running:
            self.logger.info("Cannot step while running!")
        else:
            result = self.debug_executive_proxy.invoke(self.debug_executive_model.step)
            self._check_de_response(result)

    def reset_target(self):
        """
        Reset target (in debug session)
        """
        if self._is_running:
            self.logger.info("Cannot reset while running!")
        else:
            self.logger.info("Reseting...")
            self.enter_tmod()
            self.exit_tmod()
            # No need to re-program the DE
            self.init_debug_session(False)

    def release_from_reset(self):
        """
        Release from reset (programming session)
        """
        self.device_proxy.invoke(self.device_model.release_from_reset)
        # MCLR has just been messed with, can't assume programming mode to be active anymore
        self._in_tmod = False

    def hold_in_reset(self):
        """
        Hold in reset (programming session)
        """
        self.device_proxy.invoke(self.device_model.hold_in_reset)
        # MCLR has just been messed with, can't assume programming mode to be active anymore
        self._in_tmod = False

    def debug_read_de_version(self):
        """
        Read Debug Exec version
        """
        self.logger.info("Read DE version")

        data = self.debug_executive_proxy.invoke_read(bytes_to_read=4,
                                                      method=self.debug_executive_model.read_de_version)
        self.logger.info("DE version: %d.%d.%d.%d", data[3], data[2], data[1], data[0])
        return data

    def debug_write_flash(self, byte_address, data):
        """
        Write flash in debug mode
        :param byte_address: start address
        :param data: data to write
        """
        self.logger.info("Write flash of %d byte(s) to byte address %d", len(data), byte_address)

        word_address = byte_address // 2

        # Setup write request
        de_command = self.debug_executive_object.de_command_memory_write(word_address, len(data))

        # Add data
        de_command.extend(data)

        result = self.debug_executive_proxy.invoke_write(data_to_write=de_command,
                                                         method=self.debug_executive_model.debug_write_flash,
                                                         numbytes=len(data),
                                                         delay=self.device_object.PAGE_PROGRAMMING_DELAY_US)
        self._check_de_response(result)

    def debug_read_flash(self, byte_address, numbytes):
        """
        Read flash in debug mode
        :param byte_address: start address
        :param numbytes: number of bytes to read
        :return:
        """
        self.logger.info("Read flash of %d bytes from byte address %d", numbytes, byte_address)

        word_address = byte_address // 2
        words = numbytes // 2

        # Gather chunks
        result = bytearray()

        # TODO - read granularity from tool
        chunk_size_words = 0x100 // 2

        # Loop until done
        while words > 0:
            # Handle leftovers
            if chunk_size_words > words:
                chunk_size_words = words

            self.logger.info("Read %d words from word_address 0x%02X", chunk_size_words, word_address)

            # Setup read request
            de_command = self.debug_executive_object.de_command_memory_read(word_address, chunk_size_words)

            # Execute via proxy
            chunk = self.debug_executive_proxy.invoke_write_read(de_command, chunk_size_words * 2,
                                                                 self.debug_executive_model.debug_read_flash,
                                                                 numbytes=int(chunk_size_words * 2))

            # Word address increment
            word_address += chunk_size_words
            words -= chunk_size_words
            # Append to results
            result.extend(chunk)

        return result

    def debug_read_test(self, byte_address, numbytes):
        """
        Read Test / Configuration Memory (User ID, Config words, Test memory) in debug mode
        :param byte_address: start address (byte)
        :param numbytes: number of bytes to read
        :return:
        """
        self.logger.info("Read Test memory of %d bytes from byte address %d", numbytes, byte_address)

        word_address = byte_address // 2
        words = numbytes // 2
        # Gather chunks
        result = bytearray()

        # TODO - read granularity from tool
        chunk_size_words = 0x100 // 2

        # Loop until done
        while words > 0:
            # Handle leftovers
            if chunk_size_words > words:
                chunk_size_words = words

            # Setup read request
            de_command = self.debug_executive_object.de_command_memory_read(word_address, chunk_size_words)

            # Execute via proxy
            chunk = self.debug_executive_proxy.invoke_write_read(de_command, chunk_size_words * 2,
                                                                 self.debug_executive_model.debug_read_test,
                                                                 numbytes=int(chunk_size_words * 2))
            # Word address increment
            word_address += chunk_size_words
            words -= chunk_size_words
            # Append to results
            result.extend(chunk)

        return result

    def debug_read_eeprom(self, byte_address, numbytes):
        """
        Read EEPROM in debug mode
        :param byte_address: start address (byte)
        :param numbytes: number of bytes to read
        :return:
        """
        self.logger.info("Read EEPROM of %d bytes from byte address %d", numbytes, byte_address)

        # Gather chunks
        result = bytearray()

        # TODO - read granularity from tool
        chunk_size_bytes = 0x100

        # Loop until done
        while numbytes > 0:
            # Handle leftovers
            if chunk_size_bytes > numbytes:
                chunk_size_bytes = numbytes

            # Setup read request
            de_command = self.debug_executive_object.de_command_memory_read(byte_address, chunk_size_bytes)

            # Execute via proxy
            chunk = self.debug_executive_proxy.invoke_write_read(de_command, chunk_size_bytes,
                                                                 self.debug_executive_model.debug_read_eeprom,
                                                                 numbytes=int(chunk_size_bytes))
            # Address increment
            byte_address += chunk_size_bytes
            numbytes -= chunk_size_bytes
            # Append to results
            result.extend(chunk)

        return result

    def set_sw_bp(self, byte_address, instruction, flags):
        """
        Insert / remove software breakpoint
        :param byte_address: address to probe
        :param instruction: instruction to insert
        :param flags: ignored
        :return: instruction removed
        """
        # pylint: disable=unused-argument
        # Fetch the number of words per page from the device
        pagebytes = self.device_object.get_flash_write_row_size_bytes()
        # Calculate the start address of this page
        page_start_address = byte_address & ~(pagebytes - 1)
        # Calculate the page offset of the instruction to modify
        page_offset = byte_address % pagebytes

        # Read out the original page
        self.logger.info("Reading page starting at {0:04X}".format(page_start_address))
        data = self.debug_read_flash(page_start_address, pagebytes)

        # Extract the original instruction
        opcode = binary.unpack_le16(data[page_offset:page_offset + 2])
        self.logger.info("Original instruction: 0x%04X", opcode)

        # Replace Instruction
        data[page_offset] = instruction & 0xFF
        data[page_offset + 1] = (instruction >> 8) & 0xFF

        # Erase page
        self.logger.info("Erasing page at address {0:04X}".format(page_start_address))
        self.debug_erase(page_start_address)

        # Rewrite
        self.logger.info("Writing back page")
        self.debug_write_flash(page_start_address, data)

        # Return the original opcode replaced
        return int(opcode)


class PythonScriptedPic16Debugger(PythonScriptedPicDebugger):
    """
    PIC16 variant
    """
    pass


class PythonScriptedPic18Debugger(PythonScriptedPicDebugger):
    """
    PIC18 variant
    """

    def set_sw_bp(self, address, instruction, flags):
        """
        Insert / remove software breakpoint
        :param address: address to probe
        :param instruction: instruction to insert
        :param flags: ignored
        :return: instruction removed
        """
        self.logger.error("Software breakpoints are currently not supported for PIC18")
        # TODO when DE is ready for it https://jira.microchip.com/browse/MHD-212

    def debug_erase(self, address):
        """
        Erase flash memory in debug mode
        :param address: page start address
        :return:
        """
        self.logger.error("Erase flash memory in debug mode is not supported for PIC18")

    def debug_write_flash(self, address, data):
        """
        Write flash in debug mode
        :param address: start address
        :param data: data to write
        """
        self.logger.error("Write flash in debug mode is not supported for PIC18")

    def debug_read_flash(self, address, numbytes):
        """
        Read flash in debug mode
        :param address: start address
        :param numbytes: number of bytes to read
        :return:
        """
        self.logger.error("Read flash in debug mode is not supported for PIC18")

    def debug_read_test(self, address, numbytes):
        """
        Read Test memory in debug mode
        """
        self.logger.error("Read test memory in debug mode is not supported for PIC18")

    def debug_read_eeprom(self, address, numbytes):
        """
        Read Test memory in debug mode
        """
        self.logger.error("Read EEPROM memory in debug mode is not supported for PIC18")

    def set_pc(self, pc):
        """
        Write the PC
        :param pc: PC value
        """
        self.logger.error("Write PC is not supported for PIC18")

    def debug_read_emulation(self, address, length):
        """
        Read emulation memory in debug mode
        :param address: start address
        :param length: number of locations to read
        :return:
        """
        self.logger.debug("Read emulation memory of %d byte(s) from %d", length, address)

        # Setup read request
        de_command = self.debug_executive_object.de_command_memory_read(address, length)

        # Execute via proxy
        return self.debug_executive_proxy.invoke_write_read(de_command, length,
                                                            self.debug_executive_model.read_emulation,
                                                            numbytes=int(length))

    def debug_write_emulation(self, address, data, length):
        """
        Write emulation memory in debug mode
        :param address: start address
        :param data: data to write
        :param length: number of locations to write
        :return:
        """
        self.logger.debug("Write emulation memory of %d locations to address %d", length, address)

        # Setup write request
        de_command = self.debug_executive_object.de_command_memory_write(address, length)

        # Add data
        de_command.extend(data)

        result = self.debug_executive_proxy.invoke_write(data_to_write=de_command,
                                                         method=self.debug_executive_model.write_emulation,
                                                         numbytes=int(length))
        self._check_de_response(result)

    def get_pc(self):
        """
        Read the PC
        """
        self.logger.debug("Read PC")
        resp = self.debug_executive_proxy.invoke(self.debug_executive_model.read_pc)

        # Mask out to 3 bytes
        pc = binary.unpack_le32(resp) & 0xFFFFFF
        self.logger.debug("PC read as:")
        self.logger.debug(pc)
        return pc
