"""
Wrapper for invoking GEN4-scripts on 5G FW platform
"""
import logging
from pyedbglib.util import binary

def pic24_compact(data):
    """
    Compacts an 8-byte raw data block into a 6-byte PIC24 compact frame
    :param data: raw data
    :return: compact data
    """
    while len(data) % 8:
        data.append(0)

    output = []
    for i in range(0, len(data), 8):
        output.append(data[i])
        output.append(data[i + 1])
        output.append(data[i + 2])
        # no i+3
        output.append(data[i + 6])
        output.append(data[i + 4])
        output.append(data[i + 5])
        # no i+7
    return output


def pic24_decompact(data):
    """
    Decompacts (expands) a 6-byte PIC24 frame into a raw 8-byte block
    :param data: compact data
    :return: raw data
    """
    while len(data) % 6:
        data.append(0)
    output = []
    for i in range(0, len(data), 6):
        output.append(data[i])
        output.append(data[i + 1])
        output.append(data[i + 2])
        output.append(0)
        output.append(data[i + 4])
        output.append(data[i + 5])
        output.append(data[i + 3])
        output.append(0)
    return output

def pic24_pack_params(params):
    """
    Takes a list of parameters and returns a byte array of raw byte values ready to be sent to the tool
    """
    packed_params = []
    for param in params:
        packed_params.append(binary.pack_le32(param))
    return packed_params


class Gen4ScriptWrapper(object):
    """
    Proxy object which accumulates primitives and then executes them
    """

    def __init__(self, model_object, controller):
        self.logger = logging.getLogger(__name__)
        self.logger.debug("Using GEN4 proxy")
        self.model_object = model_object
        self.controller = controller

    def _make_command(self, content, params):
        cmd = self.controller.new_command(content)
        for param in params:
            cmd.add_parameter(param)
        return cmd

    def invoke(self, method, **kwargs):
        """
        Invokes a given method with arguments - no data
        """
        parameters, script_content, options = method(self.model_object, **kwargs)
        cmd = self._make_command(script_content, parameters)

        # Generate a bytestream and pass is to the controller for remote execution
        return self.controller.execute(cmd.generate_bytestream())

    def invoke_read(self, bytes_to_read, method, **kwargs):
        """
        Invokes a given method with arguments - data is read back
        """
        # Use a trivial data buffer
        data_buffer_id = 1

        parameters, script_content, options = method(self.model_object, **kwargs)
        cmd = self._make_command(script_content, parameters)

        # Assign the data buffer
        cmd.set_data_dest(data_buffer_id)
        # Generate a bytestream and pass is to the controller for remote execution
        self.controller.execute(cmd.generate_bytestream())

        if 'packed_data_count' in options:
            # Read back and return the data buffer after remote execution
            data = self.controller.read_data_buffer(data_buffer_id, options['packed_data_count'])

            self.logger.debug("Unpacking %d bytes into %d bytes", options['packed_data_count'], bytes_to_read)
            data = pic24_decompact(data)
        else:
            # Read back and return the data buffer after remote execution
            data = self.controller.read_data_buffer(data_buffer_id, bytes_to_read)

        return data

    def invoke_write(self, data_to_write, method, **kwargs):
        """
        Invokes a given method with arguments - data is written
        """
        parameters, script_content, options = method(self.model_object, **kwargs)
        cmd = self._make_command(script_content, parameters)

        # Use a trivial data buffer
        data_buffer_id = 1

        # Assign the data buffer
        cmd.set_data_source(data_buffer_id)
        # Pack?
        if 'packed_data_count' in options:
            self.logger.debug("Packing %d bytes into %d bytes", len(data_to_write), options['packed_data_count'])
            data_to_write = pic24_compact(data_to_write)
        # Send the data to the selected buffer
        self.controller.write_data_buffer(data_buffer_id, data_to_write)
        # Generate a bytestream and pass is to the controller for remote execution
        return self.controller.execute(cmd.generate_bytestream())

    def trigger_write(self, data_buffer_id, method, **kwargs):
        """
        Triggers a remote write. Does not wait for response. Useful for overlapping access.
        """
        parameters, script_content, options = method(self.model_object, **kwargs)
        cmd = self._make_command(script_content, parameters)

        # Assign the data buffer
        cmd.set_data_source(data_buffer_id)
        # Generate a bytestream and trigger remote execution
        self.controller.start_script_execution([cmd.generate_bytestream()])
        # TODO - check result

    def wait_write_done(self):
        """
        Blocks for a write response. Useful for overlapping access.
        """
        return self.controller.receive_script_execution_response()
