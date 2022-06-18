"""
Scripted (GEN4-language) debugger controller
"""
import logging

# GEN4 controller sends GEN4 scripts over USB and executes them
from pyedbglib.primitive.gen4controller import Gen4Controller
# Primitive controller takes primitive sequences over USB and executes them
from pyedbglib.primitive.primitivecontroller import PrimitiveController

# Data type helpers
from pyedbglib.util import binary

from debuggerbase import CmsisAtiPicDebugger

from gen4scriptwrapper import Gen4ScriptWrapper

from primitiveaccumulator import PrimitiveFunctionAccumulatorExecuter

from debugprovider import PrinterTool

def is_blank(data):
    """
    Checks if a block of flash memory in an array is 'blank'
    """
    for d in range(0, len(data), 1):
        if not data[d] == 0xFF:
            return False
            # TODO: flash width should depend on the target

    return True


class Gen4WrapperDebugger(CmsisAtiPicDebugger):
    """
    Wrapper for a python-based debugger
    """
    DE_COMMAND = 0x31
    DE_COMMAND_DATA_ONLY = 0x35

    def __init__(self, device_name):
        self.logger = logging.getLogger(__name__)
        CmsisAtiPicDebugger.__init__(self, device_name)
        self.logger.info("Creating nEDBG GEN4 language wrapper")
        self.use_pe = False

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

        if isinstance(tool, PrinterTool):
            # Use this mode to display primitive strings
            self.logger.debug("Printer Tool")
            from primitiveprinter import PrimitiveFunctionPrinter
            self.device_proxy = PrimitiveFunctionPrinter(self.device_object)

            self.debug_executive_model = self.device_model.DEBUGGING_INTERFACE
            self.debug_executive_object = self.device_model.DEBUGGING_INTERFACE()

            self.debug_executive_proxy = PrimitiveFunctionPrinter(self.debug_executive_object)

            self.prog_executive_model = self.device_model.PROGRAMMING_EXECUTIVE_INTERFACE
            self.prog_executive_object = self.device_model.PROGRAMMING_EXECUTIVE_INTERFACE()

            self.prog_executive_proxy = PrimitiveFunctionPrinter(self.prog_executive_object)
        else:
            # NB: Use self.transport only after setup session
            if self.transport:
                # Controller object for interfacing with the debugger tool in programming mode
                self.logger.debug("Creating programming primitive controller")
                self.prog_controller = Gen4Controller(self.transport)

                # Controller object for interfacing with the debugger tool in debug mode
                self.logger.debug("Creating debug primitive controller")
                self.debug_controller = PrimitiveController(self.transport)

                self.logger.debug("Creating GEN4 wrapper")
                self.device_proxy = Gen4ScriptWrapper(self.device_object, self.prog_controller)

                # Debug is currently only available when using remote USB primitive execution (ie: transport exists)
                # Instantiate the debug executive driver
                self.debug_executive_model = self.device_model.DEBUGGING_INTERFACE
                self.debug_executive_object = self.device_model.DEBUGGING_INTERFACE()

                self.debug_executive_proxy = PrimitiveFunctionAccumulatorExecuter(self.debug_executive_object,
                                                                                self.debug_controller)

                self.prog_executive_model = self.device_model.PROGRAMMING_EXECUTIVE_INTERFACE
                self.prog_executive_object = self.device_model.PROGRAMMING_EXECUTIVE_INTERFACE()

                # For the programming executive we use primitives like for the debug executive so we can just reuse the debug_controller
                self.prog_executive_proxy = PrimitiveFunctionAccumulatorExecuter(self.prog_executive_object, self.debug_controller)

    def set_program_exec(self, address, data, pe_version=None):
        """
        Store the programming exec for later use
        :param address: PE address
        :param data: PE content
        :param pe_version: One byte version (Upper nibble is major version and lower nibble is minor version)
        """
        self.program_exec_address = address
        self.program_exec_data = data
        self.program_exec_version = pe_version


    def set_debug_exec(self, address, data):
        """
        Store the debug exec for later use
        """
        self.debug_exec_address = address
        self.debug_exec_data = data

    def enter_tmod(self):
        """
        Enter TMOD (programming mode)
        """
        # Already in?
        if self._in_tmod:
            return

        # PE mode enabled?
        if self._in_tmod_pe:
            # Then we have to disable it first
            self.exit_tmod()

        # Set ICSP clock frequency
        self.device_proxy.invoke(self.device_model.set_speed)

        # Enter TMOD
        self.logger.info("Enter TMOD")
        self.device_proxy.invoke(self.device_model.enter_tmod)

        # Read ID for good measure
        result = self.device_proxy.invoke_read(bytes_to_read=4, method=self.device_model.read_id)
        device_id = binary.unpack_le32(result) >> 16

        self.logger.info("Device ID read: {0:04X}".format(device_id & 0xFFFF))
        if device_id & 0xFFFF == 0x0000 or device_id & 0xFFFF == 0x3FFF:
            raise Exception("Unable to read ID")

        self._in_tmod = True

    def enter_tmod_pe(self):
        """
        Enter TMOD (programming mode) enabling Programming Executive
        Note Programming Executive must already be programmed in the device before calling this function
        :return Programming Executive version (one byte, upper nibble is major version and lower nibble is minor version)
        """
        # Already in?
        if self._in_tmod_pe:
            return self._current_pe_version

        # Normal mode enabled?
        if self._in_tmod:
            # Then we have to disable it first
            self.exit_tmod()

        # Set ICSP clock frequency
        self.device_proxy.invoke(self.device_model.set_speed_pe)

        # Enter TMOD
        self.logger.info("Enter TMOD, PE mode")
        self.device_proxy.invoke(self.device_model.enter_tmod_pe)

        try:
            self._current_pe_version = self.prog_executive_object.check_pe_connection_by_proxy(self.prog_executive_proxy)
        except:
            # Even if a PE is present in the target it can suddenly become unavailable for example if the Debug config bit has just been set
            # If reading the PE version fails normal ICSP should be used as a fallback
            # Disable future PE use (in the current session)
            self.use_pe = False
            self.logger.info("Could not contact PE, falling back to normal ICSP")
            self.enter_tmod()
            return None

        self._in_tmod_pe = True

        return self._current_pe_version

    def read_id(self):
        """
        Reads the device ID
        :return: device ID
        """
        # Read device ID
        result = self.device_proxy.invoke_read(bytes_to_read=4, method=self.device_model.read_id)
        device_id = binary.unpack_le32(result) >> 16

        self.logger.info("Device ID read: {0:04X}".format(device_id & 0xFFFF))
        if device_id == 0x0000 or device_id == 0xFFFF:
            self.logger.error("Suspect device ID read")
        return device_id

    def exit_tmod(self):
        """
        Exit TMOD (programming mode)
        """
        # Already out?
        if not self._in_tmod and not self._in_tmod_pe:
            return

        # Exit TMOD
        self.logger.info("Exit TMOD")
        self.device_proxy.invoke(self.device_model.exit_tmod)

        self._in_tmod = False
        self._in_tmod_pe = False

    def read_flash_memory(self, byte_address, numbytes):
        """
        Read flash memory
        :param byte_address: start address
        :param numbytes: number of bytes
        """
        # Gather chunks
        result = bytearray()

        # ATI chunk is 512
        # TODO: read out from ATI
        chunk_size_bytes = 512

        if self.use_pe:
            # Enable eICSP (PE mode) only when we need it
            self.enter_tmod_pe()

        # Loop until done
        while numbytes > 0:
            # Handle leftovers
            if chunk_size_bytes > numbytes:
                chunk_size_bytes = numbytes
            # Read
            chunk = self._read_flash_block(byte_address, chunk_size_bytes)

            # Increment address according to number of locations read.
            byte_address += chunk_size_bytes
            numbytes -= chunk_size_bytes

            # Append to results
            result.extend(chunk)

        if self.use_pe:
            # The default is normal ICSP mode, so we revert to it when current operation is done
            self.enter_tmod()

        return result


    def _read_flash_block(self, byte_address, numbytes):
        """
        Read flash block
        """
        self.logger.debug("Read flash block ({0:d} bytes) at 0x{1:02X}".format(numbytes, byte_address))

        if self.use_pe:
            # Using Programming Executive (PE), assuming PE is loaded and running
            data = self.prog_executive_object.read_flash_by_proxy(self.prog_executive_proxy, int(byte_address), numbytes)
        else:
            # Invoke read by proxy
            data = self.device_proxy.invoke_read(bytes_to_read=numbytes, method=self.device_model.read_flash,
                                                byte_address=int(byte_address), numbytes=numbytes)

        return data

    def write_flash_memory(self, address, data):
        """
        Write flash memory
        :param address: start address
        :param data: data to write
        """
        if self.use_pe:
            # Enable eICSP mode (PE mode) only when we need it
            self.enter_tmod_pe()

        if self.options['overlapped_usb_access']:
            self._write_flash_block_overlapped(address, data)
        else:
            self._write_flash_block(address, data)

        if self.use_pe:
            # Default is normal ICSP mode so we revert to this mode when current operation is done
            self.enter_tmod()

    @staticmethod
    def chunks(data, chunk_size):
        """
        Yield successive chunk_size-sized chunks from data
        """
        for i in range(0, len(data), chunk_size):
            yield data[i:i + chunk_size]

    @staticmethod
    def pad(data, pagesize):
        """
        Pad a chunk before sending
        :param data: data to pad
        :param page_size: pad to make data a multiple of this size
        :return: padded chunk
        """
        # Avoid messing with the data object directly as it might have unintended side effects (like changing the stored PE or DE)
        padded_data = bytearray()
        padded_data.extend(data)
        while len(padded_data) % pagesize:
            padded_data.append(0xFF)
        return padded_data

    def _write_flash_block(self, byte_address, data):
        """
        Writes flash
        :param byte_address:    byte address to start writing from
        :param data:            data to write
        """
        self.logger.debug("Flash block write")

        # ATI chunking
        # TODO: read out from ATI
        chunksize = 512

        # Make sure the chunk size is a multiple of the page size as we can only write full pages
        pagesize = self.device_object.get_flash_write_row_size_bytes()
        chunksize -= chunksize % pagesize

        for chunk in self.chunks(data, chunksize):
            if not is_blank(chunk):
                self.logger.info("Writing %d bytes to byte address 0x%04X", len(chunk), byte_address)

                # MPLAB is supposed to always write complete pages but in the past it has in some situations not done so (MPLABX-4885)
                # So as a safety mechanism against the GEN4 script hanging we do add padding here if needed.
                self.logger.debug("Padding memory chunk to ensure a complete page is written")
                padded_chunk = self.pad(chunk, pagesize)

                self._write_flash_chunk(byte_address, padded_chunk)

            # Increment address
            byte_address += chunksize

    def _write_flash_chunk(self, byte_address, data):
        """
        Write a chunk of flash
        :param byte_address:    start byte address
        :param data:            data bytearray to program
        """
        self.logger.debug("Flash chunk write")

        # Store flag for later write-back
        use_pe_original = self.use_pe

        if self.use_pe:
            # We can't use PE mode for config words even though they are implemented as normal flash. This is because config words might mess up the PE execution for example if clocks are changed or debug is enabled
            # Note greater than (not greater than or equal) because byte_address + bytes to be written will point to first memory location after the memory that is currently about to be written
            if (byte_address + len(data)) > self.device_object.get_config_start_address_byte():
                # Temporary change the flag
                self.use_pe = False
                # Leave the PE mode
                self.exit_tmod()
                # Enter normal ICSP mode
                self.enter_tmod()

        numbytes = len(data)

        if self.use_pe:
            # Using Programming Executive (PE), assuming PE is loaded and running
            self.prog_executive_object.write_flash_page_by_proxy(self.prog_executive_proxy, int(byte_address), data)
        else:
            self.device_proxy.invoke_write(data_to_write=data, method=self.device_model.write_flash_page,
                                        byte_address=int(byte_address), numbytes=numbytes)
            # TODO - check result

            if use_pe_original:
                # Recover flag in case we had to temporary change it
                self.use_pe = use_pe_original
                # Leave normal mode
                self.exit_tmod()
                # Back to PE mode
                self.enter_tmod_pe()

    def _verify_flash_block(self, byte_address, data, silent_early_exit=False):
        """
        Verify Block
        """
        self.logger.info("Reading flash (%d bytes from word address 0x%04X)", len(data), byte_address)
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
                    self.logger.error("Flash verify error at 0x%04X (wrote 0x%02X; read 0x%02X)",
                                      ((byte_address + i) // 2), data[i], read_back[i])
        if numerrors > 0:
            self.logger.error("%d verification errors", numerrors)
            return False
        return True


    def _write_config_word(self, byte_address, data):
        """
        Write config words
        """
        raise NotImplementedError("Implementation missing for GEN4-script driver")

    def erase(self, byte_address=None):
        """
        Erase the device
        """
        # Use address if provided
        self.device_proxy.invoke(self.device_model.bulk_erase, byte_address=byte_address)

    def erase_de_memory(self, byte_address, numbytes):
        """
        Erase the Debug Executive
        :param byte_address: start address
        :param numbytes: number of bytes
        """
        self.logger.info("Erase DE mem %d bytes at byte address 0x%08X", numbytes, byte_address)
        data = self.device_proxy.invoke(method=self.device_model.erase_testmem_range, byte_address=int(byte_address),
                                        numbytes=numbytes)
        self.logger.info("Done")

    def write_pe_memory(self, byte_address, data):
        """
        Write Program Executive memory
        :param byte_address: start address
        :param data: data to write
        """
        self.logger.info("Writing PE to address 0x%06X", byte_address)
        # We must always write complete pages for PIC24 so we have to pad the data. This is done by MPLAB for normal program memory
        padded_data = self.pad(data, self.device_object.get_flash_write_row_size_bytes())
        self._write_flash_block(byte_address, padded_data)

    def erase_pe_memory(self, byte_address, numbytes):
        """
        Erase the Program Executive
        :param byte_address: start address
        :param numbytes: number of bytes
        """
        self.logger.info("Erase PE mem %d bytes at byte address 0x%08X", numbytes, byte_address)
        data = self.device_proxy.invoke(method=self.device_model.erase_testmem_range, byte_address=int(byte_address),
                                        numbytes=numbytes)
        self.logger.info("Done")

    def write_de_memory(self, byte_address, data):
        """
        Write DE memory
        :param byte_address: start address
        :param data: data to write
        """
        self.logger.info("Writing DE to address 0x%06X", byte_address)
        # We must always write complete pages for PIC24 so we have to pad the data. This is done by MPLAB for normal program memory
        padded_data = self.pad(data, self.device_object.get_flash_write_row_size_bytes())
        self._write_flash_block(byte_address, data)

    def write_config_memory(self, address, data):
        """
        Write config memory
        :param address: start address
        :param data: data to write
        """
        raise NotImplementedError("Implementation missing for GEN4-script driver")

    def start_programming_operation(self, program_pe=True):
        """
        Start programming
        :param program_pe: Program Programming Executive into device
        """
        self.use_pe = False

        # First check if a Programming Executive (PE) is already present in the device
        pe_version_current = None
        pe_version_match = False
        # No point in checking PE version if no PE version has been specified and the program PE flag is set.
        # In that case we always have to verify the PE by reading it out.
        if not program_pe or self.program_exec_version is not None:
            try:
                self.logger.debug("Attempt PE communication")
                pe_version_current = self.enter_tmod_pe()

                # First we just check if the correct PE is already present
                if self.program_exec_version is not None and pe_version_current is not None:
                    if (pe_version_current & 0xFF) == (self.program_exec_version & 0xFF):
                        self.use_pe = True
                        pe_version_match = True
                        self.logger.info("PE version match, no need to program PE")
            except:
                self.logger.debug("Could not contact PE")
                pass

        if program_pe and not pe_version_match:
            if self.program_exec_address is None:
                self.logger.warning("Program Executive not set! Reverting to normal ICSP mode")
            else:
                self.enter_tmod()
                self.logger.info("Checking PE")
                status = True
                if self._verify_flash_block(self.program_exec_address, self.program_exec_data, silent_early_exit=True):
                    self.logger.info("PE OK")
                else:
                    self.logger.info("Erasing PE")
                    self.erase_pe_memory(self.program_exec_address, len(self.program_exec_data))
                    self.logger.info("Writing PE")
                    self.write_pe_memory(self.program_exec_address, self.program_exec_data)
                    self.logger.info("Verifying PE")
                    status = self._verify_flash_block(self.program_exec_address, self.program_exec_data)
                self.exit_tmod()
                if not status:
                    self.use_pe = False
                    self.logger.error("PE verification failed!")
                    raise Exception("Error writing programming executive!")
                else:
                    self.use_pe = True
        elif self.program_exec_version is None:
            if pe_version_current is not None:
                self.logger.info("No PE version specified - using PE already present")
                self.use_pe = True
            else:
                self.logger.info("No PE available, use normal ICSP mode")

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
                # Store flag for later write-back
                use_pe_original = self.use_pe

                # No PE usage when programming the DE as the PE won't work when Debug enable config bit
                # has been set (which normally happens before the debug session is initialized)
                self.use_pe = False

                self.enter_tmod()
                self.logger.info("Checking DE")
                status = True
                if self._verify_flash_block(self.debug_exec_address, self.debug_exec_data, silent_early_exit=True):
                    self.logger.info("DE OK")
                else:
                    self.logger.info("Erasing DE")
                    self.erase_de_memory(self.debug_exec_address, len(self.debug_exec_data))
                    self.logger.info("Writing DE")
                    self.write_de_memory(self.debug_exec_address, self.debug_exec_data)
                    self.logger.info("Verifying DE")
                    status = self._verify_flash_block(self.debug_exec_address, self.debug_exec_data)
                self.exit_tmod()

                # Revert the PE flag since we are done with DE programming
                self.use_pe = use_pe_original
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
        self._in_tmod_pe = False

    def end_debug_session(self):
        """
        End debug session
        """
        raise NotImplementedError("Implementation missing for GEN4-script driver")

    def _check_de_response(self, result):
        """
        Checks the DE response
        :param result: raw response
        :return:
        """
        cmd = result[0]
        if cmd == self.DE_COMMAND or cmd == self.DE_COMMAND_DATA_ONLY:
            self.logger.info("DE response: %X %X %X %X", result[0], result[1], result[2], result[3])
            status = result[1]
            # TODO: formalise these exceptions if they prove useful (and testable)
            if status == 0x81:
                raise Exception("Timeout waiting for DE handshake to signal clock high")
            if status == 0x82:
                raise Exception("Timeout waiting for DE handshake to signal clock low")
            if status == 0x83:
                raise Exception("Timeout waiting for DE transfer to signal clock high")
            if status == 0x84:
                raise Exception("Timeout waiting for DE transfer to signal clock low")
            if status == 0x85:
                raise Exception("Timeout waiting for DE transfer to signal data low")

    def debug_read_memory(self, address, length):
        """
        Read memory in debug mode
        :param address: start address
        :param length: number of bytes to read
        :return:
        """
        self.logger.debug("Read RAM of %d byte(s) from %d", length, address)

        # Setup read request
        de_command = self.debug_executive_object.de_command_memory32_read(address, int(length))

        # Execute via proxy
        result = self.debug_executive_proxy.invoke_write_read(de_command, length, self.debug_executive_model.read_ram,
                                                              numbytes=int(length))
        return result

    def debug_write_memory(self, address, data, length):
        """
        Write memory in debug mode
        :param address: start address
        :param data: data to write
        :param length: number of bytes to write
        :return:
        """
        self.logger.debug("Write RAM of %d byte(s) to address %d", length, address)

        # Setup write request
        de_command = self.debug_executive_object.de_command_memory32_write(address, int(length))

        # Add data
        de_command.extend(data)

        result = self.debug_executive_proxy.invoke_write(data_to_write=de_command,
                                                         method=self.debug_executive_model.write_ram,
                                                         numbytes=int(length))
        self._check_de_response(result)

    def debug_read_emulation(self, address, length):
        """
        Read memory in debug mode
        :param address: start address
        :param length: number of bytes to read
        :return:
        """
        self.logger.debug("Read emulation mem of %d byte(s) from %d", length, address)

        # Setup read request
        de_command = self.debug_executive_object.de_command_memory24_read(address, int(length) // 2)

        # Execute via proxy
        result = self.debug_executive_proxy.invoke_write_read(de_command, length,
                                                              self.debug_executive_model.read_emulation,
                                                              numbytes=int(length))
        return result

    def debug_write_emulation(self, address, data, length):
        """
        Write memory in debug mode
        :param address: start address
        :param data: data to write
        :param length: number of bytes to write
        :return:
        """
        self.logger.debug("Write emulation mem of %d byte(s) to address %d", length, address)

        # Setup write request
        de_command = self.debug_executive_object.de_command_memory24_write(address, int(length) // 2)

        # Add data
        de_command.extend(data)

        result = self.debug_executive_proxy.invoke_write(data_to_write=de_command,
                                                         method=self.debug_executive_model.write_emulation,
                                                         numbytes=int(length))
        self._check_de_response(result)

    def debug_erase(self, address):
        """
        Erase flash memory in debug mode
        :param address: page start address
        :return:
        """
        raise NotImplementedError("Implementation missing for GEN4-script driver")

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
        # TODO: differentiate between failure code and bogus PC once a test-case exists

        pc = binary.unpack_le32(resp) & 0xFFFF
        self.logger.debug("PC read as:")
        self.logger.debug(pc)
        return pc

    def set_pc(self, pc):
        """
        Write the PC
        :param pc: PC value
        """
        raise NotImplementedError("Implementation missing for GEN4-script driver")

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
            self.logger.info("Restarting debug...")
            # No need to re-program the DE
            self.init_debug_session(False)
            self.logger.info("Done")

    def release_from_reset(self):
        """
        Release from reset (programming session)
        """
        self.logger.info("Release from reset")
        self.device_proxy.invoke(self.device_model.release_from_reset)

    def hold_in_reset(self):
        """
        Hold in reset (programming session)
        """
        self.device_proxy.invoke(self.device_model.hold_in_reset)

    def debug_read_de_version(self):
        """
        Read Debug Exec version
        """
        self.logger.info("Read DE version")

        data = self.debug_executive_proxy.invoke_read(bytes_to_read=4,
                                                      method=self.debug_executive_model.read_de_version)
        self.logger.info("DE version len: %d", len(data))
        self.logger.info("DE version: %d.%d.%d", data[0], data[1], data[2])
        return data

    def debug_write_flash(self, byte_address, data):
        """
        Write flash in debug mode
        :param byte_address: start address
        :param data: data to write
        """
        raise NotImplementedError("Implementation missing for GEN4-script driver")

    def debug_read_flash(self, byte_address, numbytes):
        """
        Read flash in debug mode
        :param byte_address: start address
        :param numbytes: number of bytes to read
        :return:
        """
        self.logger.info("Read flash memory of %d bytes from byte address %d", numbytes, byte_address)

        # PIC24 DE packs flash data according to prog spec, i.e. 2 24-bit instructions packed into 6 bytes/3 words
        # (16-bit words). The bytes parameter we get in is number of bytes to read where each 24-bit
        # instruction actually takes up 4 bytes in the memory map, i.e. 2 16-bit words or 32 bits.
        # Since data is packed we only have to transfer numbytes*(3/4)
        # TODO: this massaging should not really be done on this layer
        numbytes_actual = (numbytes * 3) // 4

        # Gather chunks
        result = bytearray()

        # TODO: read out from ATI
        chunk_size_bytes = 512

        # The chunk size must be possible to split into an integer number of n byte "packs"
        chunk_size_bytes -= chunk_size_bytes % self.debug_executive_object.de_read_flash_pack_size()

        # Loop until done
        while numbytes_actual > 0:
            # One chunk should not cross the 16-bit boundary for word address (i.e. 0x20000 byte address)
            # see MPLABX-4374
            # Remember each 3 bytes corresponds to one 24-bit instruction which takes up four bytes in the memory map
            if byte_address < 0x20000 and (byte_address + (chunk_size_bytes * 4) // 3) >= 0x20000:
                # Only read the memory locations up to the 16-bit boundary for word address
                temp_chunk_size_bytes = ((0x20000 - byte_address) * 3) // 4
            else:
                temp_chunk_size_bytes = chunk_size_bytes

            # Handle leftovers
            if temp_chunk_size_bytes > numbytes_actual:
                temp_chunk_size_bytes = numbytes_actual

            # Setup read request. The DE will transfer 4 packed instructions (24-bit instructions taking up 2 words
            # in the memory space) per loop which results in 12 actual bytes of data
            # The DE takes word (16-bit word) address
            de_command = self.debug_executive_object.de_command_read_flash(byte_address // 2, temp_chunk_size_bytes)

            # Execute via proxy
            chunk = self.debug_executive_proxy.invoke_write_read(de_command, temp_chunk_size_bytes,
                                                                 self.debug_executive_model.debug_read_flash,
                                                                 numbytes=int(temp_chunk_size_bytes))

            # Check for problems
            if not chunk:
                self.logger.error("Unable to read flash from debug executive! Aborting.")
                return result

            # Remember each 3 bytes corresponds to one 24-bit instruction which takes up four bytes in the memory map
            byte_address += (temp_chunk_size_bytes * 4) // 3
            # TODO: this massaging should not really be done on this layer
            numbytes_actual -= temp_chunk_size_bytes

            result.extend(chunk)
            self.logger.debug("Reading flash data (%d bytes remaining)", numbytes_actual)

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
        raise NotImplementedError("Implementation missing for GEN4-script driver")
