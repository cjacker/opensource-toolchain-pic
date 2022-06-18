import logging
from pyedbglib.primitive import primitives


class PrimitiveFunction(object):
    def __init__(self, model_object):
        self.logger = logging.getLogger(__name__)
        # Store the model object for later 'execution' of functions
        self.model_object = model_object


class PrimitiveResourceProvider(object):
    def programming_interface(self, variant):
        raise Exception("Resource not implemented")

    def debug_interface(self, family):
        raise Exception("Resource not implemented")

    def board_interface(self):
        raise Exception("Resource not implemented")

    def pin_driver(self):
        raise Exception("Resource not implemented")


class BoardInterface(object):
    def delay_ms(self, milli_seconds):
        raise Exception("Board interface not implemented")

    def delay_us(self, micro_seconds):
        raise Exception("Board interface not implemented")


class HardwareInterface(object):
    def set_clk(self):
        raise Exception("Hardware interface not implemented")

    def clr_clk(self):
        raise Exception("Hardware interface not implemented")

    def _pins(self, value):
        raise Exception("Hardware interface not implemented")

    def get_pins(self):
        raise Exception("Hardware interface not implemented")

    def set_clk_in_data_in(self):
        self._pins(primitives.ICSP_PINS_CLK_IN_DATA_IN)

    def set_clk_high_data_low(self):
        self._pins(primitives.ICSP_PINS_CLK_HIGH_DATA_LOW)

    def set_all_pins_low(self):
        self._pins(primitives.ICSP_PINS_ALL_LOW)

    def set_mclr_high(self):
        raise Exception("Hardware interface not implemented")

    def set_mclr_low(self):
        raise Exception("Hardware interface not implemented")


class DebugInterface(object):
    def debug_command(self, de_cmd, bytes_out, bytes_in):
        raise Exception("Debug interface not implemented")

class ProgramExecInterface(object):
    def send_word(self, word):
        raise Exception("Program exec interface not implemented")

    def receive_word(self):
        raise Exception("Program exec interface not implemented")

    def handshake(self):
        raise Exception("Program exec interface not implemented")