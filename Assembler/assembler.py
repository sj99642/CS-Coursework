"""
The assembler. This file will manage the actual assembly. It is not split up into different files because fundamentally the assembler is not too complex. 
Communication with the GUI is managed via standard output.
"""

import re
from pprint import pprint
import struct
from collections import namedtuple
import json
import sys

# Set to true if the -i flag is used (i.e. the GUI is running)
INTERACTIVE_MODE = False

# The default values for the contents of the meta section
META_CONFIG_DEFAULT = {
    "mem_amt": 4
}

# A dict of opcodes.
OPCODES = {
    "HLT": 0x00,

    "CMP_char": 0x01,
    "CMP_uchar": 0x02,
    "CMP_short": 0x03,
    "CMP_ushort": 0x04,
    "CMP_int": 0x05,
    "CMP_uint": 0x06,
    "CMP_float": 0x07,

    "JMP": 0x08,
    "JE": 0x09,
    "JNE": 0x0A,
    "JLT": 0x0B,
    "JLE": 0x0C,
    "JGT": 0x0D,
    "JGE": 0x0E,

    "MOV_1B": 0x10,
    "MOV_2B": 0x11,
    "MOV_4B": 0x12,

    "LEA": 0x14,

    "ADD_char": 0x20,
    "ADD_uchar": 0x21,
    "ADD_short": 0x22,
    "ADD_ushort": 0x23,
    "ADD_int": 0x24,
    "ADD_uint": 0x25,
    "ADD_float": 0x26,

    "SUB_char": 0x28,
    "SUB_uchar": 0x29,
    "SUB_short": 0x2A,
    "SUB_ushort": 0x2B,
    "SUB_int": 0x2C,
    "SUB_uint": 0x2D,
    "SUB_float": 0x2E,

    "MUL_char": 0x30,
    "MUL_uchar": 0x31,
    "MUL_short": 0x32,
    "MUL_ushort": 0x33,
    "MUL_int": 0x34,
    "MUL_uint": 0x35,
    "MUL_float": 0x36,

    "IDIV_char": 0x38,
    "IDIV_uchar": 0x39,
    "IDIV_short": 0x3A,
    "IDIV_ushort": 0x3B,
    "IDIV_int": 0x3C,
    "IDIV_uint": 0x3D,
    "IDIV_float": 0x3E,

    "MOD_char": 0x40,
    "MOD_uchar": 0x41,
    "MOD_short": 0x42,
    "MOD_ushort": 0x43,
    "MOD_int": 0x44,
    "MOD_uint": 0x45,
    "MOD_float": 0x46,

    "EDIV_char": 0x48,
    "EDIV_uchar": 0x49,
    "EDIV_short": 0x4A,
    "EDIV_ushort": 0x4B,
    "EDIV_int": 0x4C,
    "EDIV_uint": 0x4D,
    "EDIV_float": 0x4E,

    "AND_1B": 0x50,
    "AND_2B": 0x51,
    "AND_4B": 0x52,

    "OR_1B": 0x54,
    "OR_2B": 0x55,
    "OR_4B": 0x56,

    "XOR_1B": 0x58,
    "XOR_2B": 0x59,
    "XOR_4B": 0x5A,

    "NOT_1B": 0x5C,
    "NOT_2B": 0x5D,
    "NOT_4B": 0x5E,

    "LSH_1B": 0x60,
    "LSH_2B": 0x61,
    "LSH_4B": 0x62,

    "RSH_1B": 0x64,
    "RSH_2B": 0x65,
    "RSH_4B": 0x66
}

# The names of opcodes without any extra information. Useful for searching.
OPCODE_NAMES = {
    "HLT",
    "CMP",
    "JMP",
    "JE",
    "JNE",
    "JLT",
    "JLE",
    "JGT",
    "JGE",
    "MOV",
    "LEA",
    "ADD",
    "SUB",
    "MUL",
    "IDIV",
    "MOD",
    "EDIV",
    "AND",
    "OR",
    "XOR",
    "NOT",
    "LSH",
    "RSH"
}

