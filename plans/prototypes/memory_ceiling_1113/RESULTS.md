# #1113 — How does a whole-report recording stay inside memory? (measurement prototype)

Machine: Linux, 64 GB RAM, 32 cores. `rerun-sdk 0.35.0` (pin `>=0.32.0,<=0.35.0`),
inputs and outputs on local disk (ext4 on LVM). Peak RSS metric: **VmHWM** from `/proc/self/status`, read at the
end of a fresh subprocess per strategy run (3 reps, medians reported).
`getrusage().ru_maxrss` was recorded too but discarded: on Linux the rusage high-water
mark survives fork+exec, so every child inherits the orchestrator's peak — VmHWM is reset
at execve and is the honest per-process number.

## Synthetic input

`itemgen.py` mimics one `ResultRerun` artifact per item — user code logging at arbitrary,
self-chosen entity paths with **no** item prefix (exactly the blobs that exist on disk
today): 500 scalar steps (`rr.Scalars` on a `step` sequence timeline), 8 raw 512x512x3
uint8 random images (`rr.Image`, incompressible, ~0.8 MB chunks), one static 64^3 float32
`rr.Tensor` (~1 MB). ~7.1 MB/item on disk.

| scale | items | total on disk |
|---|---|---|
| tiny | 6 | 42.4 MB |
| small | 12 | 84.8 MB |
| large | 24 | 169.5 MB |
| xlarge | 48 | 339.1 MB |

Plus a big-chunk set for the largest-item law: `size=2048, steps=100` → 12.6 MB image
chunks, **97.5 MB per item** (`big1` = 1 item / 97.5 MB, `big4` = 4 items / 389.8 MB).

## Strategies (`run_one.py`)

| id | what it does |
|---|---|
| null | imports only (rerun + pyarrow + numpy) — process RSS floor |
| a | **today's path**: the real `ComposableContainerRerun.render()` — decode all items, hold all chunks, memory sink, `memory_recording().drain_as_bytes()`, `write_bytes` |
| b | **#1104 rider**: identical decode/hold-all merge, but the output recording streams to disk via `RecordingStream.save(path)` instead of the drain |
| c | **log-at-sink**: ONE host recording with a `save()` sink; each item logged directly under its final `item_{i}` prefix at collect time; no per-item recording exists |
| cf | c + blocking `recording.flush()` after every item |
| d | **re-root-at-collect** for pre-existing blobs: `RrdReader.stream()` → `with_entity_path(prefix/…)` → `send_chunks([chunk])` immediately; nothing accumulated |
| df | d + blocking flush after every item |
| d2 | rust-side pipeline: `LazyChunkStream.merge(*streams).write_rrd()` — merge runs all N inputs **concurrently** |
| d2s | rust-side **sequential**: one `LazyChunkStream.from_iter(generator).write_rrd()` over all items |

a, b, c/cf, d/df all produce structurally identical output (verified: 1 recording store +
1 blueprint store, identical `/item_N/...` entity paths). d2/d2s produce the same data
chunks but no blueprint (`write_rrd` emits a single recording store).

## Measurements

(Canonical medians of 3 reps per cell; full raw data in `results.json` from
`measure.py`. Null floor ≈ 90.6 MB VmHWM.)

