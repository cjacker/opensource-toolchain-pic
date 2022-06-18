"""
Centralized logging configuration
"""

import logging
import logging.config
from logging import Handler
import os.path
import json

class MPLABLogHandler(Handler):
    """
    A python logging module handler that passes messages to the MPLAB X log system
    """
    def __init__(self, log_object):
        self.log = log_object
        Handler.__init__(self)

    def emit(self, record):
        log_entry = self.format(record)
        log_level = record.levelno
        # Check the record log level, and route it to the appropriate MPLAB X log call
        if log_level is logging.DEBUG:
            return self.log.debug(log_entry)
        if log_level is logging.INFO:
            return self.log.info(log_entry)
        if log_level is logging.WARNING:
            return self.log.warning(log_entry)
        if log_level is logging.ERROR or log_level is logging.CRITICAL:
            return self.log.error(log_entry)
        # Unknown log level
        return self.log.info(log_entry)


def replace_item(obj, key, replace_value):
    """
    Replaces the dictionary value of key with replace_value in the obj dictionary.
    """
    if key in obj:
        obj[key] = replace_value

    for k, v in obj.items():
        if isinstance(v, dict):
            replace_item(v, key, replace_value)

def setup_logger(log, file_path):
    """
    Initialize the python logging module, and map it to the MPLAB X log system
    """
    # Configuration file name
    configuration_name = 'logging.json'
    # Construct the configuration path
    configuration_path = os.path.abspath("{}/common/{}".format(file_path, configuration_name))

    # Open the logging configuration
    with open(configuration_path) as configuration_file:
        config_dict = json.load(configuration_file)

    # Override the mplab log settings?
    override = config_dict.get('override_mplab_setting', False)

    # When override is False, all logging settings are overwritten with settings from MPLAB X
    #
    # When override is True, all logging settings from MPLAB X are ignored.
    # Output is shown, and logging configuration is applied from logging.json

    if override is False:
        # Get log level from MPLAB, update the level settings accordingly
        # private final Level[] levels = {
        #     Level.ALL, //0
        #     Level.CONFIG, // 1
        #     Level.FINE, //2
        #     Level.FINER, // 3
        #     Level.FINEST, //4
        #     Level.INFO, //5
        #     Level.OFF, //6
        #     Level.SEVERE, //7
        #     Level.WARNING //8
        # };

        mplab_level = log.getLogLevelThreshold()
        # Set a high log level for "OFF"
        level = 100  # 50 is the highest standard log level in the python logging module
        show = True
        if mplab_level <= 4:
            level = "DEBUG"
        elif mplab_level == 5:
            level = "INFO"
        elif mplab_level == 6:
            show = False # Level 6 is "OFF"
        elif mplab_level == 7:
            level = "WARNING"
        elif mplab_level == 8:
            level = "ERROR"

        # Replace the log level setting for all handlers, filters and loggers
        replace_item(config_dict, 'level', level)

        # Display logging output in MPLAB?
        log.setShowOutput(show)
    else:
        log.setShowOutput(True)


    # Inject the mplab log object into the configuration
    config_dict['handlers']['mplabx']['log_object'] = log

    # Apply the logging configuration
    logging.config.dictConfig(config_dict)


if __name__ == '__main__':
    # Code for testing purposes
    class DummyLogger(object):
        """
        A dummy logger class for testing
        """
        def __init__(self):
            pass
        def getLogLevelThreshold(self):
            return 100
        def setShowOutput(self, value):
            pass

    LOG = DummyLogger()
    setup_logger(LOG, os.path.dirname(os.path.abspath(__file__)))
