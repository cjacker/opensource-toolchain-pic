"""
ProgInterfaceProvider

Provices various variants of programming interfaces using primitives
"""
from pyedbglib.primitive import primitives
from primitiveutils import ParametricToken


class IcspProgInterface(object):
    """
    Base class for ICSP programming interface variants
    """

    # pylint: disable=too-few-public-methods
    def __init__(self):
        pass

class ProgInterfaceGen4(IcspProgInterface):
    """
    GEN4 uses a binary-array for programming interface
    """

    # pylint: disable=too-few-public-methods
    def __init__(self):
        IcspProgInterface.__init__(self)


class ProgInterfaceIcspPic8bit(IcspProgInterface):
    """
    PIC 8-bit ICSP programming interface variants
    """

    def __init__(self):
        IcspProgInterface.__init__(self)

    def command(self, cmd):
        """
        An ICSP command request
        """
        self.write_command_literal(cmd)

    def payload(self, value):
        """
        An ICSP payload / data-cycle request
        """
        self.write_payload_literal(value)

    def write_command_literal(self, value):
        """
        Command variant
        """
        # pylint: disable=unused-argument, no-self-use
        raise Exception("Write command literal must be implemented for this variant!")

    def write_payload_literal(self, value):
        """
        Payload variant
        """
        # pylint: disable=unused-argument, no-self-use
        raise Exception("Write payload literal must be implemented for this variant!")

    def set_speed(self, period_ns):
        """
        Set ICSP clock period in nanoseconds
        """
        # pylint: disable=unused-argument, no-self-use
        raise Exception("Write set speed must be implemented for this variant!")

class ProgInterfaceIcspC8D24(ProgInterfaceIcspPic8bit):
    """
    PIC 8-bit ICSP programming interface variant with:
    - 8-bit command structure
    - 24-bit data/payload structure
    """

    def __init__(self):
        ProgInterfaceIcspPic8bit.__init__(self)

class ProgInterfaceIcspC8D24PrimitiveGenerator(ProgInterfaceIcspC8D24):
    """
    Primitive generator for this ICSP variant
    """

    def __init__(self, target):
        ProgInterfaceIcspC8D24.__init__(self)
        self.target = target

    def write_string_literal(self, characters):
        """
        Write a four-character literal string
        """
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
        self.target.new_element(primitives.WRITE_BITS_LITERAL_MSB)
        self.target.append_byte(32)  # not ([len(value) * 8])
        if isinstance(value, ParametricToken):
            value.bytecount = 4
            self.target.add_token(value)
        else:
            self.target.append_le32(value)

    def write_command_literal(self, value):
        """
        Write an eight-bit literal value (command cycle)
        """
        self.target.new_element(primitives.WRITE_BITS_LITERAL_MSB)
        self.target.append_byte(8)
        if isinstance(value, ParametricToken):
            value.bytecount = 4
            self.target.add_token(value)
        else:
            self.target.append_le32(value)

    def write_payload_literal(self, value):
        """
        Write an twenty-four-bit literal value (data cycle)
        """
        self.target.new_element(primitives.P16ENV3_WRITE_PAYLOAD_LITERAL)
        self.target.append_byte(24)
        if isinstance(value, ParametricToken):
            value.bytecount = 4
            self.target.add_token(value)
        else:
            self.target.append_le32(value)

    def write_data_word(self):
        """
        Write a 16-bit word as a twenty-four-bit value from the data pipe (indirect write)
        """
        self.target.new_element(primitives.P16ENV3_WRITE_BUFFER)

    def write_data_byte(self):
        """
        Write a byte as a twenty-four-bit value from the data pipe (indirect write)
        """
        self.target.new_element(primitives.P16ENV3_WRITE_BUFFER_DFM)

    def read_data_word(self):
        """
        Read a 16-bit word as a twenty-four-bit value to the data pipe (indirect read)
        """
        self.target.new_element(primitives.P16ENV3_READ_PAYLOAD_PFM)
        result = self.target.sync(2)
        return result

    def read_data_byte(self):
        """
        Read a 8-bit word as a twenty-four-bit value to the data pipe (indirect read)
        """
        self.target.new_element(primitives.P16ENV3_READ_PAYLOAD_DFM)
        result = self.target.sync(1)
        return result

    def set_speed(self, period_ns):
        """
        Set ICSP clock period in nanoseconds
        """
        self.target.new_element(primitives.SET_SPEED)
        self.target.append_le32(period_ns)



class ProgInterfaceIcspC6D16(ProgInterfaceIcspPic8bit):
    """
    PIC 8-bit ICSP programming interface variant with:
    - 6-bit command structure
    - 16-bit data/payload structure
    """

    def __init__(self):
        ProgInterfaceIcspPic8bit.__init__(self)


class ProgInterfaceIcspC6D16PrimitiveGenerator(ProgInterfaceIcspC6D16):
    """
    Primitive generator for this ICSP variant
    """

    def __init__(self, target):
        ProgInterfaceIcspC6D16.__init__(self)
        self.target = target

    def write_string_literal(self, characters):
        """
        Write a four-character literal string
        """
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
        self.target.new_element(primitives.WRITE_LITERAL_32_LSB)
        if isinstance(value, ParametricToken):
            value.bytecount = 4
            self.target.add_token(value)
        else:
            self.target.append_le32(value)

    def write_command_literal(self, value):
        """
        Write an eight-bit literal value (command cycle)
        """
        self.target.new_element(primitives.WRITE_BITS_LITERAL)
        self.target.append_byte(6)
        if isinstance(value, ParametricToken):
            value.bytecount = 4
            self.target.add_token(value)
        else:
            self.target.append_le32(value)

    def write_payload_literal(self, value):
        """
        Write an twenty-four-bit literal value (data cycle)
        """
        self.target.new_element(primitives.WRITE_BITS_LITERAL)
        self.target.append_byte(16)
        if isinstance(value, ParametricToken):
            value.bytecount = 4
            self.target.add_token(value)
        else:
            self.target.append_le32(value << 1)

    def write_data_word(self):
        """
        Write a 16-bit word as a twenty-four-bit value from the data pipe (indirect write)
        """
        self.target.new_element(primitives.P16F_WRITE_LOC_BUFFER)

    def read_data_word(self):
        """
        Read a 16-bit word as a twenty-four-bit value to the data pipe (indirect read)
        """
        self.target.new_element(primitives.P16F_READ_LOC_BUFFER)
        result = self.target.sync(2)
        return result

    def set_speed(self, period_ns):
        """
        Set ICSP clock period in nanoseconds
        """
        self.target.new_element(primitives.SET_SPEED)
        self.target.append_le32(period_ns)


