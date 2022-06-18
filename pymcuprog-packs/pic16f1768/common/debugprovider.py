"""
Helper function to instantiate a debugger model instance
"""
import logging
import importlib

class ConfigGeneratorTool:
    """
    Tool class for generating XML output from scripts for making drag-and-drop programming support
    Does not use hardware.
    """
    def __init__(self):
        # Clean contents
        self.contents = {}

    def add_new_entry(self, script_id, xml):
        """
        Add an element
        :param script_id: identifier
        :param xml: element
        :return:
        """
        if not script_id in self.contents:
            self.contents[script_id] = xml

    def get_contents(self):
        """
        Retrieve contents
        :return: contents
        """
        return self.contents

class EmbeddedTool:
    """
    Dummy Tool type for running PIC programming scripts on embedded systems like Raspberry Pi
    """
    pass

class PrinterTool:
    """
    Dummy Tool type for printing PIC programming scripts output only
    """
    pass

def provide_debugger_model(device_name):
    """
    Serves up a debug model instance for a given device name
    :param device_name: device name string
    :return: model instance
    """

    # Dynamically import model based on device name
    import_module_name = "{}pds".format(device_name)
    logging.getLogger(__name__).info("Importing '%s'", import_module_name)

    # Import and create device model
    logging.getLogger(__name__).info("Importing device model object")
    try:
        device_module = importlib.import_module(import_module_name)
    except NameError as e:
        raise Exception("Error building Python debug stack: '{}'".format(e))

    logging.getLogger(__name__).info("Instantiating device model for '%s'", device_name)
    # Find the model
    device_model = getattr(device_module, "DeviceDefinition")
    # Create an object
    try:
        debugger = device_model.DEBUGGER_MODEL(device_name)
    except AttributeError:
        raise Exception(
            "Error building Python debug stack: '{}pds.py as no DEBUGGER_MODEL defined.'".format(device_name))

    # Load the device model into the debugger
    debugger.load_device_object(device_model)

    return debugger
