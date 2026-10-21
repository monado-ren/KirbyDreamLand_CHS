/*
 * sameboy_capture - headless capture driver built on SameBoy's core.
 *
 * The original workspace drove BGB from a command line:
 *
 *   bgb64.exe -rom R -state IN.sna -demoplay IN.dem \
 *             -br 'ADDR/ROMBANK=N' -stateonexit OUT.sna -screenonexit OUT.png
 *
 * SameBoy's SDL frontend only accepts `[--fullscreen] [rom]`, so this program
 * links Core/ directly and offers the same capabilities.  A BGB `.sna` is a BESS
 * file, and SameBoy's core both reads and writes BESS, so states move between
 * the two emulators unchanged.
 *
 * Usage:
 *   sameboy_capture --rom R [--state S] [--frames N] [--shot P]
 *                   [--breakpoint ADDR] [--save-state P] [--model dmg|cgb]
 *                   [--boot dmg_boot.bin] [--keys F:key+key,...] [--keys-hold N]
 *                   [--input SCRIPT] [--record PATH] [--record-from F]
 *                   [--record-until F] [--dump PATH]
 *
 * --boot is required in practice.  SameBoy has no built-in boot ROM: without one
 * the CPU never leaves the boot area, the LCD stays off and no frame is ever
 * produced.  Supply SameBoy's own open-source replacement (BootROMs/dmg_boot.asm,
 * 256 bytes); the checksum used here is in docs/SAMEBOY_CAPTURE.md.
 *
 * --keys drives input without a .dem file, e.g. `--keys 240:start`.
 *
 * --input is the exact-frame form the recorded sessions need:
 *   "232:p:up+select+a,236:r:up+select+a,267:p:start,277:r:start"
 * Each event is `<frame>:<p|r>:<key>[+<key>...]` and is applied *before* that
 * frame runs, so frame F sees the new key state.
 *
 * --record streams raw RGB24 frames (160x144) to PATH, or to stdout when PATH is
 * `-`, so a pipe can feed ffmpeg without touching the disk.  --record-from and
 * --record-until bound the range (default 0 .. --frames).
 *
 * --dump writes the final machine state as raw VRAM (0x2000) + OAM (0xA0) +
 * I/O registers (0x80) so two emulators can be compared at the same frame.
 *
 * Exit codes: 0 done, 1 usage/IO error, 2 breakpoint reached before --frames.
 */

#include <Core/gb.h>

#include <png.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static GB_gameboy_t gb;
static uint32_t pixels[160 * 144];

static uint16_t breakpoint_address;
static bool breakpoint_armed;
static bool breakpoint_hit;

static uint32_t rgb_encode(GB_gameboy_t *gameboy, uint8_t r, uint8_t g, uint8_t b)
{
    (void) gameboy;
    return ((uint32_t) r << 16) | ((uint32_t) g << 8) | b;
}

static void noop_log(GB_gameboy_t *gameboy, const char *string,
                     GB_log_attributes attributes)
{
    (void) gameboy;
    (void) string;
    (void) attributes;
}

/* Checked once per frame; the original chain only ever stopped between frames. */
static void vblank(GB_gameboy_t *gameboy)
{
    if (breakpoint_armed && gameboy->pc == breakpoint_address) {
        breakpoint_hit = true;
    }
}

static bool write_png(const char *path, const uint32_t *source,
                      unsigned width, unsigned height)
{
    FILE *file = fopen(path, "wb");
    if (!file) {
        fprintf(stderr, "cannot open %s for writing\n", path);
        return false;
    }
    png_structp png = png_create_write_struct(PNG_LIBPNG_VER_STRING, NULL, NULL, NULL);
    if (!png) { fclose(file); return false; }
    png_infop info = png_create_info_struct(png);
    if (!info) { png_destroy_write_struct(&png, NULL); fclose(file); return false; }
    if (setjmp(png_jmpbuf(png))) {
        png_destroy_write_struct(&png, &info);
        fclose(file);
        return false;
    }
    png_init_io(png, file);
    png_set_IHDR(png, info, width, height, 8, PNG_COLOR_TYPE_RGB,
                 PNG_INTERLACE_NONE, PNG_COMPRESSION_TYPE_DEFAULT,
                 PNG_FILTER_TYPE_DEFAULT);
    png_write_info(png, info);
    png_bytep row = malloc((size_t) width * 3);
    if (!row) { png_destroy_write_struct(&png, &info); fclose(file); return false; }
    for (unsigned y = 0; y < height; y++) {
        for (unsigned x = 0; x < width; x++) {
            uint32_t p = source[y * width + x];
            row[x * 3 + 0] = (png_byte) ((p >> 16) & 0xFF);
            row[x * 3 + 1] = (png_byte) ((p >> 8) & 0xFF);
            row[x * 3 + 2] = (png_byte) (p & 0xFF);
        }
        png_write_row(png, row);
    }
    free(row);
    png_write_end(png, NULL);
    png_destroy_write_struct(&png, &info);
    fclose(file);
    return true;
}