# A mapping between register names and their numbers.
REGISTERS = {
    "eax": 0xA0,
    "ebx": 0xB0,
    "ecx": 0xC0,
    "edx": 0xD0,
    "esi": 0xE1,
    "edi": 0xE2,
    "ebp": 0xE3,
    "esp": 0xE4,

    "ax": 0xA1,
    "bx": 0xB1,
    "cx": 0xC1,
    "dx": 0xD1,

    "ah": 0xA2,
    "bh": 0xB2,
    "ch": 0xC2,
    "dh": 0xD2,

    "al": 0xA3,
    "bl": 0xB3,
    "cl": 0xC3,
    "dl": 0xD3,

    "out": 0xF0,
    "in": 0xF1
}

# Code below is for storing information about the data types.
# I expected other pieces of information too.
DataTypeMetadata = namedtuple("DataTypeMetadata", ["size"])
DTYPE_META = {
    "char": DataTypeMetadata(1),
    "uchar": DataTypeMetadata(1),
    "short": DataTypeMetadata(2),
    "ushort": DataTypeMetadata(2),
    "int": DataTypeMetadata(4),
    "uint": DataTypeMetadata(4),
    "float": DataTypeMetadata(4),
    "1B": DataTypeMetadata(1),
    "2B": DataTypeMetadata(2),
    "4B": DataTypeMetadata(4)
}

# ---------- CLASSES


class Instruction:
    """
    Base class for instructions. 
    """
    def __init__(self, instr_num):
        self.instruction_num = instr_num

    def get_bytes_length(self):
        raise NotImplementedError("Must only use a subclass of Instruction")

    def get_bytes(self, mem_table):
        raise NotImplementedError("Must only use a subclass of Instruction")


class DataInstruction(Instruction):
    """
    A type of instruction from the data section. It sets a variable. In its implementation, it is a MOV command,
    moving an immediate value to a certain memory address
    """

    def __init__(self, instr_num, name, value, dtype):
        super().__init__(instr_num)
        self.name = name
        self.value = value
        self.data_type = dtype

    def __eq__(self, other):
        return (self.name == other.name) \
               and (self.value == other.value) \
               and (self.data_type == other.data_type) \
               and (self.instruction_num == other.instruction_num)

    def __repr__(self):
        return "DataInstruction({0.instruction_num}, {0.name}, {0.value}, {0.data_type})".format(self)

    def _calculate_valsize(self):
        """Calculate the number of bytes in the value"""
        if self.data_type == "float":
            valsize = 4
        else:
            # An integer type; calculate its size
            if abs(int(self.value)) < 256:
                valsize = 1
            elif abs(int(self.value)) < 65536:
                valsize = 2
            else:
                valsize = 4

        return valsize

    def get_bytes_length(self):
        # (Command (MOV) + Opcode data + Memory address = 6) + size of value
        return 6 + self._calculate_valsize()

    def get_bytes(self, mem_table):
        # The instruction byte
        if self.data_type in ("char", "uchar"):
            instr = struct.pack(">B", OPCODES["MOV_1B"])
        elif self.data_type in ("short", "ushort"):
            instr = struct.pack(">B", OPCODES["MOV_2B"])
        elif self.data_type in ("int", "uint", "float"):
            instr = struct.pack(">B", OPCODES["MOV_4B"])
        else:
            raise ValueError("Cannot find size of type {}".format(self.data_type))

        valsize = self._calculate_valsize()
        # The byte to describe the operands and the format string for how to turn the immediate value into binary
        if valsize == 1:
            operand_num = b"R" # 0x52
            val_fmt_str = ">B"
        elif valsize == 2:
            operand_num = b"S" # 0x53
            val_fmt_str = ">H"
        elif valsize == 4:
            operand_num = b"T" # 0x54
            val_fmt_str = ">I"
        else:
            raise ValueError("Illegal value size: {}".format(valsize))

        # The memory address
        mem_addr = struct.pack(">I", mem_table[self.name])

        # The initial value
        if self.data_type == "float":
            value_bytes = struct.pack(">F", float(self.value))
        else:
            value_bytes = struct.pack(val_fmt_str, int(self.value))

        # Put them all together and return
        return instr + operand_num + mem_addr + value_bytes

    def get_op1_bytes(self, mem_table):
        """Get the bytes of the first operand."""
        return struct.pack(">I", mem_table[self.name])

    def get_op2_bytes(self, mem_table):
        """Get the bytes of the second operand."""
        valsize = self._calculate_valsize()
        # The byte to describe the operands and the format string for how to turn the immediate value into binary
        if valsize == 1:
            val_fmt_str = ">B"
        elif valsize == 2:
            val_fmt_str = ">H"
        elif valsize == 4:
            val_fmt_str = ">I"
        else:
            raise ValueError("Illegal value size: {}".format(valsize))

        if self.data_type == "float":
            return struct.pack(">F", float(self.value))
        else:
            return struct.pack(val_fmt_str, int(self.value))



