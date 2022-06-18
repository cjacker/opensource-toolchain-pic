"""
Tool selftest protocol

This protocol is mainly used for production and firmware testing purposes
"""

import logging
import sys
import os

from .jtagice3protocol import Jtagice3Protocol
from ..util import binary

class SelftestProtocol(Jtagice3Protocol):
    """
    Implementation of the tool selftest protocol on the JTAGICE3 protocol family

    Not all tools support all commands
    """

    HANDLER_SELFTEST = 0x81
    VERSION0 = 0x00

    CMD_SELFTEST_TIMEOUT_MS                 = 0x00
    CMD_SELFTEST_TIMER_START                = 0x01
    CMD_SELFTEST_TIMER_EXPIRED              = 0x02

    CMD_SELFTEST_DELAY_S                    = 0x10
    CMD_SELFTEST_DELAY_MS                   = 0x11
    CMD_SELFTEST_DELAY_US                   = 0x12

    CMD_SELFTEST_DGI_PIN_RAW_READ           = 0x20

    CMD_SELFTEST_PLATFORM                   = 0xF0

    RSP_SELFTEST_OK                         = 0x80
    RSP_SELFTEST_LIST                       = 0x81
    RSP_SELFTEST_DATA                       = 0x84
    RSP_SELFTEST_FAILED                     = 0xA0
    RSP_SELFTEST_FAILED_WITH_DATA           = 0xA1

    SELFTEST_FAILED_OK                      = 0x00
    SELFTEST_FAILED_NOT_SUPPORTED           = 0x10
    SELFTEST_FAILED_INVALID_PARAMETER_VALUE = 0x13

    SELFTEST_DGI_PINS = {
        0: 'DGI_SPI_MOSI',
        1: 'DGI_SPI_MISO',
        2: 'DGI_SPI_SCK',
        3: 'DGI_SPI_SS',
        4: 'DGI_USART_TX',
        5: 'DGI_USART_RX',
        6: 'DGI_USART_CLK',
        7: 'DGI_I2C_DATA',
        8: 'DGI_I2C_CLK',
        9: 'CDC_TX',
        10: 'CDC_RX',
        11: 'DGI_GPIO0',
        12: 'DGI_GPIO1',
        13: 'DGI_GPIO2',
        14: 'DGI_GPIO3'
    }

    def __init__(self, transport):
        self.logger = logging.getLogger(__name__)
        super(SelftestProtocol, self).__init__(
            transport, Jtagice3Protocol.HANDLER_SELFTEST)

    def selftest_timeout_ms(self, timeout_ms, counter_value=0):
        """
        Test timer timeout

        This function starts a timer with the given timeout value and returns when the timer has expired.
        Alternatively the timer counter value can be overridden by providing a counter_value value >0

        :param: timeout_ms Timeout value in milliseconds
        :param counter_value: Value to be written to timer counter register before timer is started.
            A value of 0 means skip writing any value. The counter_value can be used to test overflow
            situations
        """
        self.logger.debug("Timeout ms selftest %dms, counter: %d", timeout_ms, counter_value)

        self.check_response(self.jtagice3_command_response(
            bytearray([self.CMD_SELFTEST_TIMEOUT_MS, self.VERSION0])
            + binary.pack_le16(timeout_ms)
            + binary.pack_le16(counter_value)))

    def selftest_timer_start(self, timer_id, timeout_ms):
        """ Start a timer with the given ID and timeout value"""
        self.logger.debug("Start timer %d with %dms timeout", timer_id, timeout_ms)
        self.check_response(self.jtagice3_command_response(
            bytearray([self.CMD_SELFTEST_TIMER_START, self.VERSION0, timer_id])
            + binary.pack_le16(timeout_ms)))

    def selftest_timer_expired(self, timer_id):
        """
        Check if a timer has expired

        :param timer_id: ID of timer to check
        :returns: True if timer has expired, False if not
        """
        self.logger.debug("Check if timer %d has expired", timer_id)
        response = self.check_response(self.jtagice3_command_response(
            bytearray([self.CMD_SELFTEST_TIMER_EXPIRED, self.VERSION0, timer_id])))
        if response[0] == 0x01:
            return True
        else:
            return False

    def selftest_delay_s(self, delay_s):
        """
        Issue a delay of delay_s seconds

        :param delay_s: Delay value in seconds. Max is 2^16 - 1 (65535)
        """
        self.logger.debug("Delay s selftest %ds", delay_s)
        self.check_response(self.jtagice3_command_response(
            bytearray([self.CMD_SELFTEST_DELAY_S, self.VERSION0])
            + binary.pack_le32(delay_s)))

    def selftest_delay_ms(self, delay_ms):
        """
        Issue a delay of delay_ms milliseconds

        :param delay_ms: Delay value in milliseconds. Max is 2^16 - 1 (65535)
        """
        self.logger.debug("Delay ms selftest %dms", delay_ms)
        self.check_response(self.jtagice3_command_response(
            bytearray([self.CMD_SELFTEST_DELAY_MS, self.VERSION0])
            + binary.pack_le32(delay_ms)))

    def selftest_delay_us(self, delay_us):
        """
        Issue a delay of delay_us microseconds

        :param delay_us: Delay value in microseconds. Max is 2^16 - 1 (65535)
        """
        self.logger.debug("Delay us selftest %dus", delay_us)
        self.check_response(self.jtagice3_command_response(
            bytearray([self.CMD_SELFTEST_DELAY_US, self.VERSION0])
            + binary.pack_le32(delay_us)))
