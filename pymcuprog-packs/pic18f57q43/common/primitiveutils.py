"""
    primitiveutils
    A collection of utility functions used for executing primitives on the debugger
"""
import logging

try:
    # Python 2.x needs izip, imported as zip
    # pylint: disable=redefined-builtin, no-name-in-module
    from itertools import izip as zip
except ImportError:
    # Python 3.x has zip already, which does the same
    pass

# pyedbglib dependencies
from pyedbglib.primitive import primitives

class PrimitiveException(Exception):
    """
    Custom Exception for primitive sequencer
    """
    def __init__ (self, msg=None, code=0):
        super(PrimitiveException, self).__init__(msg)
        self.code = code

LOGGER = logging.getLogger(__name__)


# Primitve sequences are generated by running a programming algorithm with output directed to a primitive accumulator.
# The primtive sequences have unrolled loops.
# Primitive sequences are nested python lists of lists or byte-code or objects


class ParametricToken(object):
    """
    A token injected in a primitive sequence for later extraction
    """

    # Token types
    TOKEN_ADDRESS_LE32 = 1

    # pylint: disable=too-few-public-methods
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.debug("Creating token")
        self.offset = None


class ParametricValueToken(ParametricToken):
    """
    This token represents a VALUE parameter
    """
    # pylint: disable=too-few-public-methods
    def __init__(self, tokentype):
        ParametricToken.__init__(self)
        self.logger = logging.getLogger(__name__)
        self.logger.debug("Creating value token")
        # Token type is provided on creation
        self.type = tokentype
        # Byte-count is determined on use
        self.bytecount = 0
        # Transform is [determined on use]
        self.transform = 0

    def __floordiv__(self, other):
        """
        Divide this parameter by two on the way in
        :param other: not used
        :return: ifself
        """
        self.logger.info("Dividing by %d", other)
        if other == 2:
            self.transform = 1
        else:
            raise Exception("Unsupported parameteric transform|")
        return self

    def __add__(self, other):
        """
        Parameteric increment - cannot be applied
        :param other: addend
        :return: 0
        """
        self.logger.warning("Unsupported parameteric token operation: '+ %d'", other)
        return 0

    def __int__(self):
        """
        int() operator override to allow logging to print tokens
        :return: 0
        """
        return 0


# We choose (for now) to NOT parameterise lambdas until we really need to
# class ParametricScalarToken (ParametricToken):
#     """
#     This token represents a SCALAR parameter (loop/lambda)
#     """
#     def __init__ (self, repeatcount, sequencelength):
#         ParametricToken.__init__(self)
#         self.logger = logging.getLogger(__name__)
#         self.logger.debug("Creating lambda token")
#         self.repeatcount = repeatcount
#         self.sequencelength = sequencelength


def process_primitive_sequence(cmd):
    """
    Processes a primitive sequence before sending for remote execution
    - Rolls loops
        - to save space on the transport
        - to execute faster on remote hardware
    - Wrap as a lambda function
    - Flatten and extract tokens (for parameterising)

    :param cmd: sequence to process
    :return: command array and token array
    """
    success = True
    lambda_tokens = None
    # Roll loops recursively for maximum compression
    while success:
        success, cmd, lambda_tokens = roll_loops(cmd)

    cmd = enclose_as_lambda(cmd)
    cmd, tokens = flatten_tree(cmd)
    tokens = tokens + lambda_tokens
    return cmd, tokens

def list_compare(a_list, b_list):
    """
    Verifies that the input "lists" are of the same type and of the same length
    :return: True if they are equaul, False if not
    """
    # pylint: disable=unidiomatic-typecheck
    if type(a_list) != type(b_list):
        return False
    if type(a_list) != list:
        return a_list == b_list
    if len(a_list) != len(b_list):
        return False
    # Is this a list of lists?
    for unzipped_a, unzipped_b in zip(a_list, b_list):
        if not list_compare(unzipped_a, unzipped_b):
            return False
    return True