/* One raw RGB24 frame, 160x144, written straight to the recording stream. */
static bool write_frame(FILE *stream)
{
    static uint8_t row[160 * 3];
    for (unsigned y = 0; y < 144; y++) {
        for (unsigned x = 0; x < 160; x++) {
            uint32_t p = pixels[y * 160 + x];
            row[x * 3 + 0] = (uint8_t) ((p >> 16) & 0xFF);
            row[x * 3 + 1] = (uint8_t) ((p >> 8) & 0xFF);
            row[x * 3 + 2] = (uint8_t) (p & 0xFF);
        }
        if (fwrite(row, 1, sizeof(row), stream) != sizeof(row)) return false;
    }
    return true;
}

/* --keys takes a tiny script: comma-separated "<frame>:<key>[+<key>...]".
 * At each listed frame the keys are pressed for --keys-hold frames (default 8).
 * This mirrors the button demos the original BGB driver fed via -demoplay. */
typedef struct { unsigned frame; GB_key_t keys[4]; unsigned count; } key_step_t;

/* --input takes absolute press/release events:
 * "<frame>:<p|r>:<key>[+<key>...]". */
typedef struct {
    unsigned frame;
    bool press;
    GB_key_t keys[4];
    unsigned count;
} input_event_t;

static GB_key_t key_from_name(const char *name)
{
    static const struct { const char *name; GB_key_t key; } table[] = {
        {"right", GB_KEY_RIGHT}, {"left", GB_KEY_LEFT}, {"up", GB_KEY_UP},
        {"down", GB_KEY_DOWN}, {"a", GB_KEY_A}, {"b", GB_KEY_B},
        {"select", GB_KEY_SELECT}, {"start", GB_KEY_START},
    };
    for (size_t i = 0; i < sizeof(table) / sizeof(table[0]); i++)
        if (strcmp(table[i].name, name) == 0) return table[i].key;
    return GB_KEY_MAX;
}

static const char *arg_value(int argc, char **argv, const char *name)
{
    for (int i = 1; i < argc - 1; i++)
        if (strcmp(argv[i], name) == 0) return argv[i + 1];
    return NULL;
}

static bool has_flag(int argc, char **argv, const char *name)
{
    for (int i = 1; i < argc; i++)
        if (strcmp(argv[i], name) == 0) return true;
    return false;
}

static uint8_t *read_file(const char *path, size_t *size)
{
    FILE *file = fopen(path, "rb");
    if (!file) return NULL;
    fseek(file, 0, SEEK_END);
    long length = ftell(file);
    rewind(file);
    if (length <= 0) { fclose(file); return NULL; }
    uint8_t *buffer = malloc((size_t) length);
    if (buffer && fread(buffer, 1, (size_t) length, file) != (size_t) length) {
        free(buffer); buffer = NULL;
    }
    fclose(file);
    if (buffer) *size = (size_t) length;
    return buffer;
}