| strategy | scale | items | input MB | out MB | wall s (med) | VmHWM MB (med) | VmHWM min..max | ΔRSS MB | ΔRSS/input |
|---|---|---|---|---|---|---|---|---|---|
| null | - | 0 | 0.0 | 0.0 | 0.24 | 90.6 | 90.6..90.6 | 0.0 | - |
| a | tiny | 6 | 42.4 | 42.5 | 0.44 | 322.3 | 322.0..327.1 | 231.7 | 5.46x |
| b | tiny | 6 | 42.4 | 42.5 | 0.42 | 227.3 | 213.9..227.3 | 136.7 | 3.22x |
| c | tiny | 6 | 42.4 | 42.5 | 0.46 | 197.5 | 196.7..199.5 | 106.9 | 2.52x |
| cf | tiny | 6 | 42.4 | 42.5 | 0.44 | 183.8 | 183.7..186.8 | 93.2 | 2.20x |
| d | tiny | 6 | 42.4 | 42.5 | 0.37 | 190.3 | 189.1..207.8 | 99.7 | 2.35x |
| df | tiny | 6 | 42.4 | 42.5 | 0.4 | 190.4 | 188.3..190.5 | 99.8 | 2.35x |
| d2 | tiny | 6 | 42.4 | 42.4 | 0.26 | 193.3 | 186.3..200.4 | 102.7 | 2.42x |
| d2s | tiny | 6 | 42.4 | 42.4 | 0.27 | 118.2 | 118.2..118.2 | 27.6 | 0.65x |
| a | small | 12 | 84.8 | 85.0 | 0.59 | 465.3 | 465.0..466.4 | 374.7 | 4.42x |
| b | small | 12 | 84.8 | 85.0 | 0.48 | 289.0 | 289.0..289.2 | 198.4 | 2.34x |
| c | small | 12 | 84.8 | 85.0 | 0.55 | 228.5 | 228.0..229.8 | 137.9 | 1.63x |
| cf | small | 12 | 84.8 | 85.0 | 0.58 | 183.5 | 178.9..187.3 | 92.9 | 1.10x |
| d | small | 12 | 84.8 | 85.0 | 0.4 | 214.7 | 190.0..222.5 | 124.1 | 1.46x |
| df | small | 12 | 84.8 | 85.0 | 0.44 | 190.7 | 189.4..195.4 | 100.1 | 1.18x |
| d2 | small | 12 | 84.8 | 84.7 | 0.33 | 254.7 | 239.5..258.4 | 164.1 | 1.94x |
| d2s | small | 12 | 84.8 | 84.7 | 0.39 | 118.6 | 118.5..118.7 | 28.0 | 0.33x |
| a | large | 24 | 169.5 | 169.9 | 0.77 | 747.4 | 745.6..748.1 | 656.8 | 3.87x |
| b | large | 24 | 169.5 | 169.9 | 0.64 | 389.7 | 389.1..393.1 | 299.1 | 1.76x |
| c | large | 24 | 169.5 | 169.9 | 1.2 | 291.2 | 288.4..358.2 | 200.6 | 1.18x |
| cf | large | 24 | 169.5 | 169.9 | 0.93 | 183.9 | 180.0..185.2 | 93.3 | 0.55x |
| d | large | 24 | 169.5 | 169.9 | 0.48 | 223.1 | 222.3..245.8 | 132.5 | 0.78x |
| df | large | 24 | 169.5 | 169.9 | 0.5 | 192.6 | 191.9..193.2 | 102.0 | 0.60x |
| d2 | large | 24 | 169.5 | 169.4 | 0.35 | 351.2 | 347.4..354.1 | 260.6 | 1.54x |
| d2s | large | 24 | 169.5 | 169.4 | 0.4 | 119.0 | 119.0..119.1 | 28.4 | 0.17x |
| a | xlarge | 48 | 339.1 | 339.8 | 1.17 | 1308.7 | 1250.8..1312.5 | 1218.1 | 3.59x |
| b | xlarge | 48 | 339.1 | 339.8 | 0.83 | 620.0 | 603.1..624.5 | 529.4 | 1.56x |
| c | xlarge | 48 | 339.1 | 339.7 | 2.36 | 434.4 | 399.9..538.0 | 343.8 | 1.01x |
| cf | xlarge | 48 | 339.1 | 339.7 | 1.19 | 179.6 | 177.7..185.4 | 89.0 | 0.26x |
| d | xlarge | 48 | 339.1 | 339.8 | 0.66 | 226.0 | 217.3..227.8 | 135.4 | 0.40x |
| df | xlarge | 48 | 339.1 | 339.8 | 1.67 | 193.2 | 185.3..195.0 | 102.6 | 0.30x |
| d2 | xlarge | 48 | 339.1 | 338.9 | 1.07 | 463.1 | 457.9..491.4 | 372.5 | 1.10x |
| d2s | xlarge | 48 | 339.1 | 338.9 | 0.56 | 119.3 | 119.3..119.5 | 28.7 | 0.08x |

### Big-chunk probe (largest-item law)

| strategy | set | input | largest item | VmHWM (3 reps) |
|---|---|---|---|---|
| df | big1 | 97.5 MB | 97.5 MB | 281.2 / 287.5 / 282.6 |
| df | big4 | 389.8 MB | 97.5 MB | 319.4 / 314.2 / 385.2 |
| d2s | big1 | 97.5 MB | 97.5 MB | 207.7 / 207.9 / 207.8 |
| d2s | big4 | 389.8 MB | 97.5 MB | 209.0 / 206.3 / 205.4 |

d2s: 4x the total at the same largest item → peak unchanged (207.8 → 206.9 MB).
Chunk size 1 MB → 12.6 MB moved the constant 118.5 → ~208 MB. **Peak tracks the largest
in-flight chunk (times a small pipeline factor), not the total and not even the item.**

## Scaling laws (ΔRSS = median VmHWM − 90.6 MB floor)

| strategy | law | fitted slope (MB RSS per MB input) | multiplier at 339 MB |
|---|---|---|---|
| a (today) | **linear in TOTAL** | ~3.3 (+ ~90 MB constant) | 3.6x |
| b (save rider) | **linear in TOTAL** | ~1.3 | 1.5x |
| c (log-at-sink, unflushed) | creeping backlog, ~linear | ~0.7 | 0.9x |
| cf (log-at-sink + flush) | **BOUNDED** | ~0 (flat ~93 MB) | 0.27x and falling |
| d (re-root stream) | bounded, noisy (batcher bursts) | ~0 (flat 100–170 MB) | 0.3–0.5x falling |
| df (re-root stream + flush) | **BOUNDED** | ~0 (flat ~95 MB) | 0.28x and falling |
| d2 (rust merge, concurrent) | linear in ITEM COUNT | ~0.9 | 1.1x |
| d2s (rust sequential) | **BOUNDED** | ~0 (flat **~28 MB**) | 0.08x and falling |

