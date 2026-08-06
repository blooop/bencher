# Research dossier: rerun-native report delivery (#1107)

Evidence base for the grilling session on wayfinder ticket
[#1107](https://github.com/blooop/bencher/issues/1107) — *"How is a rerun-native report
delivered, and what becomes of utils_rrd?"*. This file records facts, not decisions.
Gathered 2026-08-06 against the installed `rerun-sdk 0.35.0` / `rerun-notebook 0.35.0`
(pixi env; project pin is `>=0.32.0,<=0.35.0`).

Companion prototype: `plans/research/build_offline_rerun_html.py` (see §B).

---

## A. Research findings

### A1. `.rrd` / viewer version compatibility

**The documented hard guarantee is "adjacent minor versions"; since 0.32 the blog
promise is stronger ("old data will always load"), and the version is embedded in
every file's header.**

- Official docs ([reference/sdk/operating-modes](https://rerun.io/docs/reference/sdk/operating-modes)):
  "RRD files saved with Rerun 0.23 or later can be opened with a newer Rerun version"
  and "At the moment, we only guarantee compatibility across adjacent minor versions
  (e.g. Rerun 0.24 can open RRDs from 0.23)."
- The [0.23 release blog](https://rerun.io/blog/release-0.23) (Apr 2025) is where
  forward-compat started: 0.23 was "the last release where we break them"; migration
  happens on-the-fly at load. Pre-0.23 files cannot be loaded at all
  ([0.23.0 release notes](https://github.com/rerun-io/rerun/releases/tag/0.23.0)).
- The [0.32 announcement blog](https://rerun.io/blog/data-layer-for-robot-learning)
  (May 2026) upgraded the promise: "In practice we haven't broken compatibility between
  any versions since then and now feel confident to promise **general backward
  compatibility** on the file format… **old data will always load**." Note the docs
  warning above still only *guarantees* adjacent-minor — cite both when deciding what
  bencher may promise downstream.
- The **SDK version is embedded in the .rrd header**. First 8 bytes of a file written
  by SDK 0.35.0 (`xxd tiny.rrd | head -1`):

  ```
  5252 4632 0023 0000   RRF2 . major=0x00 minor=0x23(=35) patch=0x00
  ```

  Magic `RRF2`, then a 4-byte crate version (0.35.0). A delivery layer can therefore
  *read the required viewer version out of the recording itself* instead of trusting a
  filename or sidecar metadata.
- Escape hatch: the SDK ships a full CLI — `pixi run rerun rrd migrate foo.rrd`
  rewrites a recording to the current version (creates `foo.backup.rrd`); also
  `merge` (relevant: the destination report merges many panes into one recording),
  `optimize`, `verify`, `stats`, `print`
  ([CLI reference](https://rerun.io/docs/reference/cli); verified locally against
  rerun-cli 0.35.0).
- Blueprints are the weak spot: `.rbl` compatibility is explicitly out of scope of the
  data-compat promise ([#6410](https://github.com/rerun-io/rerun/issues/6410),
  [#6403](https://github.com/rerun-io/rerun/issues/6403) — blueprints broke 0.15→0.16
  even when data didn't). Interacts with blocked-by ticket #1106.

### A2. Hosted viewer (`app.rerun.io`) permanence

- **No documented permanence policy.** The
  [embed docs](https://rerun.io/docs/howto/integrations/embed-web) show the pinned URL
  pattern `https://app.rerun.io/version/{v}/?url={rrd}` but make no retention promise.
- Empirically (2026-08-06): `/version/0.10.0/` (2023), `/0.20.3/`, `/0.32.0/` all still
  return HTTP 200 (GCS-hosted). Observed behavior, not a contract.

### A3. Self-hosted / offline viewer options in the pinned SDK

The SDK ships the **complete standalone web-viewer app** — no CDN required:

- `rerun_bindings` embeds the viewer app (`index.html` + `re_viewer.js` (222 KB,
  wasm-bindgen no-modules build) + `re_viewer_bg.wasm` (39.8 MB raw / 15.2 MB gzip)).
  `rr.start_web_viewer_server(port=...)` serves it; verified by
  `curl http://localhost:9631/re_viewer.js` etc. against SDK 0.35.0.
  `rr.serve_web_viewer()` is the higher-level variant that also opens a browser.
- `rerun-notebook` (installed as a dependency of `rerun-sdk[notebook]`, present in the
  pixi env) ships viewer assets **inside the wheel**:
  `site-packages/rerun_notebook/static/{widget.js (288 KB), re_viewer_bg.wasm (48 MB)}`.
- `re_viewer.js` contains **zero external URLs** (grep for `https?://` over the served
  file returns nothing). The stock `index.html` has two externals — Google Fonts and a
  telemetry script gated on `hostname == "app.rerun.io"` — both trivially strippable.
- The [`@rerun-io/web-viewer` npm package](https://www.npmjs.com/package/@rerun-io/web-viewer)
  (0.35.0, ~48.5 MB unpacked) also bundles the wasm, so npm-installed usage is fully
  offline; only the CDN/`+esm` route (what `utils_rrd._CDN_VIEWER_TEMPLATE` uses today)
  needs the network. Its README states the version-matching rule: package version ==
  supported SDK version; ≥0.23 can also load the previous minor's files.

### A4. How `rr.notebook_show()` / the `Viewer` widget embeds

**Default is CDN; offline is one env var away.** From the installed
`rerun_notebook/__init__.py` (0.35.0):

- Default asset URL is `https://app.rerun.io/version/{__version__}/notebook/widget.js`
  (line 104) — i.e. **notebook embeds fetch viewer JS+wasm from app.rerun.io by
  default** (chosen because anywidget's inline transmission "results in a memory
  leak", per the [rerun-notebook PyPI page](https://pypi.org/project/rerun-notebook/)).
- `RERUN_NOTEBOOK_ASSET=serve-local` — background thread serves the wheel's static
  assets from localhost (lines 106–110).
- `RERUN_NOTEBOOK_ASSET=inline` — `_inline_widget()` (line 58) gzips the wasm,
  base64s it into a `data:` URL, and splices it into `widget.js` so the whole widget
  is one self-contained ESM string. **This is exactly the trick the prototype in §B
  reuses.** Known caveat: memory/perf issues on Colab
  ([#9274](https://github.com/rerun-io/rerun/issues/9274)).
- `notebook_show` requires a live kernel (data is streamed to the widget); it is not
  itself a save-to-static answer, but it proves the SDK's blessing of the
  local-assets path.

---

## B. Prototype: fully offline single-file HTML viewer

`plans/research/build_offline_rerun_html.py` builds ONE self-contained HTML that opens
a `.rrd` with **zero network access, from `file://`**. Recipe:

1. Fetch `re_viewer.js` + `re_viewer_bg.wasm` from the SDK's own bundled asset server
   (`rr.start_web_viewer_server()`), so the viewer version always matches the SDK that
   wrote the recording.
2. Inline the wasm as gzip+base64, decompressed in-browser with `DecompressionStream`
   (same as `rerun_notebook`'s `inline` mode); init wasm-bindgen from an in-memory
   `Response`.
3. Inline the `.rrd` as base64 and push it through
   `WebHandle.open_channel("inline", ...)` / `send_rrd_to_channel` /
   `close_channel` — the channel API in `re_viewer.js:248,306` — so nothing is fetched.

**Verified, not guessed:**

- `grep -oE 'https?://[a-zA-Z0-9./_-]+' offline_tiny.html` → empty. No external URLs.
- Rendered in headless Chrome with DNS blackholed
  (`--host-resolver-rules="MAP * ~NOTFOUND"`, `file://` URL): screenshot shows the full
  viewer UI with the point cloud, timeline (10 frames), blueprint panel. The 47.7 MB
  variant (22.5 MB recording) renders the same way.
- Nothing blocked full offline. The only wrinkle: `WebAssembly.instantiateStreaming`
  must be deleted on `file://` (the SDK's own `index.html` does the identical hack).

Caveats: browser must support wasm SIMD (Chrome 91+/Firefox 89+/Safari 16.4+, from the
SDK's `index.html` feature probe); ~30 MB+ strings go through `atob`, which is fine in
practice but worth profiling for very large reports.

## C. Size measurements (base64 overhead)

Recordings generated with SDK 0.35.0 (`Points3D`, random float32 — essentially
incompressible, i.e. worst case). `pixi run python plans/research/build_offline_rerun_html.py <rrd> <html>`:

| .rrd size | self-contained HTML | delta over viewer baseline |
|---|---|---|
| 24 KB (tiny) | 17.71 MB | +0.03 MB |
| 1.16 MB (med) | 19.23 MB | +1.55 MB (= 4/3 × rrd) |
| 22.5 MB (big) | 47.70 MB | +30.0 MB (= 4/3 × rrd) |

**Model: `HTML ≈ 17.7 MB (fixed viewer) + 1.33 × rrd_bytes`.** The 17.7 MB floor is
`re_viewer_bg.wasm` (39.8 MB raw → 15.2 MB gzip → 17.45 MB b64) + 222 KB JS. The floor
is paid **once per HTML file**, so for a report of many panes the wasm argues for one
merged recording + blueprint (cf. #1106) or a sidecar layout — N separate self-contained
panes would each carry 17.7 MB. Gzipping the rrd before b64 would help on real (less
random) data; a `DecompressionStream` call is already in the pipeline.

For comparison, today's `inline_rrd_iframes(portable=True)` output is
`1.33 × rrd + ~2 KB` per pane but needs the CDN at view time; the sidecar (default)
mode is `1.0 × rrd` + CDN + an HTTP server.

## D. Inventory of `bencher/utils_rrd.py` (425 lines)

Classification: **(a)** CDN-iframe transport, **(b)** Panel/Tornado serving machinery,
**(c)** generic `.rrd` utility that survives any delivery answer.

| Symbol | Line | Class | Notes |
|---|---|---|---|
| `_get_rerun_version` | :36 | (c) | Resolves viewer version from installed SDK; any backend needs this (or should read it from the RRF2 header, §A1). |
| `rrd_to_pane` | :44 | (a) | `app.rerun.io/version/<v>` iframe around a public URL. Panel-typed return. |
| `publish_and_view_rrd` | :56 | (a) | git-publish + `rrd_to_pane`; CDN and Panel. |
| `rrd_file_to_pane` | :69 | (a)+(b) | Enforces `cachedir/rrd/` root (:118–124), emits iframe at `/rrd_static/` (b) or portable sidecar (a). Panel-typed. |
| `_CDN_VIEWER_TEMPLATE` | :141 | (a) | Viewer page importing `@rerun-io/web-viewer@<v>/+esm` from jsDelivr. |
| `_CDN_VIEWER_INLINE_TEMPLATE` | :166 | (a) | Data inlined base64, viewer still CDN. Halfway to §B's prototype — swap the CDN import for inlined JS+wasm and it becomes (c). |
| `_wrap_viewer_controls` | :194 | (c)-ish | Fullscreen/new-tab chrome; HTML-string-in/out, backend-agnostic, though its href contract is coupled to `inline_rrd_iframes`'s regex. |
| `_cdn_viewer_files` / `_cdn_viewer_html` caches | :229/:232 | (a)/(b) | Keyed by version; one leg serves `/rrd_static/`, the other portable saves. |
| `_cdn_viewer_url` | :235 | (b) | Writes `viewer_<v>.html` into `cachedir/rrd/` for the Panel server route. |
| `_get_cdn_viewer_html` | :257 | (a) | Template cache. |
| `_write_rrd_sidecar` | :264 | (c) | Copies `.rrd` (+ viewer page) into a report dir preserving job-key subdirs; the copy half survives any answer. |
| `_portable_rrd_pane` | :288 | (a) | Sidecar + relative-URL iframe; needs an HTTP origin + CDN. |
| `_RRD_URL_RE` | :329 | (b) | Regex over Bokeh's double-entity-encoded HTML; self-documented as FRAGILE (:326–328); dies with Panel-as-host. |
| `_write_inline_viewer` | :335 | (a) | Base64 rrd into `_CDN_VIEWER_INLINE_TEMPLATE`. |
| `inline_rrd_iframes` | :351 | (b) | Save-time rewrite pass over Panel-saved HTML; called from `bench_report.py:39-41`. Exists only because panes render before the save target is known — a rerun-native backend that knows its target up front doesn't need a post-hoc rewrite. |

Related machinery outside the file:

- `bencher/bench_plot_server.py:186-203` — `_rrd_extra_patterns()` mounts
  `cachedir/rrd/` at `/rrd_static/` via a **Tornado** `_CorsStaticHandler` (the ticket
  text says "Flask"; it is Tornado extra_patterns on `pn.serve`). Class (b).
- `bencher/variables/results.py:460-463` — `ResultRrd`'s only hook into the pane
  builder (a `partial(rrd_file_to_pane, ...)`), i.e. the single seam where a different
  delivery backend would plug in.
- `test/test_rrd_inline.py` — tests pin the (b) regex behavior.

Net: the truly delivery-agnostic core is small — version resolution (:36), the
sidecar file copy (:264), and the viewer-controls chrome (:194). Everything else is
either the CDN transport or the Panel/Tornado host, and the §B prototype shows the CDN
transport has a drop-in offline replacement whose only cost is ~17.7 MB per HTML file.

---

## Implications for the ticket's five questions (facts, not the decision)

1. **What is a saved report on disk?** All three candidates are now demonstrated:
   bare `.rrd` (desktop viewer; version self-describing via RRF2 header), sidecar
   HTML+`.rrd` (today's default save), and fully-offline single HTML (§B, +17.7 MB).
2. **Is the CDN dependency acceptable?** It is no longer *forced*: the SDK bundles the
   viewer (§A3) and the offline single-file path works (§B). app.rerun.io old versions
   are empirically retained but unpromised (§A2).
3. **What survives of the serving machinery?** Only (c)-class items (§D); the Tornado
   `/rrd_static/` route and the save-time regex rewrite are Panel-host artifacts.
4. **Versioning hazard:** the recording carries its writer version in-band (§A1);
   official guarantee adjacent-minor, blog promise "old data always loads" since 0.32;
   `rerun rrd migrate` is the escape hatch; blueprints (`.rbl`) are exempt from the
   promise — relevant to #1106.
5. **Can `show()` and `save()` share one answer?** The same bundled viewer serves
   both: live = SDK asset server / `serve_web_viewer` (or notebook widget with
   `serve-local`), static = the same JS+wasm inlined (§B). One viewer, two
   packagings — the divergence is packaging, not viewer.