class TextInstruction(Instruction):
    """
    Represents a standard instruction in the assembly code. Has to store the mnemonic, a label (optionally),
    the data type and the operands.
    """
    def __init__(self, instr_num, opcode: str, dtype: str, op1, op2, label=""):
        super().__init__(instr_num)
        self.opcode_mnemonic = opcode
        self.data_type = dtype
        self.operand1 = op1
        self.operand2 = op2
        self.label = label

        if not dtype:
            # None was specified, so try to work it out based on the operands
            op1_size = op1.get_required_length() if op1 is not None else 0
            op2_size = op2.get_required_length() if op2 is not None else 0

            max_op_size = max(op1_size, op2_size)

            if max_op_size == 1:
                self.data_type = "char"
            elif max_op_size == 2:
                self.data_type = "short"
            elif max_op_size == 4:
                self.data_type = "int"

    def __eq__(self, other):
        return self.instruction_num == other.instruction_num \
                and self.opcode_mnemonic == other.opcode_mnemonic \
                and self.data_type == other.data_type \
                and self.operand1 == other.operand1 \
                and self.operand2 == other.operand2 \
                and self.label == other.label

    def __repr__(self):
        return "TextInstruction({0.instruction_num}, {0.opcode_mnemonic}, {0.data_type}, {op1}, {op2}, {0.label})".format(self,
                op1=str(self.operand1),
                op2=str(self.operand2))


    def get_bytes_length(self):
        # (Opcode byte + operand byte = 2) + operand 1 + operand 2
        length = 2
        if self.operand1 is not None:
            length += self.operand1.get_required_length()

        if self.operand2 is not None:
            length += self.operand2.get_required_length()

        return length

    def get_bytes(self, mem_table):
        # First find the opcode byte

        # Check the opcode is valid
        if self.opcode_mnemonic not in OPCODE_NAMES:
            raise ValueError("Unsupported opcode mnemonic: {}".format(self.opcode_mnemonic))

        # Is this the type of opcode that has no subtypes?
        if self.opcode_mnemonic in OPCODES.keys():
            opcode_num = OPCODES[self.opcode_mnemonic]

        # Is it based on a data type?
        elif (self.opcode_mnemonic + "_" + self.data_type) in OPCODES.keys():
            opcode_num = OPCODES[self.opcode_mnemonic + "_" + self.data_type]

        # If neither of those, then it might be size based
        elif (self.data_type in ("char", "uchar")) and (self.opcode_mnemonic + "_1B" in OPCODES.keys()):
            opcode_num = OPCODES[self.opcode_mnemonic + "_1B"]
        elif (self.data_type in ("short", "ushort")) and (self.opcode_mnemonic + "_2B" in OPCODES.keys()):
            opcode_num = OPCODES[self.opcode_mnemonic + "_2B"]
        elif (self.data_type in ("int", "uint", "float")) and (self.opcode_mnemonic + "_4B" in OPCODES.keys()):
            opcode_num = OPCODES[self.opcode_mnemonic + "_4B"]

        else:
            raise ValueError("Mismatch between opcode {} and data type {}".format(self.opcode_mnemonic, self.data_type))

        # Turn the opcode number into an opcode byte
        opcode_byte = struct.pack(">B", opcode_num)

        # Next, find the operand byte
        operand_num = self.operand1.get_bit_designation() if self.operand1 is not None else 0
        operand_num = operand_num << 4    # Shift the bits to the left to make space for the second
        operand_num += self.operand2.get_bit_designation() if self.operand2 is not None else 0
        operand_byte = struct.pack(">B", operand_num)

        # Get the operand bytes
        op1_bytes = self.operand1.get_bytes() if self.operand1 is not None else b""
        op2_bytes = self.operand2.get_bytes() if self.operand2 is not None else b""

        # Add them together
        instr_bytes = opcode_byte + operand_byte + op1_bytes + op2_bytes

        assert len(instr_bytes) == self.get_bytes_length()

        return instr_bytes

    def get_op1_bytes(self, mem_table):
        return self.operand1.get_bytes() if self.operand1 is not None else b""

    def get_op2_bytes(self, mem_table):
        return self.operand2.get_bytes() if self.operand2 is not None else b""