static unsigned parse_events(const char *script, input_event_t *events,
                             unsigned capacity)
{
    unsigned count = 0;
    if (!script) return 0;
    char *copy = strdup(script);
    /* strtok_r, not strtok: the key list is split inside the event loop, and
     * plain strtok() shares one parse position, which truncated the event list
     * after the first entry and silently dropped every key release. */
    char *outer_save = NULL;
    for (char *entry = strtok_r(copy, ",", &outer_save); entry && count < capacity;
         entry = strtok_r(NULL, ",", &outer_save)) {
        char *first = strchr(entry, ':');
        if (!first) continue;
        *first = 0;
        char *second = strchr(first + 1, ':');
        if (!second) continue;
        *second = 0;
        input_event_t *event = &events[count];
        event->frame = (unsigned) strtoul(entry, NULL, 0);
        event->press = strcmp(first + 1, "p") == 0;
        event->count = 0;
        char *inner_save = NULL;
        char *key_text = strtok_r(second + 1, "+", &inner_save);
        while (key_text && event->count < 4) {
            GB_key_t key = key_from_name(key_text);
            if (key != GB_KEY_MAX) event->keys[event->count++] = key;
            key_text = strtok_r(NULL, "+", &inner_save);
        }
        if (event->count) count++;
    }
    free(copy);
    return count;
}

