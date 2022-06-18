"""
PrimitivePrinter

Used for executing simple primitive sequences and getting nothing but text out
"""
from proginterfaceprovider import ProgInterfaceIcspC8D24
from proginterfaceprovider import ProgInterfaceIcspC6D16
from proginterfaceprovider import ProgInterfaceGen4

from primitivebase import PrimitiveFunction
from primitivebase import PrimitiveResourceProvider
from primitivebase import DebugInterface
from primitivebase import BoardInterface
from primitivebase import HardwareInterface
from primitivebase import ProgramExecInterface
from primitiveproxy import PrimitivePrinterProxy

from primitiveaccumulator import PrimitiveFunctionAccumulator

from primitiveutils import process_primitive_sequence

import xml.etree.ElementTree as ETree

SCRIPT_IDS = {
    'enter_tmod': 0,
    'read_id': 1,
    'bulk_erase': 2,
    'write_flash': 3,
    'write_flash_page': 3,
    'write_config': 4,
    'write_config_word': 4,
    'exit_tmod': 5,
    'read_flash': 6,
    'write_eeprom': 7,
    'write_id': 8,
    'write_user_id_word': 8,
    'read_eeprom': 9,
    'read_config': 10,
    'skip_page': 11,

}


def sequence_to_xml(script_id, tokens, sequence):
    """
    Generates simple XML text output.
    Can be used for making config
    :param script_id: script ID to embed
    :param tokens: tokens to encode
    :param sequence: primitive sequence content
    <type>PRIMITIVE_SEQUENCE</type>
    <id>x</id>
    <data>a, b, c...</data>
    :return: xml 'entry' element
    """
    # Convert sequence to string
    from primitiveutils import array_to_hexstring
    sequence_string = array_to_hexstring(sequence)

    # Convert tokens to array
    from primitiveutils import tokens_to_array
    token_array = tokens_to_array(tokens)
    # Then to string
    token_string = array_to_hexstring(token_array)

    # Concatenate
    data = token_string + sequence_string
    # Strip
    if data.endswith(", "):
        data = data[:-2]

    xml_entry = ETree.Element("entry")
    xml_type = ETree.SubElement(xml_entry, "type").text = "PRIMITIVE_SEQUENCE"
    xml_id = ETree.SubElement(xml_entry, "id").text = "{0:d}".format(script_id)
    xml_data = ETree.SubElement(xml_entry, "data").text = data

    return xml_entry


class PrimitiveResourceProviderPrinter(PrimitiveResourceProvider):
    """
    Resource provider for printing
    """

    def __init__(self, printer):
        self.printer = printer

    def programming_interface(self, variant):
        if variant == ProgInterfaceIcspC8D24:
            return ProgInterfaceIcspC8D24Printer(self.printer)
        elif variant == ProgInterfaceIcspC6D16:
            return ProgInterfaceIcspC6D16Printer(self.printer)
        elif variant == ProgInterfaceGen4:
            return ProgInterfaceGen4Printer(self.printer)
        else:
            raise Exception("Invalid ICSP variant requested.")

    def debug_interface(self, family):
        return DebugInterfacePrinter(self.printer)

    def board_interface(self):
        return BoardInterfacePrinter(self.printer)

    def pin_driver(self):
        return HardwareInterfacePrinter(self.printer)

    def program_exec_interface(self):
        return ProgramExecInterfacePrinter(self.printer)