class Operand:
    """
    Superclass for all operands. They use the features here to standardise
    things that all operands have. 
    """
    def __init__(self):
        self._bit_designation = -1
        self._required_length = -1

    def get_bit_designation(self):
        return self._bit_designation

    def get_required_length(self):
        return self._required_length

    def get_bytes(self):
        raise NotImplementedError("Must use a subclass of Operand")


class RegisterOperand(Operand):
    """
    Refers to a register. Stores its name, bit designation and length needed, and works out its numerical version.
    """
    def __init__(self, regname: str):
        super().__init__()
        self.name = regname.lower()
        self.numerical = REGISTERS[regname.lower()]

        self._bit_designation = 1
        self._required_length = 1

    def __eq__(self, other):
        return isinstance(other, RegisterOperand) \
                and self.name == other.name \
                and self.numerical == other.numerical \
                and self._bit_designation == other._bit_designation \
                and self._required_length == other._required_length

    def __repr__(self):
        return "RegisterOperand({0.name})".format(self)

    def __str__(self):
        return "\"{0.name}\"".format(self)

    def get_bytes(self):
        # Basically turn the numerical register number into a byte
        return struct.pack(">B", self.numerical)


class ImmediateOperand(Operand):
    """
    Represents an immediate value, like "5". Has to work out the size and type.
    """
    def __init__(self, value: str):
        super().__init__()
        try:
            self.value = int(value)
        except ValueError:
            self.value = float(value)

        if isinstance(self.value, float) or self.value < -32768 or self.value > 65536:
            self.size = 4
            self._bit_designation = 4
        elif self.value < -128 or self.value > 255:
            self.size = 2
            self._bit_designation = 3
        else:
            self.size = 1
            self._bit_designation = 2

        self._required_length = self.size

    def __eq__(self, other):
        return isinstance(other, ImmediateOperand) \
                and self.value == other.value \
                and self.size == other.size \
                and self._required_length == other._required_length

    def __repr__(self):
        return "ImmediateOperand({0.value})".format(self)

    def __str__(self):
        return str(self.value)

    def _get_value_format_string(self):
        # Find the formatting string to use to turn it into bytes
        if isinstance(self.value, float):
            return ">f"
        elif self.value < -32768:
            return ">i"
        elif self.value < -128:
            return ">h"
        elif self.value < 0:
            return ">b"
        elif self.value < 256:
            return ">B"
        elif self.value < 65536:
            return ">H"
        else:
            return ">I"

    def get_bytes(self):
        return struct.pack(self._get_value_format_string(), self.value)

class AddressOperand(Operand):
    """
    An address. To start with, self.addr will be a string, but eventually it will be replaced with a memory address.
    """
    def __init__(self, address: (str, int)):
        super().__init__()
        self.addr = address
        self._bit_designation = 5
        self._required_length = 4

    def __eq__(self, other):
        return isinstance(other, AddressOperand) \
                and self.addr == other.addr \
                and self._bit_designation == other._bit_designation \
                and self._required_length == other._required_length

    def __repr__(self):
        return "AddressOperand({0.addr})".format(self)

    def get_bytes(self):
        return struct.pack(">I", self.addr)


