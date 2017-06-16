# -*- coding: utf-8 -*-
"""SMBus backend for rpi2caster-driver"""

from functools import reduce
try:
    # smbus-cffi
    from smbus import SMBus
except ImportError:
    # smbus2
    from smbus2 import SMBus

# Output latch registers for SMBus MCP23017 control
OLATA, OLATB = 0x14, 0x15
# Port direction registers for SMBus MCP23017 control
IODIRA, IODIRB = 0x00, 0x01


class SMBusOutput:
    """Python SMBus-based output controller for rpi2caster."""
    name = 'SMBus output driver'

    def __init__(self, signals, mcp0_address, mcp1_address, i2c_bus=1):
        self.mcp0_address = mcp0_address
        self.mcp1_address = mcp1_address
        self.port = SMBus(i2c_bus)
        # initialize pins as outputs with low initial state
        for address in self.mcp0_address, self.mcp1_address:
            for register in IODIRA, IODIRB, OLATA, OLATB:
                self.port.write_byte_data(address, register, 0x00)
        # map signals to outputs
        signal_numbers = [2 ** x for x in range(32)]
        self.mapping = dict(zip(signals, signal_numbers))

    def _send(self, byte0, byte1, byte2, byte3):
        """Write 4 bytes of data to all ports (A, B)
        on all devices (0, 1)"""
        self.port.write_byte_data(self.mcp0_address, OLATA, byte3)
        self.port.write_byte_data(self.mcp0_address, OLATB, byte2)
        self.port.write_byte_data(self.mcp1_address, OLATA, byte1)
        self.port.write_byte_data(self.mcp1_address, OLATB, byte0)

    def valves_on(self, signals):
        """Get the signals, transform them to numeric value and send
        the bytes to i2c devices"""
        if signals:
            assignment = (self.mapping.get(sig, 0) for sig in signals)
            number = reduce(lambda x, y: x | y, assignment)
            # Split it to four bytes sent in sequence
            byte0 = (number >> 24) & 0xff
            byte1 = (number >> 16) & 0xff
            byte2 = (number >> 8) & 0xff
            byte3 = number & 0xff
        else:
            byte0 = byte1 = byte2 = byte3 = 0x00

        self._send(byte0, byte1, byte2, byte3)

    def valves_off(self):
        """Turn off all the valves"""
        self._send(0x00, 0x00, 0x00, 0x00)
