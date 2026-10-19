# SPDX-License-Identifier: MIT
"""Relocate edited graphics resources into free expanded-ROM space.

The v0.5.1 snapshot allocates most resources with zero spare capacity: offsets
are packed back to back, so a page edit that compresses even one byte larger no
longer fits its original slot.  This module moves such a resource to a free gap
inside the expanded 256 KiB area and rewrites the loader patches that point at
it, so the edited resource keeps working without touching original game code.

Only patches already present in the manifest are rewritten (no new patch is
invented); a resource without a recognised loader patch is refused, because a
silently unpointed copy would corrupt the game.
"""
from __future__ import annotations

import common

GRAPHICS_LOW = 0x40000
GRAPHICS_HIGH = 0x80000


def allocations(manifest):
    return sorted(((r['offset'], r['offset'] + r['capacity']) for r in manifest['resources']),
                  key=lambda item: item[0])


def free_gaps(manifest):
    gaps = []
    cursor = GRAPHICS_LOW
    for start, end in allocations(manifest):
        if start > cursor:
            gaps.append((cursor, start))
        cursor = max(cursor, end)
    if cursor < GRAPHICS_HIGH:
        gaps.append((cursor, GRAPHICS_HIGH))
    return gaps


def _align_up(value, alignment):
    return (value + alignment - 1) // alignment * alignment


def loader_patches(manifest, label):
    """Patch entries whose field names start with the resource label token."""
    matched = []
    for item in manifest['patches']:
        fields = item['field'].split(';')
        if any(field == label or field.startswith(label + '_') for field in fields):
            matched.append(item)
    return matched


def rewrite_loader(manifest, label, old_bank, old_cpu, new_bank, new_cpu):
    """Rewrite loader patches from one resource location to another.

    Returns ``(changed_patches, address_sites, bank_sites)``.  An address site
    stores the CPU address as two little-endian bytes; a bank site is a
    one-byte patch whose old value equals the previous bank number.
    """
    old_address = old_cpu.to_bytes(2, 'little')
    new_address = new_cpu.to_bytes(2, 'little')
    address_sites = bank_sites = 0
    changed = 0
    for item in loader_patches(manifest, label):
        replacement = bytearray(bytes.fromhex(item['replacement_hex']))
        touched = False
        position = replacement.find(old_address)
        while position >= 0:
            replacement[position:position + 2] = new_address
            address_sites += 1
            touched = True
            position = replacement.find(old_address, position + 2)
        if len(replacement) == 1 and replacement[0] == old_bank:
            replacement[0] = new_bank
            bank_sites += 1
            touched = True
        if touched:
            item['replacement_hex'] = bytes(replacement).hex()
            changed += 1
    return changed, address_sites, bank_sites


def relocate(manifest, entry, size):
    """Move one resource into a free gap and update its loader patches.

    Returns the updated entry.  The resource keeps its CPU address when the
    loader only patches its bank byte (that is how bank-aligned graphics are
    referenced), otherwise any bank-internal address is accepted.
    """
    require = common.require
    old_bank, old_cpu = entry['bank'], entry['cpu_address']
    old_patches = loader_patches(manifest, entry['label'])
    require(old_patches, 'No loader patch references ' + entry['id'] + '; refusing to relocate')
    address_hint = old_cpu.to_bytes(2, 'little')
    address_sites = sum(1 for item in old_patches
                        if address_hint in bytes.fromhex(item['replacement_hex']))
    require(size <= 0x4000, 'A resource cannot grow beyond one 16 KiB bank')
    required_offset = 0 if address_sites else (old_cpu - 0x4000)
    placement = None
    for start, end in free_gaps(manifest):
        # Bank-referenced resources (those whose loader patches only carry a bank
        # byte) are addressed as base+0 of their bank, so they must land exactly
        # at a bank boundary.  Resources that also patch an address may keep any
        # in-bank offset, which is why required_offset is added after aligning.
        candidate = _align_up(start, 0x4000) + required_offset
        if candidate + size > end:
            continue
        if candidate // 0x4000 != (candidate + size - 1) // 0x4000:
            continue
        placement = candidate
        break
    require(placement is not None,
            'No free contiguity of ' + str(size) + ' bytes for ' + entry['id'])
    new_bank = placement // 0x4000
    new_cpu = 0x4000 + placement % 0x4000
    changed, address_sites, bank_sites = rewrite_loader(
        manifest, entry['label'], old_bank, old_cpu, new_bank, new_cpu)
    require(changed > 0, 'Loader patch for ' + entry['id'] + ' was not recognised')
    entry['offset'] = placement
    entry['bank'] = new_bank
    entry['cpu_address'] = new_cpu
    entry['capacity'] = size
    entry['relocated_from'] = {'offset': entry['offset'], 'bank': old_bank,
                               'cpu_address': old_cpu}
    print('RELOCATE=' + entry['id'] + ' 0x' + format(placement, '05X')
          + ' bank=' + str(new_bank) + ' cpu=0x' + format(new_cpu, '04X')
          + ' patches=' + str(changed) + ' addr_sites=' + str(address_sites)
          + ' bank_sites=' + str(bank_sites))
    return entry