def roll_loops(content, minimum_sequence_length=1, maximum_sequence_length=None, threshold=4):
    """
    Compacts a primitive sequence by looking for repeated sections and turning them into loops
    :param content: primitive sequence to squash
    :param minimum_sequence_length: minimum length to process
    :param maximum_sequence_length: maximum length to process
    :param threshold: minumum length of a contraction worth doing. Avoids micro-optimising the wrong things
    """
    tokens = []
    # Calculate bounds
    absolute_max_sequence_length = len(content) // 2
    # Use happy default values if not provided
    if maximum_sequence_length is None:
        maximum_sequence_length = absolute_max_sequence_length
    else:
        if maximum_sequence_length > absolute_max_sequence_length:
            maximum_sequence_length = absolute_max_sequence_length

    # Sweep by sequence lengths
    for seqlen in range(minimum_sequence_length, maximum_sequence_length):
        # Sweep from element 0
        for start in range(len(content) - seqlen):
            needle = content[start:start + seqlen]
            repeats = 0
            for substring in range(start + seqlen, len(content) - seqlen + 1, seqlen):
                if not list_compare(content[substring:substring + seqlen], needle):
                    break
                else:
                    repeats += 1
                    # Repeat-count is an 8-bit off-by-one field.
                    if repeats == 255:
                        # Max repeats!
                        break
            if repeats > 0:
                # logger.info("Found substring of %d elements repeated %d times at offset %d", seqlen, repeats, start)
                # Is this contraction worth doing?
                if seqlen * repeats > threshold:
                    prefix = content[:start]
                    suffix = content[start + seqlen * (repeats + 1):]

                    # Add token
                    # We choose (for now) to NOT parameterise lambdas until we really need to
                    # token = ParametricScalarToken(repeats, seqlen)
                    # tokens.append(token)
                    # contraction = [token]

                    # Trust blindly
                    contraction = [primitives.LAMBDA, repeats, seqlen]
                    contraction += content[start:start + seqlen]
                    content = prefix + [contraction] + suffix

                    return True, content, tokens
    return False, content, tokens


def enclose_as_lambda(content):
    """
    Wraps an entire, complete primitive stream into an outer lambda function
    The new outer lambda has repeat count '0' ie: execute once
    :param content: primitive sequence
    :return: outer lambda array
    """
    length = len(content)
    return [primitives.LAMBDA, 0, length] + content


def flatten_tree(source):
    """
    Flattens a nested list into a straight list.  Structure is thus lost, and no further processing can be done
    This is a recursive process
    """
    tokens = []
    result = []
    do_flatten_tree(source, result, tokens)
    return result, tokens


def do_flatten_tree(source, result, tokens):
    """
    Does recursive tree flattening.
    If tokens are encountered, they must be substituted with zeros while keeping track of their absolute positions
    :return: list of results, list of tokens extracted
    """
    if isinstance(source, bytearray):
        raise Exception("Byte-array base not supported!")
    if isinstance(source, list):
        for item in source:
            do_flatten_tree(item, result, tokens)
        return  # result
    # Hope its a number at this point
    if isinstance(source, ParametricValueToken):
        source.offset = len(result)
        LOGGER.info("%d byte Value Token called %s at %d (transform %d)", source.bytecount, source.type, source.offset, source.transform)
        if source.bytecount == 0:
            raise Exception("Zero-lenght token found!")
        tokens.append(source)
        # Substitute zeros
        for _ in range(source.bytecount):
            result.append(0)
    # We choose (for now) to NOT parameterise lambdas until we really need to
    # elif isinstance(source, ParametricScalarToken):
    #     logger.info("Lambda Token!")
    #     result.append(primitives.LAMBDA)
    #     source.offset = len(result)
    #     result.append(source.repeatcount)
    #     result.append(source.sequencelength)
    else:
        result.append(source)




def array_to_hexstring(values):
    """
    Converts an array to a string of ascii hex values
    :param values:
    :return:
    """
    hexstring = ""
    for value in values:
        hexstring += "0x{0:02X}, ".format(value)
    return hexstring


def tokens_to_array(tokens):
    """
    Adds offsets and byte-counts into token list
    """
    LOGGER.info("%d token(s) for encoding", len(tokens))

    # T is for token, Token system zero
    token_prefix = [ord('T'), 0]
    # How many
    token_count = len(tokens)
    if token_count > 1:
        raise Exception("No multi-token support.")
    token_prefix.append(token_count)
    if token_count > 0:
        for token in tokens:
            if isinstance(token, ParametricValueToken):
                LOGGER.info("Substitute token type '%d' of size '%d' bytes at offset '%d' (transform '%d')",
                        token.type,
                        token.bytecount, token.offset, token.transform)

                if token.type == ParametricValueToken.TOKEN_ADDRESS_LE32:
                    token_prefix.append(ParametricValueToken.TOKEN_ADDRESS_LE32)
                    token_prefix.append(token.bytecount)
                    token_prefix.append(token.transform)
                    token_prefix.append(token.offset & 0xFF)
                    token_prefix.append((token.offset >> 8) & 0xFF)
                else:
                    raise Exception("Unsupported token type!")
            else:
                raise Exception("Unsupported token!")

    return token_prefix