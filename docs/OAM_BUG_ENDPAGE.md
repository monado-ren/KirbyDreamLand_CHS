# 结局提示页精灵「闪烁」= DMG OAM bug

## 现象

用 SameBoy 录制日版原版结局提示页（`baserom.gb` + 同一处结局跳转补丁，
帧 13000–15000）时，个别帧的 Kirby 精灵会被画成一条竖线 + 一条横条的
「L」形，看起来像两个精灵叠在一起。同帧号的 PyBoy 录制中从未出现。

最初怀疑是模拟器渲染 bug 或精度选项，实测排除后定位到 **DMG 的 OAM bug**。

## 排查过程

### 1. ROM 里只有一条 OAM 更新路径

| 检查 | 结果 |
| --- | --- |
| `ldh [$46],a`（OAM DMA 触发） | 1 处，bank 5 `$4ACE` |
| `call $FF80`（DMA 例程入口） | 1 处，bank 0 `$1D3F`（VBlank ISR 内） |
| `ld hl,$FE00` / `ld [$FExx],a` / `ld [$FF46],a` / `ld c,$46` | 全部 0 处 |

DMA 源固定 `$C0` → 每帧把 `$C000..$C09F` 拷进 OAM。

### 2. 每帧确实只有一次 OAM DMA

给 `sameboy_capture --trace` 加上 DMA 起始日志（`dma_steps_left` 由 0 变非 0），
f14024–f14029 六帧全部是：

```text
DMA-start line=144 src=C000 pc=FF84 b6
```

### 3. 撕裂帧的现场

同一支 trace 在 OAM 字节发生变化时打印寄存器：

```text
14027  30 OAM[19] 7C->6C pc=5093 b6 DE=FEB4 HL=FF8C SP=FFFA row=20
14027  30 OAM[1A] 58->3A pc=5093 b6 DE=FEB4 HL=FF8C SP=FFFA row=20
14027  30 OAM[1D] 74->84 pc=5093 b6 DE=FEB4 HL=FF8C SP=FFFA row=20
14027  30 OAM[1E] 48->68 pc=5093 b6 DE=FEB4 HL=FF8C SP=FFFA row=20
```

- `DE = $FEB4`，**落在 OAM 地址区间 `$FE00-$FEFF`**
- 出事的指令是 16 位 `dec de`（`$5092`，执行完 PC=`$5093`）
- `accessed_oam_row = 0x20`（PPU 正在访问 OAM；其他帧是 0x68 / 0xA0）

### 4. SameBoy 的实现

`Core/sm83_cpu.c`：

```c
static void cycle_oam_bug(GB_gameboy_t *gb, uint8_t register_id)
{
    if (GB_is_cgb(gb)) { gb->pending_cycles += 4; return; }   /* CGB 没有这个 bug */
    ...
    GB_trigger_oam_bug(gb, gb->registers[register_id]);
    gb->pending_cycles = 4;
}
```

`Core/memory.c`：

```c
void GB_trigger_oam_bug(GB_gameboy_t *gb, uint16_t address)
{
    if (GB_is_cgb(gb)) return;
    if (address >= 0xFE00 && address < 0xFF00) {
        if (gb->accessed_oam_row != 0xff && gb->accessed_oam_row >= 8) {
            gb->oam[row]     = bitwise_glitch(oam[row],     oam[row-8], oam[row-4]);
            gb->oam[row + 1] = bitwise_glitch(oam[row + 1], oam[row-7], oam[row-3]);
            for (unsigned i = 2; i < 8; i++) gb->oam[row + i] = gb->oam[row - 8 + i];
        }
    }
}
```

三个条件在撕裂帧上同时成立：地址在 `$FE00-$FEFF`、PPU 正在访问 OAM、
16 位 INC/DEC。篡改方式是把 `row`、`row-8`、`row-4` 三行做位混合——正好
就是我们实测到的「相邻两行精灵混在一起」。

### 5. PyBoy 没有实现

PyBoy 源码里检索不到任何 OAM bug 相关实现，所以同一帧渲染干净。

## 结论

- **不是 SameBoy 的配置问题**：核心能调的全是外观类（调色板、色彩校正、
  边框、音频滤波、倒带、RTC），DMG 型号也只编译了 `DMG_B`。
- **SameBoy 在这里更准确**：它忠实模拟了 DMG 的 OAM 损坏现象。
- **游戏本身带触发条件**：可见帧里对 DE 做 16 位递减，而 DE 恰好处于
  `$FE00-$FEFF`；真机同样会花屏。
- **与汉化无关**：日版原版 `baserom.gb` 用同样补丁同样复现。

## 复现方式

```bash
# 生成日版原版结局 fixture
python3 - <<'PY'
from pathlib import Path
d = bytearray(Path('baserom.gb').read_bytes())
d[0x1809C:0x1809F] = bytes.fromhex('c3d440')   # 标题 START 分支跳结局
Path('/tmp/jp_ending_extra.gb').write_bytes(bytes(d))
PY

# 指令级采样（frames 14026-14028）
/tmp/sameboy_capture --rom /tmp/jp_ending_extra.gb --boot /tmp/dmg_boot.bin \
  --frames 14030 --input "232:p:start,242:r:start" \
  --record-from 14026 --record-until 14029 --trace /tmp/trace.txt
```

## 对视觉回归包的影响

视觉回归包由 PyBoy 生成，不模拟 OAM bug，因此包里不会出现这些花屏帧。
这是模拟器覆盖面差异，不是数据问题；`baserom.gb` 与本地化 ROM 在这段
代码上完全一致。
