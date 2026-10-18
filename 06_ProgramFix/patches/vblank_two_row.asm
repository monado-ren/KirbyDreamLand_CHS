; SPDX-License-Identifier: MIT
;
; Localization patch: stage-intro BG-map writer, two rows per vblank.
;
; Replaces the routine at ROM file 0x180A0..0x180C8 (bank 6, CPU $40A0..$40C8).
; The original routine streams one row of the stage-intro map from ROM 0x40CA
; into the 0x9800 BG map, 10 entries per call.  The localized stage bundles are
; loaded as one block at VRAM 0x9000 (128 tiles + 576/960-byte map), so the
; writer now streams 12 entries per call from a staged WRAM source at $D40C,
; writing two rows per frame and wrapping the map column at $67.
;
; Original bytes (Rev 1), for review:
;   fa 3a d0   ld a, [$D03A]
;   a7         and a
;   c8         ret z
;   01 45 99   ld bc, $9945
;   11 ca 40   ld de, $40CA
;   21 00 cb   ld hl, $CB00
;   3e 0a      ld a, $0A
; .old_loop:
;   f5         push af
;   78         ld a, b
;   22         ldi [hl], a
;   79         ld a, c
;   22         ldi [hl], a
;   1a         ld a, [de]
;   22         ldi [hl], a
;   13         inc de
;   03         inc bc
;   f1         pop af
;   3d         dec a
;   20 f3      jr nz, .old_loop
;   af         xor a
;   ea 1e cb   ld [$CB1E], a
;   fa 91 ff   ld a, [$FF91]
;   cb d7      set 2, a
;   ea 91 ff   ld [$FF91], a
;   c9         ret
;
; Build note: assembled with RGBDS 1.0.4 (`rgbasm` + `rgblink`).  The build
; itself stays stdlib-only; the assembled replacement bytes are pinned in
; 06_ProgramFix/change_surface.json and this file is re-assembled when RGBDS is
; available (`python 00_Tools/change_surface.py check --rgbds build/rgbds`).

SECTION "vblank_two_row", ROMX[$40A0], BANK[6]
VblankTwoRow:
    ld a, [$D03A]
    and a
    ret z
    ld bc, $9947          ; +2: first written cell (was $9945)
    ld hl, $CB00          ; VRAM queue base
    ld d, $D4             ; staged source high byte ($D40C)
    ld e, $0C             ; 12 entries = two 6-cell rows per frame
.loop:
    ld a, b
    ldi [hl], a
    ld a, c
    ldi [hl], a
    ld a, d
    ldi [hl], a
    inc d
    inc c
    ld a, e
    cp 7                  ; wrap after every 6 map cells ...
    jr nz, .nowrap
    ld c, $67             ; ... back to the next map row start
.nowrap:
    dec e
    jr nz, .loop
    xor a
    ld [hl], a
    ldh a, [$FF91]
    set 2, a
    ldh [$FF91], a