class ArithmeticOperand(Operand):
    """
    One of the following types of arithmetic operands. 
    """
    type_6 = r"^(?P<a>[a-zA-Z0-9]+)$"    # a
    type_7 = r"^(?P<a>[a-zA-Z0-9]+)\*(?P<b>[a-zA-Z0-9]+)$"    # a*b
    type_8 = r"^(?P<a>[a-zA-Z0-9]+)\+(?P<b>[a-zA-Z0-9]+)$"    # a+b
    type_9 = r"^(?P<a>[a-zA-Z0-9]+)\*(?P<b>[a-zA-Z0-9]+)\+(?P<c>[a-zA-Z0-9]+)$"     # a*b+c
    type_10 = r"^(?P<a>[a-zA-Z0-9]+)\+(?P<b>[a-zA-Z0-9]+)\*(?P<c>[a-zA-Z0-9]+)$"    # a+b*c

    def __init__(self, asm_str: str):
        super().__init__()
        self.asm_str = asm_str

        if not asm_str.strip():
            raise ValueError("Cannot process empty operand")

        # See which type of operand this is and set everything accordingly
        if re.search(self.type_10, asm_str) is not None:
            m = re.match(self.type_10, asm_str)
            self._bit_designation = 10
            self._required_length = 3
            self.a = m.group("a")
            self.b = m.group("b")
            self.c = m.group("c")
        elif re.search(self.type_9, asm_str) is not None:
            m = re.match(self.type_9, asm_str)
            self._bit_designation = 9
            self._required_length = 3
            self.a = m.group("a")
            self.b = m.group("b")
            self.c = m.group("c")
        elif re.search(self.type_8, asm_str) is not None:
            m = re.match(self.type_8, asm_str)
            self._bit_designation = 8
            self._required_length = 2
            self.a = m.group("a")
            self.b = m.group("b")
            self.c = None
        elif re.search(self.type_7, asm_str) is not None:
            m = re.match(self.type_7, asm_str)
            self._bit_designation = 7
            self._required_length = 2
            self.a = m.group("a")
            self.b = m.group("b")
            self.c = None
        elif re.search(self.type_6, asm_str) is not None:
            m = re.match(self.type_6, asm_str)
            self._bit_designation = 6
            self._required_length = 1
            self.a = m.group("a")
            self.b = None
            self.c = None
        else:
            raise AssemblyError(-1, "Incorrect format for arithmetic operand: {}".format(asm_str))

    def __eq__(self, other):
        return isinstance(other, ArithmeticOperand) \
                and self.a == other.a \
                and self.b == other.b \
                and self.c == other.c \
                and self.asm_str == other.asm_str

    def __repr__(self):
        return "ArithmeticOperand({0.asm_str})".format(self)

    def __str__(self):
        return self.asm_str

    def _interpret_value(self, value) -> int:
        # The values in arithmetic expressions can be immediate or a register name. Either way it has to be encoded.
        if isinstance(value, str):
            # A register
            try:
                return REGISTERS[value]
            except KeyError:
                pass    # It's probably just an immediate value

        # It is just an immediate value
        numval = int(value)
        if numval in (1, 2, 4, 8):
            return numval
        else:
            raise ValueError("Only 2, 4 and 8 are permitted for multiplication in arithmetic operands")

    def get_bytes(self):
        bytes_ = b""
        for val in (self.a, self.b, self.c):
            if val is not None:
                bytes_ += struct.pack(">B", self._interpret_value(val))

        assert len(bytes_) == self._required_length, "Required length and calculated byte length do not match"
        return bytes_



class AssemblyError(Exception):
    """
    Raised when an error has happened, to inform the user of it in a standard way.
    """
    def __init__(self, line_no, description):
        super().__init__("Error on line {}: {}".format(line_no, description))
        self.line_no = line_no
        self.description = description


# ---------- FUNCTIONS




def normalise_text(text: str) -> str:
    """
    Removes comments, unnecessary whitespace and empty lines
    :param text:
    :return:
    """
    # 1.1. Split text into lines

    lines = text.split("\n")

    for i, line in enumerate(lines):
        # 1.2. For each line, if there is a semicolon, remove everything after the first semicolon
        lines[i] = lines[i].split(";")[0]

        # 1.3. Strip all whitespace from the start and end of every line
        lines[i] = lines[i].strip()

    if INTERACTIVE_MODE: print("remove_comments", json.dumps(["\n".join(lines)]))

    # 1.4. Remove empty lines
    lines = [line for line in lines if line != ""]
    if INTERACTIVE_MODE: print("remove_empty_lines", json.dumps(["\n".join(lines)]))

    # 1.5. Remove duplicate whitespace
    multiple_whitespace = re.compile(r"\s+")
    for i, line in enumerate(lines):
        lines[i] = multiple_whitespace.sub(" ", line)
    if INTERACTIVE_MODE: print("remove_dup_wspace", json.dumps(["\n".join(lines)]))

    # 1.6. Put the lines back together
    normalised_text = "\n".join(line.strip() for line in lines)

    return normalised_text


