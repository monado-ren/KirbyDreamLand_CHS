; SPDX-License-Identifier: MIT
;
; Rev 1 baseline of the stage-intro BG-map writer (bank 6, CPU $40A0..$40C8).
; This is the preimage source: the build assembles it and checks that the bytes
; equal the user-provided baserom before deriving the localized patch diffs.
; It is the one-row/10-entry version; see vblank_two_row.asm for the localized
; two-row/12-entry version.
;
; Assembled with RGBDS 1.0.4 (rgbasm + rgblink).

SECTION "vblank_two_row_rev1", ROMX[$40A0], BANK[6]
VblankTwoRowRev1:
    ld a, [$D03A]
    and a
    ret z
    ld bc, $9945
    ld de, $40CA
    ld hl, $CB00
    ld a, $0A
.loop:
    push af
    ld a, b
    ldi [hl], a
    ld a, c
    ldi [hl], a
    ld a, [de]
    ldi [hl], a
    inc de
    inc bc
    pop af
    dec a
    jr nz, .loop
    xor a
    ld [$CB1E], a
    ld a, [$FF91]
    set 2, a
    ld [$FF91], a
