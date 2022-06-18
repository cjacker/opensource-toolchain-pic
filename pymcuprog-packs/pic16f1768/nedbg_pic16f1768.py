"""
This file contains mappings from the RI4 controller inside MPLAB
to a python-based programmer/debugger
"""
import os
import logging

# Logging configuration
from common.mplablog import setup_logger
# Import driver model provider for debugger variants
from common.debugprovider import provide_debugger_model
from common.primitiveutils import PrimitiveException

from common.terminaloutput import TerminalOutput
terminal = TerminalOutput(msg)

# save CWD: in the Jython environment inside MPLAB it is only valid at load time
global current_working_dir
current_working_dir = os.getcwd()


def query_prog_addr_mode():
    """
    What kind of addressing is used in prog mode
    :return:
    0: architecture dependent
    1: linear
    """
    return 1


def query_debug_addr_mode():
    """
    What kind of addressing is used in debug mode
    :return:
    0: architecture dependent
    1: linear
    """
    return 1


def query_prog_data_mode():
    """
    What kind of data format is used in prog mode
    :return:
    0: architecture dependent
    1: raw bytes
    """
    return 1


def query_debug_data_mode():
    """
    What kind of data format is used in debug mode
    :return:
    0: architecture dependent
    1: raw bytes
    """
    return 1


# This is an API mapper for: <extracted from filename in the form tool_device.py>
global device_name
device_name = device.lower()

# Configure the logging module
# "log" is a global object injected by mplab
setup_logger(log, current_working_dir)

# Get a logger object
global logger
logger = logging.getLogger()
logger.info("Creating debugger")

# Build debugger stack for this device
global debugger
debugger = provide_debugger_model(device_name)


def begin_communication_session():
    """
    Session is starting. Initialize globals
    """
    terminal.display("API command: Begin communication session\n")
    # re-initialize the logging setup, the user may have changed log levels in the GUI.
    setup_logger(log, current_working_dir)

    options = {}
    options['skip_blank_pages'] = True
    options['overlapped_usb_access'] = False
    # Initialise stack with given transport and options
    # 'tool' object is injected by MPLAB, and is a handle to the MPLABCOMM HID interface
    debugger.setup_session(tool, options)


def end_communication_session():
    terminal.display("API command: End communication session\n")
    debugger.teardown_session()
    return


# Session / reset handling

def start_programming_operation():
    """
    Enters programming mode (TMOD)
    """
    terminal.display("API command: Start programming operation\n")
    debugger.start_programming_operation()


def end_of_operations():
    """
    Terminate session
    """
    terminal.display("API command: End of operations\n")
    debugger.end_of_operations()


def hold_in_reset():
    """
    Post session reset handler:
    Hold target in reset
    """
    terminal.display("API command: Hold in reset\n")
    debugger.hold_in_reset()


def release_from_reset():
    """
    Post session reset handler:
    Release target from reset
    """
    terminal.display("API command: Release from reset\n")
    debugger.release_from_reset()


# MPLAB Programmming API


def erase():
    """
    Bulk erase device
    """
    terminal.display("API command: Erase\n")
    debugger.erase()


def prog_write(type_of_mem, address, length, data):
    """
    Write memory to target
    :param type_of_mem: memory area/type
    :param address: start address
    :param data: data content to write
    :param length: size of data
    """
    terminal.display("API command: Write {:d} bytes to address 0x{:06X} of {} memory\n".format(length, address, type_of_mem))

    # Device support scripts always use byte addressing mode
    byte_address = address

    eeprom_data_size_bytes = 1

    # Memory types are handled differently
    if str(type_of_mem) == "Pgm":
        # Program memory
        debugger.write_flash_memory(byte_address, data)
    elif str(type_of_mem) == "Cfg":
        # Config words
        debugger.write_config_memory(byte_address, data)
    elif str(type_of_mem) == "UserOTP":
        # OTP.  Just ignore.
        terminal.display("Write OTP - ignored.\n")
    elif str(type_of_mem) == "EEData":
        # EEPROM
        if "pic16" in device_name:
            # MPLAB X does not comply with the query_prog_data_mode() setting and sends a word address for pic16 EEPROM
            debugger.write_eeprom_memory(byte_address*2, data)
        else:
            debugger.write_eeprom_memory(byte_address, data)
    elif str(type_of_mem) == "UserID":
        # User ID memory
        debugger.write_user_id_memory(byte_address, data)
    else:
        terminal.display("Unknown memtype: {}!\n".format(str(type_of_mem)))


