# SPDX-License-Identifier: MIT
"""Deterministic HAL graphics codec; no ROM, image or third-party dependencies."""
from __future__ import annotations

def reverse_bits(value):
    return int(f'{value:08b}'[::-1], 2)


def decode(data: bytes, start=0, max_output=65536):
    pos = start
    out = bytearray()
    def get():
        nonlocal pos
        if pos >= len(data):
            raise ValueError('TRUNCATED_HAL_STREAM')
        value = data[pos]
        pos += 1
        return value
    while True:
        cmd = get()
        if cmd == 255:
            return bytes(out), pos-start
        if cmd & 0xE0 == 0xE0:
            op = (cmd >> 2) & 7
            length = (((cmd & 3) << 8) | get()) + 1
        else:
            op, length = cmd >> 5, (cmd & 31) + 1
        if op > 6:
            raise ValueError('INVALID_HAL_OPCODE')
        if len(out) + length * (2 if op == 2 else 1) > max_output:
            raise ValueError('HAL_OUTPUT_LIMIT')
        if op == 0:
            out.extend(get() for _ in range(length))
        elif op == 1:
            out.extend([get()] * length)
        elif op == 2:
            pair = bytes([get(), get()])
            out.extend(pair * length)
        elif op == 3:
            value = get()
            out.extend((value+i) & 255 for i in range(length))
        else:
            source = (get() << 8) | get()
            for _ in range(length):
                if not 0 <= source < len(out):
                    raise ValueError('HAL_BACKREF_RANGE')
                value = out[source]
                out.append(reverse_bits(value) if op == 5 else value)
                source += -1 if op == 6 else 1


def header(op, length):
    if not 0 <= op <= 6 or not 1 <= length <= 1024:
        raise ValueError('HAL_COMMAND_RANGE')
    n = length - 1
    return bytes([(op << 5) | n]) if n < 32 else bytes([0xE0 | (op << 2) | (n >> 8), n & 255])


def pack(data):
    """Deterministic greedy HAL compressor, literals + RLE + forward copies.

    Unlike the exhaustive legacy encoder, this handles kilobyte scene bundles
    without quadratic reverse-bit searches. Every stream is decoded and checked.
    """
    out=bytearray();positions={};literals=bytearray();i=0
    def flush():
        while literals:
            part=bytes(literals[:1024]);del literals[:1024]
            out.extend(header(0,len(part)));out.extend(part)
    while i<len(data):
        limit=min(1024,len(data)-i)
        same=1
        while same<limit and data[i+same]==data[i]: same+=1
        best=(same,1,bytes([data[i]])) if same>=3 else (0,0,b'')
        if limit>=3:
            key=data[i:i+3]
            for src in positions.get(key,[])[-64:]:
                n=3
                while n<limit and data[src+n]==data[i+n]: n+=1
                if n>=4 and n>best[0]: best=(n,4,src.to_bytes(2,'big'))
        used,op,payload=best
        if used:
            flush();out.extend(header(op,used));out.extend(payload)
        else:
            used=1;literals.append(data[i])
            if len(literals)==1024:flush()
        for pos in range(i,i+used):
            if pos+3<=len(data):positions.setdefault(data[pos:pos+3],[]).append(pos)
        i+=used
    flush();out.append(255)
    assert decode(out)==(data,len(out))
    return bytes(out)
