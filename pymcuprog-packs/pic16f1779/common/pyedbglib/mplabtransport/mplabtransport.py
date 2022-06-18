"""mplabtransport replaces the hidtransport layer when running pyedbglib stack inside MPLAB."""
import logging


class MpLabTransport(object):
    """
    MpLabTransport supports the same API as HidTransport:
        - hid_transfer for send and receive
        - get_report_size for determining the HID report size in use
    """
    def __init__(self, tool):
        self.logger = logging.getLogger(__name__).addHandler(logging.NullHandler())
        self.mplabcomm = tool
        self.packet_size = tool.GetPacketSize()

    def get_report_size(self):
        """
        Report size as reported through the HID interface.

        Usually 64b, but can be 512b
        """
        return self.mplabcomm.GetPacketSize()

    def hid_write(self, packet):
        """Sends a packet to HID and does not wait for a response"""
        # pylint: disable=unused-argument, no-self-use
        raise Exception("Blind write not supported")

    def hid_read(self):
        """Waits for and receives a packet over HID"""
        # pylint: disable=no-self-use
        raise Exception("Blind read not supported")

    def hid_transfer(self, packet):
        """Sends a packet and receives a response."""
        # Send
        self.mplabcomm.Send(packet, len(packet))
        # Blank response
        response = bytearray(self.packet_size)
        # Receive response
        self.mplabcomm.Receive(response, len(response))
        # Convert and return
        return response