class PrimitiveFunctionPrinter(PrimitiveFunction):
    """
    Function provider for printer output
    """

    def __init__(self, model_object):
        PrimitiveFunction.__init__(self, model_object)
        self.logger.info("Using primitive printer")
        self.printer = PrimitivePrinterProxy()
        provider = PrimitiveResourceProviderPrinter(self.printer)
        self.model_object.initialise(provider)

    def invoke(self, method, **kwargs):
        """
        Invokes a given method with arguments - no data
        """
        self.printer.reset()
        self.printer.append("> Primitive printer: %s" % method.__name__)
        method(self.model_object, **kwargs)
        self.logger.info(self.printer.get_content())
        return bytearray([0x00]*4)

    def invoke_read(self, bytes_to_read, method, **kwargs):
        """
        Invokes a given method with arguments - data is read back
        """
        self.invoke(method, **kwargs)
        # Just return dummy data
        return bytearray([0xDD]*bytes_to_read)

    def invoke_write(self, data_to_write, method, **kwargs):
        """
        Invokes a given method with arguments - data is written
        """
        # pylint: disable=unused-argument
        return self.invoke(method, **kwargs)

    def invoke_write_read(self, data_to_write, bytes_to_read, method, **kwargs):
        """
        Invokes a given method with arguments - data is written and read
        """
        self.invoke(method, **kwargs)

        return bytearray([0xDD]*bytes_to_read)

class PrimitiveFunctionXmlGenerator(PrimitiveFunctionAccumulator):
    """
    Function provider for XML output
    """

    def __init__(self, model_object, tool):
        PrimitiveFunctionAccumulator.__init__(self, model_object)
        self.logger.info("XML output")
        self.xml_tool = tool

    def invoke(self, method, bytes_to_read=0, **kwargs):
        """
        Invokes a given method with arguments - no data
        """
        self.logger.info("Using XML generator")
        content = PrimitiveFunctionAccumulator.invoke(self, method, **kwargs)
        self.logger.debug("Raw content: %s", content)
        sequence, tokens = process_primitive_sequence(content)
        self.logger.debug("Sequence: %s", sequence)
        script_id = SCRIPT_IDS[method.__name__]

        xml_entry = sequence_to_xml(script_id, tokens, sequence)
        self.xml_tool.add_new_entry(script_id, xml_entry)
        result = bytearray(bytes_to_read)
        return result

    def invoke_read(self, bytes_to_read, method, **kwargs):
        """
        Invokes a given method with arguments - data is read back
        """
        # pylint: disable=unused-argument
        return self.invoke(method, bytes_to_read, **kwargs)

    def invoke_write(self, data_to_write, method, **kwargs):
        """
        Invokes a given method with arguments - data is written
        """
        # pylint: disable=unused-argument
        return self.invoke(method, **kwargs)


class ProgInterfaceIcspC8D24Printer(ProgInterfaceIcspC8D24):
    """
    Printer output for this programming interface
    """

    def __init__(self, printer):
        ProgInterfaceIcspC8D24.__init__(self)
        self.printer = printer

    # MSB-first 4 character string literal
    def write_string_literal(self, characters):
        """
        Write a four-character literal string
        """
        self.printer.append("Write string literal: '%s'" % characters)
        if len(characters) != 4:
            raise Exception("Invalid string length")
        value = 0
        for char in characters[::-1]:
            value <<= 8
            value += ord(char)

        self.write_32bit_literal(value)

    def write_32bit_literal(self, value):
        """
        Write a 32-bit literal value
        """
        self.printer.append("Write 32-bit literal: (0x%08X)" % value)

    def write_command_literal(self, cmd):
        """
        Write an eight-bit literal value (command cycle)
        """
        self.printer.append("Write command literal (0x%02X)" % cmd)

    def write_payload_literal(self, value):
        """
        Write an twenty-four-bit literal value (data cycle)
        """
        self.printer.append("Write payload literal (0x%02X)" % value)

    def write_data_word(self):
        """
        Write a 16-bit word as a twenty-four-bit value from the data pipe (indirect write)
        """
        self.printer.append("Write data WORD")

    def write_data_byte(self):
        """
        Write a byte as a twenty-four-bit value from the data pipe (indirect write)
        """
        self.printer.append("Write data BYTE")

    def read_data_word(self):
        """
        Read a 16-bit word as a twenty-four-bit value to the data pipe (indirect read)
        """
        self.printer.append("Read data WORD")
        return 0

    def read_data_byte(self):
        """
        Read a 8-bit word as a twenty-four-bit value to the data pipe (indirect read)
        """
        self.printer.append("Read data BYTE")
        return 0

    def set_speed(self, period_ns):
        """
        Set ICSP clock period in nanoseconds
        """
        self.printer.append("Set speed, {}ns".format(period_ns))