def split_into_sections(text: str) -> str:
    """
    Takes the normalised text and splits it into its individual sections
    :param text:
    :return:
    """
    # Don't bother with regular expressions for this
    # Just split where "section." occurs
    parts = text.split("section.")
    parts_with_titles = [part.split("\n", maxsplit=1) for part in parts]

    # Fill out the dictionary of sections
    sections_dict = {}
    for title, *other in parts_with_titles:
        # The thing left on the first line is the name of the section
        if title.strip() == "" and len(other) == 0:
            continue

        sections_dict[title] = (other[0] if len(other) > 0 else "").strip()

    # All sections have to be present, so check that
    for section in ("meta", "data", "text"):
        if section not in sections_dict.keys():
            raise AssemblyError(-1, "No {} section".format(section))

    return sections_dict


def divide_and_contextualise(section_dict: dict) -> (dict, str):
    """
    Divides the sections up into lines. Interprets the meta section to create a config dict, and then creates a list
    of Instruction objects based on the data and text sections. Returns both as a tuple
    :param section_dict:
    :return:
    """

    if INTERACTIVE_MODE: print("start_proc_meta")

    # 4.1. Split the meta section into lines and interpret them
    # Create the dict based on META_CONFIG_DEFAULT
    config_dict = META_CONFIG_DEFAULT.copy()

    # Split meta section into lines
    meta_lines = [x.strip() for x in section_dict["meta"].split("\n") if x.strip()]

    # Go through the lines and split on an = sign, then act on that
    for line in meta_lines:
        if INTERACTIVE_MODE: print("read_meta_line", json.dumps([line]))
        item, value = line.split("=")
        if INTERACTIVE_MODE: print("ustd_meta_line", json.dumps(["Config item {item} has value {value}".format(item=item, value=value),
            item, value]))
        config_dict.update(**{item: value})

    # Config dict done, moving on to the big part: instructions
    instruction_list = []

    if INTERACTIVE_MODE: print("start_proc_data")

    # Start with the data section, adding each one as a DataInstruction instance
    data_lines = [x.strip() for x in section_dict["data"].split("\n") if x.strip()]
    for line in data_lines:
        if INTERACTIVE_MODE: print("read_data_line", json.dumps([line]))
        # Takes the form name VAR type initial
        name, type_and_initial = [x.strip() for x in line.split("VAR") if x.strip()]
        dtype, initial = type_and_initial.split()
        if INTERACTIVE_MODE: print("ustd_data_line", json.dumps([
            "Variable '{name}' has type '{type}' and initial value '{initial}'".format(name=name, type=dtype,
                                                                                       initial=initial),
                                                                                       name, dtype, initial]))

        instruction_list.append(DataInstruction(len(instruction_list), name, initial, dtype))

    if INTERACTIVE_MODE: print("start_proc_text")

    # Next move onto the text section
    text_lines = [x.strip() for x in section_dict["text"].split("\n") if x.strip()]
    for line in text_lines:
        if INTERACTIVE_MODE: print("read_text_line", json.dumps([line]))

        # Split into basic tokens
        parts = line.split()

        # See if the first part is in the list of opcodes. If not then it is likely a label
        label = ""
        if not parts[0].upper() in OPCODE_NAMES:
            # The first must be a label; check that the second is the opcode
            label = parts[0]
            del parts[0]    # Remove the label from the list

        # Now we can assume parts[0] is the opcode
        # Next is the type. parts[1] could be a data type or it could not be
        dtype = 0
        if len(parts) > 1:
            if parts[1].lower() in ("char", "uchar", "short", "ushort", "int", "uint", "float"):
                dtype = parts[1].lower()
                del parts[1]
            elif parts[1].upper() == "1B":
                dtype = "char"
                del parts[1]
            elif parts[1].upper() == "2B":
                dtype = "short"
                del parts[1]
            elif parts[1].upper() == "4B":
                dtype = "int"
                del parts[1]
            else:
                dtype = "char"

        # If not then assume the data type is unspecified
        mnemonic = parts[0]
        del parts[0]

        # The list of parts should now just consist of the operands, separated by a space
        if len(parts) == 0:
            # No operands
            operand1 = None
            operand2 = None
        elif len(parts) == 1:
            operand1 = interpret_operand(parts[0])
            operand2 = None
        elif len(parts) == 2:
            operand1 = interpret_operand(parts[0])
            operand2 = interpret_operand(parts[1])
        else:
            raise Exception("Invalid length of {}".format(len(parts)))

        # We now have both operands; that's everything
        instruction_list.append(TextInstruction(instr_num=len(instruction_list),
                                                opcode=mnemonic,
                                                dtype=dtype,
                                                label=label,
                                                op1=operand1,
                                                op2=operand2))

        if INTERACTIVE_MODE:
            print("ustd_text_line",
                  json.dumps(["Instruction {num}. Opcode={opcode}, type={type}, label={label}, op1={op1}, op2={op2}".format(
                num=len(instruction_list) - 1,
                opcode=mnemonic,
                type=dtype,
                label=label,
                op1=operand1,
                op2=operand2
            ),
            label, mnemonic, dtype, str(operand1), str(operand2)]))
        
    return config_dict, instruction_list



