"""
Primitive Accumulator

Used for executing primitive sequences remotely.
Instead of executing each sequence as it is generated, the sequences are accumulated,
and thereafter sent for remote execution.
"""
# pyedbglib dependencies
from pyedbglib.primitive.primitivecontroller import PrimitiveController
from pyedbglib.util import binary

# primitiveutils
from primitiveutils import process_primitive_sequence
from primitiveutils import PrimitiveException

# Base classes
from primitivebase import PrimitiveFunction
from primitivebase import PrimitiveResourceProvider

# Proxies
from primitiveproxy import PrimitiveAccumulatorProxy
from primitiveproxy import PrimitiveExecuterProxy

# Generators
from primitivegenerator import HardwareInterfacePrimitiveGenerator
from primitivegenerator import BoardInterfacePrimitiveGenerator
from primitivegenerator import DebugInterfacePrimitiveGenerator
from primitivegenerator import ProgramExecInterfacePrimitiveGenerator

# ICSP variants
from proginterfaceprovider import ProgInterfaceIcspC8D24
from proginterfaceprovider import ProgInterfaceIcspC8D24PrimitiveGenerator

from proginterfaceprovider import ProgInterfaceIcspC6D16
from proginterfaceprovider import ProgInterfaceIcspC6D16PrimitiveGenerator

class PrimitiveResourceProviderPrimitiveGenerator(PrimitiveResourceProvider):
    """
    Provides resources for generating primitives
    """

    def __init__(self, target):
        self.target = target

    def programming_interface(self, variant):
        """
        Provide a "prog" object to use in scripts
        """
        if variant == ProgInterfaceIcspC8D24:
            return ProgInterfaceIcspC8D24PrimitiveGenerator(self.target)
        if variant == ProgInterfaceIcspC6D16:
            return ProgInterfaceIcspC6D16PrimitiveGenerator(self.target)
        else:
            raise Exception("Invalid ICSP variant requested: {}.".format(variant))

    def debug_interface(self, family):
        """
        Provide a debug interface
        """
        # pylint: disable=unused-argument
        return DebugInterfacePrimitiveGenerator(self.target)

    def board_interface(self):
        """
        Provide a "board" object to use in scripts
        """
        return BoardInterfacePrimitiveGenerator(self.target)

    def program_exec_interface(self):
        """
        Provide a programming executive object to use in scripts
        """
        return ProgramExecInterfacePrimitiveGenerator(self.target)

    def pin_driver(self):
        """
        Provide a "hw" object to use in scripts
        """
        return HardwareInterfacePrimitiveGenerator(self.target)


class PrimitiveFunctionAccumulator(PrimitiveFunction):
    """
    Primitive driver which accumulates primitives
    """

    # pylint: disable=too-few-public-methods
    def __init__(self, model_object):
        PrimitiveFunction.__init__(self, model_object)
        self.logger.debug("Using accumulator")
        # Create the accumulator proxy itself
        self.accumulator = PrimitiveAccumulatorProxy()
        # Request the provider for resources to initialise the model
        provider = PrimitiveResourceProviderPrimitiveGenerator(self.accumulator)
        # Initialise the model object with the provider
        self.model_object.initialise(provider)

    def invoke(self, method, **kwargs):
        """
        Invokes a function on the model object
        Accumulates the output generated in the form of an array of primitives.
        """
        self.logger.debug("Accumulating %s", method.__name__)
        # Reset the accumulator for each execution
        self.accumulator.reset()
        # Invoke the requested method on the object
        method(self.model_object, **kwargs)
        # Extract the contents of the accumulator
        return self.accumulator.get_content()


class PrimitiveFunctionDirectExecuter(PrimitiveFunction):
    """
        Primitive driver which executes primitives directly when transport layer is full
    """

    # pylint: disable=too-few-public-methods
    def __init__(self, model_object, controller):
        PrimitiveFunction.__init__(self, model_object)
        self.logger.info("Using executer")

        # Create proxy using this controller
        self.executer = PrimitiveExecuterProxy(controller)
        # Create a resource provider for this proxy
        provider = PrimitiveResourceProviderPrimitiveGenerator(self.executer)
        # Initialise the model with the provider
        self.model_object.initialise(provider)

    def invoke(self, method, **kwargs):
        """
        Invokes a given method with arguments - no data
        """
        self.logger.debug("Immediate execute: %s", method.__name__)
        # Execute at once
        result = method(self.model_object, **kwargs)
        # Make sure nothing is in the pipe
        self.executer.finalise()
        return result

    def invoke_read(self, bytes_to_read, method, **kwargs):
        """
        Invokes a given method with arguments - data is read back
        """
        self.executer.clear_accumulated_results()
        # Execute at once
        self.invoke(method, **kwargs)
        # Collect results from each section
        results = self.executer.get_accumulated_results()
        if len(results) != bytes_to_read:
            raise Exception("Size mismatch!")
        return results

    def invoke_write(self, data_to_write, method, **kwargs):
        """
        Invokes a given method with arguments - data is written
        # Note: Direct write cannot handle indirect data. Adjust your script!
        """
        # pylint: disable=unused-argument
        return self.invoke(method, **kwargs)