class ProgInterfaceIcspC6D16Printer(ProgInterfaceIcspC6D16):
    """
    Printer output for this programming interface
    """

    def __init__(self, printer):
        ProgInterfaceIcspC6D16.__init__(self)
        self.printer = printer

    # MSB-first 4 character string literal
    def write_string_literal(self, characters):
        """
        Write a four-character literal string
        """
        self.printer.append("Write string literal: '%s'" % characters)
        if len(characters) != 4:
            raise Exception("Invalid string length")
        value = 0
        for char in characters[::-1]:
            value <<= 8
            value += ord(char)

        self.write_32bit_literal(value)

    def write_32bit_literal(self, value):
        """
        Write a 32-bit literal value
        """
        self.printer.append("Write 32-bit literal: (0x%08X)" % value)

    def write_command_literal(self, cmd):
        """
        Write an eight-bit literal value (command cycle)
        """
        self.printer.append("Write command literal (0x%02X)" % cmd)

    def write_payload_literal(self, value):
        """
        Write an twenty-four-bit literal value (data cycle)
        """
        self.printer.append("Write payload literal (0x%02X)" % value)

    def write_data_word(self):
        """
        Write a 16-bit word as a twenty-four-bit value from the data pipe (indirect write)
        """
        self.printer.append("Write data WORD")

    def read_data_word(self):
        """
        Read a 16-bit word as a twenty-four-bit value to the data pipe (indirect read)
        """
        self.printer.append("Read data WORD")
        return 0

    def set_speed(self, period_ns):
        """
        Set ICSP clock period in nanoseconds
        """
        self.printer.append("Set speed, {}ns".format(period_ns))

class ProgInterfaceGen4Printer(ProgInterfaceGen4):
    """
    Printer output for this programming interface
    """

    def __init__(self, printer):
        ProgInterfaceGen4.__init__(self)
        self.printer = printer

class DebugInterfacePrinter(DebugInterface):
    """
    Printer output for this debugging interface
    """

    # pylint: disable=too-few-public-methods
    def __init__(self, printer):
        self.printer = printer

    def debug_command(self, de_cmd, bytes_out, bytes_in):
        self.printer.append("Debug command %d" % de_cmd)

class ProgramExecInterfacePrinter(ProgramExecInterface):
    """
    Printer output for this Programming Executive interface
    """
    def __init__(self, printer):
        self.printer = printer

    def send_word(self, word):
        self.printer.append("send_word: 0x{:04X}".format(word))

    def send_word_buf(self):
        self.printer.append("send_word_buf")

    def receive_word(self):
        self.printer.append("receiver_word")
        return 0x1000

    def handshake(self):
        self.printer.append("handshake")

class HardwareInterfacePrinter(HardwareInterface):
    """
    Printer output for the hardware service
    """

    def __init__(self, printer):
        self.printer = printer

    def set_clk(self):
        self.printer.append("Clock HIGH")

    def clr_clk(self):
        self.printer.append("Clock LOW")

    def _pins(self, value):
        self.printer.append("Set pins")

    def get_pins(self):
        self.printer.append("Get pins")
        return 0

    def set_mclr_high(self):
        self.printer.append("MCLR HIGH")

    def set_mclr_low(self):
        self.printer.append("MCLR LOW")


class BoardInterfacePrinter(BoardInterface):
    """
    Printer output for the board service
    """

    def __init__(self, printer):
        self.printer = printer

    def delay_ms(self, milli_seconds):
        self.printer.append("Delay ms (%d)" % milli_seconds)

    def delay_us(self, micro_seconds):
        self.printer.append("Delay us (%d)" % micro_seconds)
