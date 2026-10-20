"""Read BGB 1.6.6 native save states (`.sna`).

The original workspace captured its screenshots with BGB's command line, which
writes a `.sna` next to a PNG:

    bgb64.exe -rom <rom> -state <in.sna> -demoplay <in.dem> \\
              -br '<cpu>/ROMBANK=<n>' -stateonexit <out.sna> -screenonexit <out.png>

Those `.sna` files are a small block container:

    "BGB1.0" ... blocks ... "END " ... <u32 offset of NAME> "BESS"

Each block is `<4-byte name><u32 payload size><payload>`.  The three we need:

* ``CORE`` - 208-byte CPU/IO block.  ``CORE+0x08`` holds PC, ``CORE+0x18`` is a
  copy of the IO registers starting at ``$FF00`` (so ``LCDC`` is at ``$FF40`` =
  ``CORE+0x58``), and ``CORE+0x98``/``0x9C``/``0xBC`` are file offsets of the
  VRAM / WRAM / HRAM copies.
* ``NAME`` - free-form label.
* ``MBC `` - mapper registers.

BGB is a Windows binary and is not vendored here, so this module only *reads*
states.  Two things are still useful without the emulator:

* ``read_*`` gives back the machine state a capture was taken from, which is
  enough to rebuild its screen through ``render_screens``;
* ``edit_state`` reproduces the original workspace's trick of poking WRAM
  before a run (it set ``$D039``/``$D03A`` to force the Extra Game branch).

Example:
    state = load('capture_gallery_01.sna')
    state.io()['LCDC']      # 0xE7 on a settled page
    state.wram(0xD03B)      # current stage
"""

from __future__ import annotations

import struct

HEADER = b'BGB1.0'
FOOTER = b'BESS'
CORE_SIZE = 208

# The IO copy inside CORE starts at $FF00, so this is the delta from a register
# address to its byte in the copy.
IO_BASE = 0xFF00

# Field offsets follow the BESS specification (Best Effort Save State), which is
# what a BGB `.sna` is: a BGB-native blob with a BESS block table appended.  The
# spec is published in SameBoy's repository (BESS.md) and names every field, so
# none of these are guesses.
#
#   0x08 PC   0x0A AF   0x0C BC   0x0E DE   0x10 HL   0x12 SP
#   0x14 IME  0x15 IE   0x16 execution state
#   0x18 128 bytes of memory-mapped IO registers, starting at $FF00
#   0x98 WRAM size   0x9C WRAM offset
#   0xA0 VRAM size   0xA4 VRAM offset
#   0xA8 MBC RAM size  0xAC MBC RAM offset
#   0xB0 OAM size    0xB4 OAM offset
#   0xB8 HRAM size   0xBC HRAM offset
CORE_PC = 0x08
CORE_AF, CORE_BC, CORE_DE, CORE_HL, CORE_SP = 0x0A, 0x0C, 0x0E, 0x10, 0x12
CORE_IME, CORE_IE, CORE_EXECUTION = 0x14, 0x15, 0x16
CORE_IO = 0x18
CORE_WRAM_SIZE, CORE_WRAM_POINTER = 0x98, 0x9C
CORE_VRAM_SIZE, CORE_VRAM_POINTER = 0xA0, 0xA4
CORE_OAM_SIZE, CORE_OAM_POINTER = 0xB0, 0xB4
CORE_HRAM_SIZE, CORE_HRAM_POINTER = 0xB8, 0xBC

WRAM_START = 0xC000
HRAM_START = 0xFF80

REGISTERS = {
    'LCDC': 0xFF40, 'STAT': 0xFF41, 'SCY': 0xFF42, 'SCX': 0xFF43,
    'LY': 0xFF44, 'BGP': 0xFF47, 'OBP0': 0xFF48, 'OBP1': 0xFF49,
    'WY': 0xFF4A, 'WX': 0xFF4B,
}


class StateError(Exception):
    """A `.sna` did not parse as a BGB save state."""


def _require(condition, message):
    if not condition:
        raise StateError(message)


def _blocks(data):
    """Return {name: (payload offset, payload size)} for every block."""
    _require(data.startswith(HEADER), 'not a BGB state (missing BGB1.0 header)')
    _require(data.endswith(FOOTER), 'not a BGB state (missing BESS footer)')
    offset = struct.unpack_from('<I', data, len(data) - 8)[0]
    blocks = {}
    while True:
        _require(offset + 8 <= len(data) - 8, 'block table runs past the file')
        name = data[offset:offset + 4]
        if name == b'END ':
            break
        size = struct.unpack_from('<I', data, offset + 4)[0]
        blocks[name] = (offset + 8, size)
        offset += 8 + size
    return blocks


