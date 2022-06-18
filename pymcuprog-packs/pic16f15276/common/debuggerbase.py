"""
Base class for PIC debugger over CMSIS (ATI)
"""
import logging
import importlib

# HID substitute for when operating in MPLAB
from pyedbglib.mplabtransport.mplabtransport import MpLabTransport
from pyedbglib.protocols.cmsisdap import CmsisDapUnit

from pyedbglib.protocols.housekeepingprotocol import Jtagice3HousekeepingProtocol


class CmsisAtiPicDebugger(object):
    """
        Base wrapper for a python-based debugger
    """

    _in_tmod = False
    _in_tmod_pe = False
    _is_running = False
    _current_pe_version = 0
    logger = None

    def __init__(self, device_name):
        # Hook onto logger
        self.logger = logging.getLogger(__name__)
        # Flag: not yet initialised
        self.initialised = False

        # Store the device name
        self.device_name = device_name

        # Target state variables
        self._in_tmod = False
        self._is_running = False
        self._in_tmod_pe = False
        self._current_pe_version = 0

        # Debug exec state
        self.debug_exec_address = None
        self.debug_exec_data = None

        # Programming exec state
        self.program_exec_address = None
        self.program_exec_data = None
        self.program_exec_version = None

        # Objects start as None
        self.transport = None
        self.options = None
        self.device_model = None
        self.device_object = None
        self.device_proxy = None
        self.debug_executive_model = None
        self.debug_executive_object = None
        self.debug_executive_proxy = None
        self.controller = None

    def load_device_object(self, device_model):
        """
        Creates and stores the device object
        :param device_model: model to instantiate
        """
        self.device_model = device_model
        self.device_object = device_model()

    def teardown_session(self):
        """
        Tears down the debugger stack
        """
        # Flag as uninitialised to force a re-init
        self.logger.info("Tearing down nEDBG session...")
        self.initialised = False

    def setup_session(self, tool, options):
        """
        Configures the stack with transport and options etc and readies it for use
        :param tool: tool AKA transport mechanism
        :param options: [empty] dictionary of switches for model
        """
        self.logger.info("Setting up nEDBG session...")
        self.options = options

        # No transport specified (local/embedded execution)
        from debugprovider import ConfigGeneratorTool
        from debugprovider import EmbeddedTool
        from debugprovider import PrinterTool
        if isinstance(tool, ConfigGeneratorTool) or isinstance(tool, EmbeddedTool) or isinstance(tool, PrinterTool):
            # TODO: make embedded execution a valid transport
            return

        # Initialise transport object
        self._initialise_transport(tool)
        if not self.transport:
            self.logger.error("Unable to build tool transport!")
            return

        # Check DAP for device declaraion, in case this is an on-board debugger
        cmsis_dap_debugger = CmsisDapUnit(self.transport)
        dap_info = cmsis_dap_debugger.dap_info()
        dap_device_name = dap_info['device_name']

        # Log product info
        self.logger.info("Using CMSIS-DAP product %s (%s) with %s mounted", dap_info['product'], dap_info['serial'],
                         dap_device_name)

        # Check device info from DAP
        if dap_device_name != "" and dap_device_name.lower() != self.device_name.lower():
            # Does not look right.  Continue at own risk.
            self.logger.error("You are attempting to use a device which is not the one which was mounted on the kit!")
            self.logger.error(
                "Cut all straps between the debugger and the on-board target when accessing an external device!")
            self.logger.error(
                "Device mismatch! Project is using %s but the kit has %s mounted.  Proceed at your own risk.",
                self.device_name.lower(), dap_device_name.lower())


    def _initialise_transport(self, tool_or_transport):
        """
        Sets up the transport layer back into MPLAB
        """
        # Always do a transport init
        # Are we running standalone or inside MPLAB?
        if type(tool_or_transport).__name__ == "CyHidApiTransport":
            self.logger.info("Transport already initialised")
            self.transport = tool_or_transport
        else:
            # MPLAB type is "Controller$PacketTransfer"
            # Wrapper for MPLABCOMM
            self.logger.info("Creating transport from MPLAB AtmelIceToolExtension")
            # Re-map transport object if we are inside mplab context
            self.transport = MpLabTransport(tool_or_transport)
            self.initialised = True

        # Connect to the tool
        hk = Jtagice3HousekeepingProtocol(self.transport)
        hk.start_session()

        self.logger.info("Connecting to nEDBG...")
        major = hk.get_byte(hk.HOUSEKEEPING_CONTEXT_CONFIG, hk.HOUSEKEEPING_CONFIG_FWREV_MAJ)
        minor = hk.get_byte(hk.HOUSEKEEPING_CONTEXT_CONFIG, hk.HOUSEKEEPING_CONFIG_FWREV_MIN)
        build = hk.get_le16(hk.HOUSEKEEPING_CONTEXT_CONFIG, hk.HOUSEKEEPING_CONFIG_BUILD)
        db = hk.get_byte(hk.HOUSEKEEPING_CONTEXT_CONFIG, hk.HOUSEKEEPING_CONFIG_DEBUG_BUILD)
        self.logger.info(
            "> nEDBG version: {0:d}.{1:d}.{2:d} ({3:s})".format(major, minor, build, "debug" if db == 1 else "release"))

        voltage = hk.get_le16(hk.HOUSEKEEPING_CONTEXT_ANALOG, hk.HOUSEKEEPING_ANALOG_VTREF)
        self.logger.info("> Operating voltage: {0:0.2f}V".format(voltage / 1000.0))

