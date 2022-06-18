"""
Picdevice
Defines a base class for PIC devices.
"""
import logging

# These debugger models are supported:
# a) all PIC16 devices use native Python scripting
from scriptinginterface import PythonScriptedPic16Debugger
# b) all PIC18 devices use native Python scripting
from scriptinginterface import PythonScriptedPic18Debugger
# c) all PIC24 devices use a GEN4 wrapper
from gen4engineinterface import Gen4WrapperDebugger

# These ICSP variants are supported:
# a) 6-bit command and 16-bit data
from proginterfaceprovider import ProgInterfaceIcspC6D16
# b) 8-bit command and 24-bit data
from proginterfaceprovider import ProgInterfaceIcspC8D24
# c) GEN4 wrapper
from proginterfaceprovider import ProgInterfaceGen4


# These debug executive models are supported:
# a) DE interface to PIC16 devices
from debuginterfaceprovider import DebugExecApiVx
# b) DE interface to PIC18 devices
from debuginterfaceprovider import DebugExecApiPic18Vx
# c) DE interface to PIC24 devices
from debuginterfaceprovider import DebugExecApiPic24Vx

# These programming executive models are supported:
# a) PE interface to PIC24 devices
from programexecinterfaceprovider import ProgExecInterfacePic24

class PicDevice(object):
    """
    Base class for PIC device
    """

    # Default value for ICSP clock period. This default could be overridden in the pds files by overriding this attribute
    ICSP_CLOCK_PERIOD_NS = 200

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.hw = None
        self.board = None
        self.prog = None
    def initialise(self, resourceprovider):
        """
        Initialises the device model instance with the given resource provider.
        Checks that certain requirements within the device model exist
        """
        self.hw = resourceprovider.pin_driver()
        self.board = resourceprovider.board_interface()
        try:
            self.prog = resourceprovider.programming_interface(self.PROGRAMMING_INTERFACE)
        except:
            msg = "Programming interface ('PROG') is not defined in model for '{0:s}'".format(self.__class__.__name__)
            self.logger.error(msg)
            raise NotImplementedError(msg)

        # Tests for existence
        try:
            self.get_flash_write_row_size_bytes()
        except:
            msg = "Flash row size ('FLASH_WRITE_BYTES_PER_PAGE') is not defined in model for '{0:s}'".format(
                self.__class__.__name__)
            self.logger.error(msg)
            raise NotImplementedError(msg)

    def get_flash_write_row_size_bytes(self):
        """
        Returns the flash write row size for the device, since its used by both prog and DE
        """
        return self.FLASH_WRITE_BYTES_PER_PAGE

    def get_config_start_address_byte(self):
        """
        Returns the first address of configuration memory for the device
        This parameter is only useful for PIC24 devices where config words are just normal flash
        """
        raise NotImplementedError("CONFIG_START_ADDRESS not implemented for this device")

    def set_speed(self):
        """
        Set speed.
        Sets the ICSP clock period in nanoseconds
        """
        self.prog.set_speed(self.ICSP_CLOCK_PERIOD_NS)