class State:
    """One parsed BGB save state."""

    def __init__(self, data: bytes):
        self.data = bytes(data)
        blocks = _blocks(self.data)
        _require(b'CORE' in blocks, 'state has no CORE block')
        core, size = blocks[b'CORE']
        _require(size >= CORE_SIZE, 'CORE block is shorter than expected')
        self.core = core
        self._blocks = blocks

    # -- pointers ---------------------------------------------------------
    def _pointer(self, field):
        return struct.unpack_from('<I', self.data, self.core + field)[0]

    def pc(self):
        return struct.unpack_from('<H', self.data, self.core + CORE_PC)[0]

    def _buffer(self, size_field, pointer_field, expected):
        size = self._pointer(size_field)
        at = self._pointer(pointer_field)
        payload = self.data[at:at + size]
        # A short buffer is legal (a CGB state read as DMG), and the spec says to
        # pad it with zeros rather than fail; a long one is truncated.
        return payload[:expected].ljust(expected, b'\x00')

    def vram(self):
        return self._buffer(CORE_VRAM_SIZE, CORE_VRAM_POINTER, 0x2000)

    def wram(self):
        return self._buffer(CORE_WRAM_SIZE, CORE_WRAM_POINTER, 0x2000)

    def hram(self):
        return self._buffer(CORE_HRAM_SIZE, CORE_HRAM_POINTER, 0x7F)

    def oam(self):
        return self._buffer(CORE_OAM_SIZE, CORE_OAM_POINTER, 0xA0)

    def interrupts(self):
        """IME/IE and the execution state, as BESS records them."""
        at = self.core
        return {'IME': self.data[at + CORE_IME],
                'IE': self.data[at + CORE_IE],
                'execution': self.data[at + CORE_EXECUTION]}

    def registers(self):
        """PC/AF/BC/DE/HL/SP as the six 16-bit pairs BESS stores."""
        get = lambda field: struct.unpack_from('<H', self.data, self.core + field)[0]
        return {'PC': get(CORE_PC), 'AF': get(CORE_AF), 'BC': get(CORE_BC),
                'DE': get(CORE_DE), 'HL': get(CORE_HL), 'SP': get(CORE_SP)}

    def io(self):
        """The IO registers, keyed by name ($FF40..$FF4B and friends)."""
        at = self.core + CORE_IO
        return {name: self.data[at + (address - IO_BASE)]
                for name, address in REGISTERS.items()}

    def read_wram(self, address):
        _require(WRAM_START <= address < 0xE000, 'address outside WRAM: ' + hex(address))
        return self.wram()[address - WRAM_START]

    def read_hram(self, address):
        _require(HRAM_START <= address < 0xFFFF, 'address outside HRAM: ' + hex(address))
        return self.hram()[address - HRAM_START]

    def read(self, address):
        if WRAM_START <= address < 0xE000:
            return self.read_wram(address)
        if HRAM_START <= address < 0xFFFF:
            return self.read_hram(address)
        raise StateError('only WRAM and HRAM are addressable: ' + hex(address))

    def bg_map(self):
        """The 32x32 background map at $9800."""
        return self.vram()[0x1800:0x1C00]


def load(path):
    from pathlib import Path
    return State(Path(path).read_bytes())


def parse(data):
    return State(data)


def edit_state(source, destination, writes):
    """Write WRAM/HRAM bytes and save the result as a new `.sna`.

    This mirrors the original workspace's `edit_state`, which it used to flip
    the Extra Game flag before a run.
    """
    from pathlib import Path
    state = State(Path(source).read_bytes())
    data = bytearray(state.data)
    at_wram = state._pointer(CORE_WRAM_POINTER)
    at_hram = state._pointer(CORE_HRAM_POINTER)
    for address, value in writes.items():
        if WRAM_START <= address < 0xE000:
            data[at_wram + address - WRAM_START] = value
        elif HRAM_START <= address < 0xFFFF:
            data[at_hram + address - HRAM_START] = value
        else:
            raise StateError('cannot poke outside WRAM/HRAM: ' + hex(address))
    Path(destination).write_bytes(bytes(data))
    return destination


def describe(state):
    """Human-readable one-liner used by the audit tools."""
    io = state.io()
    return ('PC=0x%04X LCDC=0x%02X BGP=0x%02X SCY=%d SCX=%d WY=%d WX=%d'
            % (state.pc(), io['LCDC'], io['BGP'], io['SCY'], io['SCX'],
               io['WY'], io['WX']))