int main(int argc, char **argv)
{
    const char *rom_path = arg_value(argc, argv, "--rom");
    const char *state_path = arg_value(argc, argv, "--state");
    const char *shot_path = arg_value(argc, argv, "--shot");
    const char *save_path = arg_value(argc, argv, "--save-state");
    const char *break_text = arg_value(argc, argv, "--breakpoint");
    const char *frames_text = arg_value(argc, argv, "--frames");
    const char *model_text = arg_value(argc, argv, "--model");
    const char *boot_path = arg_value(argc, argv, "--boot");
    const char *record_path = arg_value(argc, argv, "--record");
    const char *record_from_text = arg_value(argc, argv, "--record-from");
    const char *record_until_text = arg_value(argc, argv, "--record-until");
    const char *dump_path = arg_value(argc, argv, "--dump");
    const char *oam_log_path = arg_value(argc, argv, "--oam-log");
    const char *trace_path = arg_value(argc, argv, "--trace");

    if (!rom_path || has_flag(argc, argv, "--help")) {
        fprintf(stderr,
            "Usage: %s --rom R [--state S] [--frames N] [--shot P]\n"
            "          [--breakpoint ADDR] [--save-state P] [--model dmg|cgb]\n"
            "          [--boot dmg_boot.bin] [--keys F:key+key,...] [--keys-hold N]\n"
            "          [--input F:p|r:key+key,...] [--record PATH|-]\n"
            "          [--record-from F] [--record-until F] [--dump PATH]\n"
            "          [--oam-log PATH] [--trace PATH]\n",
            argv[0]);
        return 1;
    }

    unsigned frames = frames_text ? (unsigned) strtoul(frames_text, NULL, 0) : 0;
    unsigned record_from = record_from_text
        ? (unsigned) strtoul(record_from_text, NULL, 0) : 0;
    unsigned record_until = record_until_text
        ? (unsigned) strtoul(record_until_text, NULL, 0) : frames;
    if (record_until > frames) record_until = frames;
    GB_model_t model = GB_MODEL_DMG_B;
    if (model_text && strcmp(model_text, "cgb") == 0) model = GB_MODEL_CGB_E;

    GB_init(&gb, model);
    GB_set_rgb_encode_callback(&gb, rgb_encode);
    GB_set_log_callback(&gb, noop_log);
    GB_set_pixels_output(&gb, pixels);

    /* SameBoy needs a boot ROM; without one the CPU never leaves the boot area,
     * the LCD stays off, and GB_run_frame waits forever for a VBlank. */
    if (boot_path && GB_load_boot_rom(&gb, boot_path)) {
        fprintf(stderr, "cannot read boot ROM: %s\n", boot_path);
        GB_free(&gb);
        return 1;
    }

    if (GB_load_rom(&gb, rom_path)) {
        fprintf(stderr, "failed to load ROM: %s\n", rom_path);
        GB_free(&gb);
        return 1;
    }

    if (state_path) {
        size_t size = 0;
        uint8_t *buffer = read_file(state_path, &size);
        if (!buffer) {
            fprintf(stderr, "cannot read state: %s\n", state_path);
            GB_free(&gb); return 1;
        }
        int status = GB_load_state_from_buffer(&gb, buffer, size);
        free(buffer);
        if (status) {
            fprintf(stderr, "failed to load state: %s\n", state_path);
            GB_free(&gb); return 1;
        }
    }

    if (break_text) {
        breakpoint_address = (uint16_t) strtoul(break_text, NULL, 0);
        breakpoint_armed = true;
        GB_set_vblank_callback(&gb, vblank);
    }

    unsigned keys_hold = 8;
    const char *hold_text = arg_value(argc, argv, "--keys-hold");
    if (hold_text) keys_hold = (unsigned) strtoul(hold_text, NULL, 0);

    static key_step_t steps[64];
    unsigned step_count = 0;
    const char *script = arg_value(argc, argv, "--keys");
    if (script) {
        char *copy = strdup(script);
        for (char *entry = strtok(copy, ","); entry && step_count < 64;
             entry = strtok(NULL, ",")) {
            char *colon = strchr(entry, ':');
            if (!colon) continue;
            *colon = 0;
            key_step_t *step = &steps[step_count++];
            step->frame = (unsigned) strtoul(entry, NULL, 0);
            char *key_text = strtok(colon + 1, "+");
            while (key_text && step->count < 4) {
                GB_key_t key = key_from_name(key_text);
                if (key != GB_KEY_MAX) step->keys[step->count++] = key;
                key_text = strtok(NULL, "+");
            }
        }
        free(copy);
    }

    static input_event_t events[256];
    unsigned event_count = parse_events(arg_value(argc, argv, "--input"), events, 256);

    FILE *trace = NULL;
    if (trace_path) {
        trace = fopen(trace_path, "w");
        if (!trace) {
            fprintf(stderr, "cannot open %s for trace\n", trace_path);
            GB_free(&gb); return 1;
        }
    }

    FILE *oam_log = NULL;
    if (oam_log_path) {
        oam_log = fopen(oam_log_path, "wb");
        if (!oam_log) {
            fprintf(stderr, "cannot open %s for OAM log\n", oam_log_path);
            GB_free(&gb); return 1;
        }
    }

    FILE *record = NULL;
    if (record_path) {
        record = strcmp(record_path, "-") == 0 ? stdout : fopen(record_path, "wb");
        if (!record) {
            fprintf(stderr, "cannot open %s for recording\n", record_path);
            GB_free(&gb); return 1;
        }
    }

    for (unsigned i = 0; i < frames && !breakpoint_hit; i++) {
        for (unsigned s = 0; s < event_count; s++) {
            if (events[s].frame != i) continue;
            for (unsigned k = 0; k < events[s].count; k++)
                GB_set_key_state(&gb, events[s].keys[k], events[s].press);
        }
        for (unsigned s = 0; s < step_count; s++) {
            if (steps[s].frame != i) continue;
            for (unsigned k = 0; k < steps[s].count; k++)
                GB_set_key_state(&gb, steps[s].keys[k], true);
            for (unsigned hold = 0; hold < keys_hold; hold++) GB_run_frame(&gb);
            for (unsigned k = 0; k < steps[s].count; k++)
                GB_set_key_state(&gb, steps[s].keys[k], false);
        }
        if (trace && i >= record_from && i < record_until) {
            /* Step instruction by instruction so a mid-frame shadow update can be
             * told apart from a VBlank DMA.  Only changes are logged. */
            static unsigned last_line = 0xFFFF, last_ff46 = 0xFFFF;
            static uint32_t last_shadow = 0, last_oam = 0;
            while (true) {
                GB_run(&gb);
                size_t ws = 0, os = 0;
                uint8_t *wram = GB_get_direct_access(&gb, GB_DIRECT_ACCESS_RAM, &ws, NULL);
                uint8_t *oam = GB_get_direct_access(&gb, GB_DIRECT_ACCESS_OAM, &os, NULL);
                uint32_t shadow_hash = 2166136261u, oam_hash = 2166136261u;
                for (size_t k = 0; k < 0xA0 && wram && k < ws; k++)
                    shadow_hash = (shadow_hash ^ wram[k]) * 16777619u;
                for (size_t k = 0; k < os; k++)
                    oam_hash = (oam_hash ^ oam[k]) * 16777619u;
                unsigned ff46 = gb.io_registers[0x46];
                unsigned line = gb.current_lcd_line;
                if (line != last_line || ff46 != last_ff46
                    || shadow_hash != last_shadow || oam_hash != last_oam) {
                    if (oam_hash != last_oam && oam) {
                        static uint8_t previous_oam[0xA0];
                        for (size_t k = 0; k < 0xA0 && k < os; k++) {
                            if (previous_oam[k] != oam[k])
                                fprintf(trace, "%u %3u OAM[%02zX] %02X->%02X pc=%04X b%u\n",
                                        i, line, k, previous_oam[k], oam[k],
                                        gb.pc, gb.mbc_rom_bank);
                            previous_oam[k] = oam[k];
                        }
                    }
                    fprintf(trace, "%u %3u %02X %08X %08X %04X %u\n",
                            i, line, ff46, shadow_hash, oam_hash, gb.pc,
                            gb.mbc_rom_bank);
                    last_line = line; last_ff46 = ff46;
                    last_shadow = shadow_hash; last_oam = oam_hash;
                }
                if (gb.vblank_just_occured) break;
            }
        } else {
            GB_run_frame(&gb);
        }
        if (oam_log && i >= record_from && i < record_until) {
            size_t oam_size = 0;
            uint8_t *oam = GB_get_direct_access(&gb, GB_DIRECT_ACCESS_OAM, &oam_size, NULL);
            if (oam && fwrite(oam, 1, oam_size, oam_log) != oam_size) {
                fprintf(stderr, "cannot write OAM log at frame %u\n", i);
                fclose(oam_log); GB_free(&gb); return 1;
            }
        }
        if (record && i >= record_from && i < record_until && !write_frame(record)) {
            fprintf(stderr, "cannot write recorded frame %u\n", i);
            if (record != stdout) fclose(record);
            GB_free(&gb); return 1;
        }
    }

    if (record) {
        fflush(record);
        if (record != stdout) fclose(record);
    }
    if (oam_log) fclose(oam_log);
    if (trace) fclose(trace);

    if (shot_path && !write_png(shot_path, pixels, 160, 144)) {
        GB_free(&gb); return 1;
    }

    if (save_path) {
        size_t size = GB_get_save_state_size(&gb);
        uint8_t *buffer = malloc(size);
        if (!buffer) { GB_free(&gb); return 1; }
        GB_save_state_to_buffer(&gb, buffer);
        FILE *file = fopen(save_path, "wb");
        bool ok = file && fwrite(buffer, 1, size, file) == size;
        if (file) fclose(file);
        free(buffer);
        if (!ok) {
            fprintf(stderr, "cannot write state: %s\n", save_path);
            GB_free(&gb); return 1;
        }
    }

    if (dump_path) {
        size_t vram_size = 0, oam_size = 0, ram_size = 0;
        uint8_t *vram = GB_get_direct_access(&gb, GB_DIRECT_ACCESS_VRAM, &vram_size, NULL);
        uint8_t *oam = GB_get_direct_access(&gb, GB_DIRECT_ACCESS_OAM, &oam_size, NULL);
        uint8_t *ram = GB_get_direct_access(&gb, GB_DIRECT_ACCESS_RAM, &ram_size, NULL);
        FILE *dump = fopen(dump_path, "wb");
        if (!dump || !vram || !oam || !ram
            || fwrite(vram, 1, vram_size, dump) != vram_size
            || fwrite(oam, 1, oam_size, dump) != oam_size
            || fwrite(ram, 1, ram_size, dump) != ram_size
            || fwrite(gb.io_registers, 1, 0x80, dump) != 0x80) {
            fprintf(stderr, "cannot write dump: %s\n", dump_path);
            if (dump) fclose(dump);
            GB_free(&gb); return 1;
        }
        fclose(dump);
    }

    size_t io_size = 0, vram_size = 0;
    uint8_t *io = GB_get_direct_access(&gb, GB_DIRECT_ACCESS_IO, &io_size, NULL);
    uint8_t *vram = GB_get_direct_access(&gb, GB_DIRECT_ACCESS_VRAM, &vram_size, NULL);
    unsigned vram_nonzero = 0;
    for (size_t i = 0; vram && i < vram_size; i++) vram_nonzero += vram[i] != 0;
    unsigned pixel_nonzero = 0;
    for (unsigned i = 0; i < 160 * 144; i++) pixel_nonzero += pixels[i] != 0;
    fprintf(stderr, "PC=%04X frames=%u LCDC=%02X vram_nz=%u pixel_nz=%u%s\n",
            gb.pc, frames, io ? io[0x40] : 0, vram_nonzero, pixel_nonzero,
            breakpoint_hit ? " (breakpoint)" : "");

    GB_free(&gb);
    return breakpoint_hit ? 2 : 0;
}