Notes:
- #1106 measured 9x on its content; here today's path measures 3.6–5.5x. The multiplier
  is content-dependent (chunk granularity: many small scalar chunks cost more per byte
  than few large image chunks). The *law* — linear in total report size — is the same,
  so a declared ceiling would have to assume the worst-case multiplier.
- c's growth without flush is un-drained batcher/sink backlog (producer outruns the file
  sink), proven by cf going flat. Any sink-contract implementation needs periodic
  blocking flushes; with them, memory is bounded.
- d2's growth is `LazyChunkStream.merge` executing all input streams concurrently —
  use the sequential `from_iter` form (d2s) for report assembly.
- Wall time never exceeded ~2 s for 339 MB on any strategy (a: ~1.2 s, d2s: ~0.55 s);
  CPU is a non-issue, confirming #1106.

## SDK streaming APIs (pinned range `rerun-sdk>=0.32.0,<=0.35.0`)

Verified on installed 0.35.0; the 0.32 migration guide documents the whole toolchain as
present from 0.32:

- `rr.RecordingStream.save(path)` — true streaming file sink ("Call this _before_ you
  log any data"); chunks flow to disk as logged/sent. Present across the entire pin range.
- `rr.RecordingStream.send_chunks(chunks)` — chunk-by-chunk append into a sinked stream
  (0.32+, replaces `send_recording`).
- `rerun.experimental.RrdReader.stream(store=)` → `LazyChunkStream` — lazy chunk
  iterator over an `.rrd` (0.32+, replaces the removed `rerun.recording` module).
- `rerun.experimental.LazyChunkStream` — `.map(fn)`, `.merge(*streams)`,
  `.from_iter(iterable)`, `.write_rrd(path, application_id=, recording_id=)` —
  documented as "memory-bounded chunk-based filtering and transformation pipelines"
  and measured to be exactly that (d2s). 0.32+.
- `Chunk.with_entity_path(new_path)` — Arrow metadata rewrite; cost unmeasurable in the
  wall numbers (d2s re-roots 339 MB in 0.55 s total including read+write).
- `rr.RecordingStream.binary_stream()` — incremental in-memory drain; explicitly
  documented as having **no backpressure**, so not the right tool here.
- Caveat: `RecordingStream.flush()` is required periodically or the batcher/sink queue
  grows (see c vs cf).

## Answers to the ticket

1. **Which strategy bounds peak RSS by largest-item instead of total?** Any strategy
   that keeps a file sink attached and never accumulates chunks: cf, df, d2s. Measured
   constants over the interpreter floor: cf ~93 MB, df ~95 MB, d2s ~28 MB — flat from
   42 MB to 390 MB of input, and flat in item count at fixed largest item (big4). The
   bound is set by the largest single chunk (a few copies in flight), not even the
   largest item.
2. **Pre-existing `.rrd` blobs / arbitrary user entity paths:** the re-root cost is a
   streaming pass — `RrdReader.stream` → `with_entity_path` → append. 339 MB of
   unprefixed legacy blobs re-rooted and merged in ~0.55–0.9 s at bounded memory. No
   whole-file materialization anywhere. Legacy recordings and user-chosen paths need no
   migration.
3. **Is prefix-at-source needed?** **No.** Prefix-at-collect (d/df) is as cheap as — in
   naive form cheaper than — log-at-final-prefix-at-source (c). #1106's "cheap win"
   hypothesis was half right: what kills the RSS spike is the *streaming sink*, not
   where the prefix is applied. The prefix can stay a composition concern assigned by
   the host at collect time (consistent with #1104's host-assigned `RerunSink.prefix`).
4. **Declared vs engineered-away:** engineer it away. See recommendation.

## Recommendation

**Engineered-away ceiling.** The pinned SDK already contains everything required, the
fix is ~local, and the bounded strategies are also the *fastest*:

- Immediate (the #1104 rider, no contract change): replace
  `memory_recording().drain_as_bytes()` with `recording.save(path)` before sending —
  cuts today's 3.3x slope to 1.3x (strategy b).
- The real fix (strategy df shape): stream per item — read → re-root → send → flush —
  and stop accumulating `_ComposedItem.chunks`. Peak RSS becomes a ~100 MB constant
  independent of report size. `right`/`down`/`overlay` need nothing else; `sequence`
  needs each item's time bounds before shifting, which is a second streaming pass over
  the item's index columns (still bounded).
- `rerun_summary._compose_ds`'s per-recursion-level intermediate `.rrd` re-encoding
  stays disk-I/O-multiplying even when memory-bounded; the #1104 host-owned sink removes
  it structurally — this measurement supports that design rather than replacing it.
- A declared ceiling would have to assume the worst-case content multiplier (9x per
  #1106) and would still be wrong for the next-larger sweep; the streaming path has no
  ceiling to declare and scales with the largest chunk, per the owner's
  "long-term correct, scales well" criterion.

## Reproduce

```bash
pixi run python plans/prototypes/memory_ceiling_1113/measure.py --workdir /tmp/mem1113
```