def interpret_operand(string: str) -> Operand:
    """
    Takes a single operand and turns it into the correct type of object.
    """
    # The operand can be one of four things:
    # * register (the name of a register)
    # * immediate (a number)
    # * address (a string other than a register name)
    # * arithmetic (an expression inside square brackets)

    string = string.strip() # Just to make sure

    if not string:
        raise ValueError("Cannot interpret an empty operand")

    # Is it a register name?
    if string.lower() in REGISTERS.keys():
        # Yes it is
        return RegisterOperand(string)

    # Is it an immediate value?
    try:
        val = int(string)
        return ImmediateOperand(val)
    except ValueError:
        # it could be an immediate float
        try:
            val = float(string)
            return ImmediateOperand(val)
        except ValueError:
            pass        # Not an immediate value

    # Is it an address label/variable?
    if string.isidentifier():
        return AddressOperand(string)

    # Is it an arithmetic expression?
    if string[0] == "[" and string[-1] == "]":
        return ArithmeticOperand(string[1: -1])

    # If it was none of those then it is invalid
    raise ValueError("Invalid operand: {}".format(string))


def record_labels_and_variables(instruction_list):
    """
    Analyse the instruction list to create a table mapping variable/label names to the 
    memory addresses they refer to.
    """
    # Create the empty tables
    label_table = {}
    var_table = {}
    mem_table = {}

    # Loop through the instructions
    for instruction in instruction_list:
        # If the instruction is a DataInstruction, add it to the variable table with its relative position
        if isinstance(instruction, DataInstruction):
            if INTERACTIVE_MODE: print("found_var [{name}] [{mrel}] [{type}]".format(
                name=instruction.name,
                mrel=calculate_var_table_size(var_table),
                type=instruction.data_type
            ))
            var_table[instruction.name] = (calculate_var_table_size(var_table), instruction.data_type)

        # If the instruction is a TextInstruction and has a label, add it to the label table
        elif isinstance(instruction, TextInstruction):
            if INTERACTIVE_MODE: print("found_label [{lname}] [{instrnum}]".format(
                lname=instruction.label,
                instrnum=instruction.instruction_num
            ))
            if instruction.label != "":
                label_table[instruction.label] = instruction.instruction_num

        # If it was neither of these types, what's it doing here?
        else:
            raise ValueError("Item in instruction list is neither \
            DataInstruction nor TextInstruction: {}".format(instruction))


    # Calculate the total size of the text section
    total_text_section_size = sum(instr.get_bytes_length() for instr in instruction_list)

    # Add all the variables to the memory address table
    for name, (offset, _) in var_table.items():
        mem_table[name] = total_text_section_size + offset

    # Add all the labels to the memory address table
    for name, instr_num in label_table.items():
        mem_table[name] = calculate_instr_start_address(instr_num, instruction_list)

    if INTERACTIVE_MODE: print("mem_offsets", json.dumps(mem_table))

    # That's done, so return it
    return mem_table



def calculate_var_table_size(var_table):
    """Calculate the current total size of the variable table, taking into account the data types of the entries."""
    size = 0
    for (_, (_, dtype)) in var_table.items():
        size += DTYPE_META[dtype].size

    return size

def calculate_instr_start_address(instr_num, instruction_list):
    """Work out where a given instruction number will start."""
    total = 0
    for instr in instruction_list[:instr_num]:
        total += instr.get_bytes_length()
    return total