class PrimitiveFunctionAccumulatorExecuter(PrimitiveFunctionAccumulator):
    """
    Proxy object which accumulates primitives and then executes them
    Inherits from class which just accumulates
    """

    def __init__(self, model_object, controller):
        PrimitiveFunctionAccumulator.__init__(self, model_object)
        self.logger.debug("Using accumulated executer")
        self.controller = controller

    def _generate_sequence(self, method, **kwargs):
        """
        Generate a primitive sequence for the given method and arguments
        """
        self.logger.debug("Accumulated execute: %s", method.__name__)
        # Generate primitive sequence by invoking said method
        content = PrimitiveFunctionAccumulator.invoke(self, method, **kwargs)
        # Process sequence, discarding tokens
        sequence, _ = process_primitive_sequence(content)
        return sequence

    def invoke(self, method, **kwargs):
        """
        Invokes a given method with arguments - no data
        """
        # Generate the sequence
        sequence = self._generate_sequence(method, **kwargs)
        # Create a command structure
        cmd = self.controller.new_command(sequence)
        # Generate a bytestream and pass is to the controller for remote execution
        return self.controller.execute_single_block(cmd.generate_bytestream())

    def invoke_read(self, bytes_to_read, method, **kwargs):
        """
        Invokes a given method with arguments - data is read back
        """
        # Use a trivial data buffer
        data_buffer_id = 1
        # Generate the sequence
        sequence = self._generate_sequence(method, **kwargs)
        # Create a command structure
        cmd = self.controller.new_command(sequence)
        # Assign the data buffer
        cmd.set_data_dest(data_buffer_id)
        # Generate a bytestream and pass is to the controller for remote execution
        status = self.controller.execute_single_block(cmd.generate_bytestream())
        statuscode = binary.unpack_le32(status)
        if statuscode != 0:
            self.logger.debug("invoke_read status: 0x%08X", statuscode)
            raise PrimitiveException("Error executing primitives", code=statuscode)

        # Read back and return the data buffer after remote execution
        return self.controller.read_data_buffer(data_buffer_id, bytes_to_read)

    def invoke_write(self, data_to_write, method, **kwargs):
        """
        Invokes a given method with arguments - data is written
        """
        # Use a trivial data buffer
        data_buffer_id = 1
        # Generate the sequence
        sequence = self._generate_sequence(method, **kwargs)
        # Create a command structure
        cmd = self.controller.new_command(sequence)
        # Assign the data buffer
        cmd.set_data_source(data_buffer_id)
        # Send the data to the selected buffer
        self.controller.write_data_buffer(data_buffer_id, data_to_write)
        # Generate a bytestream and pass is to the controller for remote execution
        return self.controller.execute_single_block(cmd.generate_bytestream())

    def invoke_write_read(self, data_to_write, bytes_to_read, method, **kwargs):
        """
        Invokes a given method with arguments - data is written and read
        """
        # Use trivial data buffers
        write_buffer_id = 0
        read_buffer_id = 1
        # Generate the sequence
        sequence = self._generate_sequence(method, **kwargs)
        # Create a command structure
        cmd = self.controller.new_command(sequence)
        # Assign the data buffers
        cmd.set_data_source(write_buffer_id)
        cmd.set_data_dest(read_buffer_id)
        # Send the data to the selected buffer
        self.controller.write_data_buffer(write_buffer_id, data_to_write)
        # Generate a bytestream and pass is to the controller for remote execution
        self.controller.execute_single_block(cmd.generate_bytestream())
        # Read back and return the data buffer after remote execution
        return self.controller.read_data_buffer(read_buffer_id, bytes_to_read)

    def trigger_write(self, data_buffer_id, method, **kwargs):
        """
        Triggers a remote write. Does not wait for response. Useful for overlapping access.
        """
        # Generate the sequence
        sequence = self._generate_sequence(method, **kwargs)
        # Create a command structure
        cmd = self.controller.new_command(sequence)
        # Assign the data buffer
        cmd.set_data_source(data_buffer_id)
        # Generate a bytestream and trigger remote execution
        self.controller.start_primitive_execution([cmd.generate_bytestream()])
        # TODO - check result

    def wait_write_done(self):
        """
        Blocks for a write response. Useful for overlapping access.
        """
        return self.controller.receive_primitive_execution_response()