def copy_data(source, destination):
    """
    Deep copy from source to destination
    :param source: from
    :param destination: to
    """
    if len(source) > len(destination):
        message = "Data size mismatch: {} byte(s) read from {}, but MPLAB X only accepted {} byte(s).".format(
            len(source),
            device_name,
            len(destination)
            )
        terminal.display("WARNING - {}\n".format(message))
        terminal.show_info_dialog_non_blocking("{}".format(message))

    for i in xrange(min(len(source), len(destination))):
        destination[i] = source[i]


def prog_read(type_of_mem, address, length, data):
    """
    Read memory from target
    :param type_of_mem: memory area/type
    :param address: start address
    :param data: data returned
    :param length: number of bytes to read
    """
    terminal.display("API command: Read {} bytes from address 0x{:06X} of {} memory\n".format(length, address, type_of_mem))
    # Device support scripts always use byte addressing mode
    byte_address = address
    eeprom_data_size_bytes = 1

    if str(type_of_mem) == "Pgm":
        # Program memory
        copy_data(debugger.read_flash_memory(byte_address, length), data)
    elif str(type_of_mem) == "Cfg":
        # Config words
        copy_data(debugger.read_config_memory(byte_address, length), data)
    elif str(type_of_mem) == "EEData":
        # EEPROM memory

        # For devices with word access to EEPROM there will be a padding byte for each data byte. We have to discard
        # the pad bytes before sending the data back to MPLAB
        temp_data = [0] * length * eeprom_data_size_bytes
        if "pic16" in device_name:
            # MPLAB X does not comply with the query_prog_data_mode() setting and sends a word address for pic16 EEPROM
            copy_data(debugger.read_eeprom_memory(byte_address*2, length * eeprom_data_size_bytes), temp_data)
        else:
            copy_data(debugger.read_eeprom_memory(byte_address, length * eeprom_data_size_bytes), temp_data)
        for dataindex in range(0, len(temp_data), eeprom_data_size_bytes):
            data[dataindex // eeprom_data_size_bytes] = temp_data[dataindex]
    elif str(type_of_mem) == "UserID" or str(type_of_mem) == "Test":
        # User ID/Test memory
        copy_data(debugger.read_flash_memory(byte_address, length), data)
    else:
        terminal.display("Unknown memtype: {}!\n".format(str(type_of_mem)))
        data = bytearray([])

def set_program_exec(address, data, pe_version=None):
    """
    Set the program executive.
    :param address: PE address
    :param data: PE content
    :param pe_version: One byte version (Upper nibble is major version and lower nibble is minor version)
    """
    terminal.display("Set Programming Executive ({:d} bytes at address 0x{:06X})\n".format(len(data), address))
    if pe_version is not None:
        terminal.display("Programming Executive version: {:x}.{:x}\n".format((pe_version & 0xF0) >> 4, pe_version & 0x0F))

    # Device support scripts always use byte addressing mode
    byte_address = address
    debugger.set_program_exec(byte_address, data, pe_version)

def set_debug_exec(address, data):
    """
    Set the debug executive.
    :param address: DE address
    :param data: DE content
    """
    terminal.display("Set Debug Executive ({:d} bytes at address 0x{:06X})\n".format(len(data), address))

    # Device support scripts always use byte addressing mode
    byte_address = address
    debugger.set_debug_exec(byte_address, data)


# MPLAB Debugging API


def begin_debug_session():
    """
    Start debug session
    """
    terminal.display("API command: Init debug session\n")

    # Now enter debug
    # At this point, if the DE fails to communicate for whatever reason, we report to the user and abort.
    try:
        debugger.init_debug_session()
    except PrimitiveException as e:
        message = "Exception communicating with debug executive: 0x{0:08X}\n".format(e.code)
        logger.error(message)
        terminal.display(message)
        message = "Be sure to select the correct debug pins in device configuration.\n"
        logger.error(message)
        terminal.display(message)
        raise Exception("Unable to communicate with DE")


def end_debug_session():
    """
    End debug session
    """
    terminal.display("API command: End debug session\n")
    debugger.end_debug_session()


def run_target():
    """
    Run!
    """
    terminal.display("API command: Run\n")
    debugger.run()


def halt_target():
    """
    Halt!
    """
    terminal.display("API command: Halt\n")
    debugger.halt()


def step_target():
    """
    Step!
    """
    # Use logger here because the function is called frequently during debug
    # A single C-code step will result in x number of assembly code steps that are printed in the console
    logger.info("API command: Step\n")
    debugger.step()


def reset_target():
    """
    Reset!
    """
    terminal.display("API command: Reset\n")
    debugger.reset_target()


def is_target_running():
    """
    Run/stopped state query
    """
    # Use logger here because the function is called frequently during debug
    logger.debug("API command: Is target running?")
    return debugger.is_running()


def debug_write(mem_type, start, length, data):
    """
    Write memory in debug mode
    :param mem_type: memory area/type
    :param start: start address
    :param data: data to write
    :param length: length in bytes
    :return:
    """
    numlocations = length
    # Use logger here because the function is called frequently during debug
    logger.info("API command: Write start address 0x{:06X}, {:06X} bytes of {} memory".format(start, length, mem_type))
    if str(mem_type) == "Emulation":
        if "pic24" in device_name or "pic18" in device_name:
            debugger.debug_write_emulation(start, data, numlocations)
        else:
            debugger.debug_write_memory(start, data, numlocations)
    elif str(mem_type) == "FileRegs":
        debugger.debug_write_memory(start, data, numlocations)
    else:
        terminal.display("Unknown memtype: {}!\n".format(str(mem_type)))


def debug_read(mem_type, start, length, data):
    """
    Read memory in debug mode
    :param mem_type: memory area/type
    :param start: start address
    :param data: data to read
    :param length: length in bytes
    """

    numbytes = length
    # Use logger here because the function is called frequently during debug
    logger.info("API command: Read start address 0x{:06X}, 0x{:06X} bytes of {} memory".format(start, length, mem_type))

    if str(mem_type) == "Emulation":
        if "pic24" in device_name or "pic18" in device_name:
            copy_data(debugger.debug_read_emulation(start, numbytes), data)
        else:
            copy_data(debugger.debug_read_memory(start, numbytes), data)
    elif str(mem_type) == "FileRegs":
        copy_data(debugger.debug_read_memory(start, numbytes), data)
    elif str(mem_type) == "Pgm":
        copy_data(debugger.debug_read_flash(start, numbytes), data)
    elif str(mem_type) == "EEData":
        copy_data(debugger.debug_read_eeprom(start, numbytes), data)
    elif str(mem_type) == "Cfg" or str(mem_type) == "UserID" or str(mem_type) == "Test":
        # All these memory types are flash but residing in "Test / Configuration memory space"
        copy_data(debugger.debug_read_test(start, numbytes), data)
    else:
        terminal.display("Unknown memtype: {}!\n".format(str(mem_type)))
        data = bytearray([])


def set_sw_bp(address, instruction, flags):
    """
    Insert or remove software breakpoints
    :param address: address to probe
    :param instruction: instruction to insert
    :param flags: parameter to ignore
    :return: instruction which was replaced
    """
    terminal.display(
        "API command: Set program break at address 0x{:06X}, store instructions 0x{:06X}, flags = 0x{:04X}\n".format(
            address, instruction, flags))
    return debugger.set_sw_bp(address, instruction, flags)


def get_pc():
    """
    Read the PC
    :return: PC value
    """
    # Use logger here because the function is called frequently during debug
    logger.info("API command: Get PC\n")
    pc = debugger.get_pc()
    return pc


def set_pc(pc):
    """
    Set the PC
    :param pc: PC value
    """
    terminal.display("API command: Set pc to 0x{:06X}\n".format(pc))
    if "pic24" in device_name:
        # For PIC24 devices there is no separate set_pc command. Instead we write to a specific memory location
        # (found by debugging ICD4 code in MPLAB)
        debug_write("FileRegs", 0x2E, 3, [pc & 0xFF, (pc >> 8) & 0xFF, (pc >> 16) & 0xFF])
    else:
        debugger.set_pc(pc)


# Unimplemented API functions


def set_hw_bp(number, address):
    """
    Set hardware breakpoint
    """
    terminal.display("API command: Set hardware breakpoint number {:d} at address 0x{:06X}\n".format(number, address))
    raise NotImplementedError("Function not implemented!")


def clear_hw_bp(number):
    """
    Clear hardware breakpoint
    """
    terminal.display("API command: Clear hardware breakpoint number {:d}\n".format(number))
    raise NotImplementedError("Function not implemented!")


def verify_transfer(type_of_mem, address, data, length):
    """
    Verify memory
    """
    terminal.display(
        "API command: Verifying {:d} bytes to address 0x{:06X} of {} memory\n".format(length, address, type_of_mem))
    raise NotImplementedError("Function not implemented!")


def blank_check():
    """
    Blank-check memory
    """
    terminal.display("API command: Blank check (TODO: not implemented!)\n")