def encode_metadata(config_dict: dict) -> bytes:
    """Takes the meta dictionary and writes it into bytes."""
    encoded = b""
    for key, value in config_dict.items():
        encoded += key.encode() + b"=" + str(value).encode() + b"&"
    encoded += b"\x00\x00\x00\x00"

    return encoded


def encode_instruction_list(instruction_list: list, memory_table: dict) -> bytes:
    """Turn the full instruction list into bytes."""
    encoded = b""
    for instr in instruction_list:
        b = instr.get_bytes(memory_table)
        if INTERACTIVE_MODE:
            print("conv_instr [{opcode}] [{opbyte}] {op1} {op2}".format(
                opcode=b[0],
                opbyte=b[1],
                op1=list(instr.get_op1_bytes(memory_table)),
                op2=list(instr.get_op2_bytes(memory_table))
            ))
        encoded += b
    return encoded


def place_memory_addresses(mem_table: dict, instruction_list: list):
    """Replace textual references in the instructions with the right memory addresses."""
    for instr in instruction_list:
        if isinstance(instr, DataInstruction):
            continue    # These don't have operands

        if isinstance(instr.operand1, AddressOperand) and isinstance(instr.operand1.addr, str):
            instr.operand1 = AddressOperand(mem_table[instr.operand1.addr])

        if isinstance(instr.operand2, AddressOperand) and isinstance(instr.operand2.addr, str):
            instr.operand2 = AddressOperand(mem_table[instr.operand2.addr])


def print_bytes_as_hex(bytes_: bytes, rowlen: int):
    for i, byte in enumerate(bytes_):
        print(format(byte, ">02X") + " ", end="")
        if (i+1) % rowlen == 0:
            print()


def main(asmfile: str, out_format: str, interactive=False):
    global INTERACTIVE_MODE
    INTERACTIVE_MODE = interactive

    if INTERACTIVE_MODE:
        outfile = open("../GUI/asmout.txt", "w")
        sys.stdout = outfile

    with open(asmfile, "rt") as file:
        text = file.read()

    # Now the text is available

    # 1. PERFORM TEXT NORMALISATION

    if INTERACTIVE_MODE: print("start_text", json.dumps([text]))
    normalised_text = normalise_text(text)
    if not INTERACTIVE_MODE: print(normalised_text)

    # 2. SPLIT DOCUMENT INTO SECTIONS
    section_dict = split_into_sections(normalised_text)
    if not INTERACTIVE_MODE: pprint(section_dict)
    if INTERACTIVE_MODE: print("split", json.dumps([section_dict["meta"], section_dict["data"], section_dict["text"]]))

    # 3. DIVIDE LINES AND CONTEXTUALISE
    config_dict, instruction_list = divide_and_contextualise(section_dict)

    # 4. RECORD LABELS/VARIABLES
    if INTERACTIVE_MODE: print("start_lv_detect")
    mem_table = record_labels_and_variables(instruction_list)

    # 5. CONVERT EACH LINE TO BYTES
    place_memory_addresses(mem_table, instruction_list)

    bytecode = b""
    bytecode += encode_metadata(config_dict)
    if INTERACTIVE_MODE:
        print("conv_meta", json.dumps(list(bytecode)))
    bytecode += encode_instruction_list(instruction_list, mem_table)

    if INTERACTIVE_MODE:
        print("end", json.dumps(list(bytecode)))
        return

    # Output it as the user wanted
    if out_format == "hex":
        print_bytes_as_hex(bytecode, 16)
    elif out_format == "binstr":
        print(bytecode)
    elif out_format == "return":    # This one is for if the assembler.py module is loaded by another python file
        return bytecode
    elif out_format == "file":
        fname = input("Name of output file: ")
        with open(fname, "wb") as file:
            file.write(bytecode)


if __name__ == "__main__":
    # Interpret the information from the command line arguments
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1].lower() == "<ask>":
            file = input("Input file: ")
        else:
            file = sys.argv[1]

        # Determine the output format
        if len(sys.argv) > 2:
            out_format = sys.argv[2]
        else:
            out_format = input("What output format (hex, binstr or file)? ")

        main(file, out_format)
    else:
        print("Assembly file is unspecified")
