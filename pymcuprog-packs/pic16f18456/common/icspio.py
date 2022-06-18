"""
    icspio.py
    Interacts with the ICSP bit-banger kernel driver

    Commands are sent using the IOCTL_ICSP_CMD command

    Data is piped in a file to and from the driver
"""
import fcntl
import struct
import logging

"""
Linux ioctl numbers made easy

size can be an integer or format string compatible with struct module

for example include/linux/watchdog.h:

#define WATCHDOG_IOCTL_BASE     'W'

struct watchdog_info {
        __u32 options;          /* Options the card/driver supports */
        __u32 firmware_version; /* Firmware version of the card */
        __u8  identity[32];     /* Identity of the board */
};

#define WDIOC_GETSUPPORT  _IOR(WATCHDOG_IOCTL_BASE, 0, struct watchdog_info)

becomes:

WDIOC_GETSUPPORT = _IOR(ord('W'), 0, "=II32s")
"""

# pylint: disable=invalid-name

# constant for linux portability
_IOC_NRBITS = 8
_IOC_TYPEBITS = 8

# architecture specific
_IOC_SIZEBITS = 14
_IOC_DIRBITS = 2

_IOC_NRMASK = (1 << _IOC_NRBITS) - 1
_IOC_TYPEMASK = (1 << _IOC_TYPEBITS) - 1
_IOC_SIZEMASK = (1 << _IOC_SIZEBITS) - 1
_IOC_DIRMASK = (1 << _IOC_DIRBITS) - 1

_IOC_NRSHIFT = 0
_IOC_TYPESHIFT = _IOC_NRSHIFT + _IOC_NRBITS
_IOC_SIZESHIFT = _IOC_TYPESHIFT + _IOC_TYPEBITS
_IOC_DIRSHIFT = _IOC_SIZESHIFT + _IOC_SIZEBITS

_IOC_NONE = 0
_IOC_WRITE = 1
_IOC_READ = 2


def _IOC(direction, io_type, nr, size):
    if isinstance(size, str):  # or isinstance(size, unicode):
        size = struct.calcsize(size)
    return direction << _IOC_DIRSHIFT | \
           io_type << _IOC_TYPESHIFT | \
           nr << _IOC_NRSHIFT | \
           size << _IOC_SIZESHIFT


def _IO(io_type, nr):
    return _IOC(_IOC_NONE, io_type, nr, 0)


def _IOR(io_type, nr, size):
    return _IOC(_IOC_READ, io_type, nr, size)


def _IOW(io_type, nr, size):
    return _IOC(_IOC_WRITE, io_type, nr, size)


def _IOWR(io_type, nr, size):
    return _IOC(_IOC_READ | _IOC_WRITE, io_type, nr, size)


IOCTL_ICSP_CMD = _IOWR(ord('i'), 0, "=s64s")


class IcspIo():
    """
    Wrapper for ICSP kernel driver interaction
    """
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        icsp_driver_file = "/dev/icsp"
        self.logger.debug("Opening file '%s' for data transfer to ICSP driver", icsp_driver_file)
        self.icsp_dev = open(icsp_driver_file, "r+b")

    def execute(self, buffer):
        """
        Executes a sequence of primitives
        """
        self.logger.debug("Sending primitive array to ICSP driver")
        fcntl.ioctl(self.icsp_dev, IOCTL_ICSP_CMD, bytearray(buffer))

    def set_data_buffer(self, buffer_id, values):
        """
        Sends data to the ICSP driver
        """
        # pylint: disable=unused-argument
        self.logger.debug("Sending %d data bytes to ICSP driver", len(values))
        self.icsp_dev.write(values)
        # Flush after write to be sure that values are available without closing the file
        # TODO: evaluate whether its better to disable file bufferring at the open() call instead of flushing here
        self.icsp_dev.flush()

    def get_data_buffer(self, buffer_id, numbytes):
        """
        Receives data from the ICSP driver
        """
        # pylint: disable=unused-argument
        self.logger.debug("Receiving %d data bytes from ICSP driver", numbytes)
        result = self.icsp_dev.read(numbytes)
        return bytearray(result)

    def __del__(self):
        if not self.icsp_dev is None:
            self.logger.debug("Closing ICSP data channel")
            self.icsp_dev.close()
