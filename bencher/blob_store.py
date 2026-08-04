"""Content-addressed blob store for materializing result payloads at collect time.

This module implements design D1 of the grammar phase-1 data model
(plans/22-grammar-phase-1-data-model.md, A6 Law 1): result payloads that
cannot live directly in a dataset cell are serialized under
``<cache_dir>/blobs/`` and the cell stores the returned **blob name**
instead of a run-local index.  Filenames are derived from the sha256 of the
serialized bytes, so identical payloads across repeats and time points
deduplicate to a single file for free.

A cell holds the name alone, never a directory — the name *is* the content
hash, so it is a complete identity and the directory prefix adds nothing a
reader could not recompute.  What the prefix does add is a dependency on the
absolute location of the cache dir at collect time, which is exactly what an
``over_time`` history outlives: a cache dir gets tarred on one machine and
restored at another path (CI cache round-trips), copied between checkouts, or
rendered from a different working directory than the sweep ran in.  Storing a
location made every historical cell in a relocated cache dangle while its blob
sat intact under the same content-addressed name.  :func:`resolve_blob` is the
one place that turns a cell back into a file, and it resolves names against the
*active* cache dir for that reason.  ``cache_management`` reached the same
conclusion independently for reachability (see :func:`blob_name`).

A name alone is a complete *identity* but not a complete *address*, so dropping
the directory cannot be the whole story: a cell that names no location resolves
only where a ``cachedir`` happens to sit in the reader's working directory, and
``bencher <result.pkl> <out>`` renders wherever the user invoked it.  The cache
dir a result was collected under is therefore recorded once per dataset
(:data:`BLOB_CACHE_DIR_ATTR`) and tried after the active one, so both the moved
cache and the foreign working directory resolve — see :func:`resolve_blob` for
the full order.

Supported formats, dispatched on the payload type:

- ``pandas.DataFrame`` → ``.parquet`` (falls back to ``.pkl`` when the
  contents cannot be written as parquet, e.g. nested-object columns)
- ``xarray.Dataset`` → ``.nc`` (netCDF3 via the scipy engine; falls back to
  ``.pkl`` when any data var or coord dtype is not netCDF3-safe, so payloads
  never round-trip with silently changed dtypes)
- ``xarray.DataArray`` → ``.da.nc`` (same dtype rules; loads back as a
  ``DataArray`` with its ``name`` preserved)
- ``bytes`` → ``.bin`` (raw)
- anything else picklable, including str/Path payloads → ``.pkl`` (a path
  string is an ordinary payload: it is pickled, never dereferenced, so the
  render-time container receives exactly the string the worker stored and
  every blob stays under the cache dir)

.. warning::
    The ``.pkl`` fallback is the pickle surface that architecture plan A3
    wants gone.  It exists only because ``ResultDataSet`` documents its
    payload as "any picklable object"; the A3 migration should tighten this
    to the structured formats above with its own deprecation story.
"""

import hashlib
import io
import logging
import os
import pickle
import re
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import xarray as xr

logger = logging.getLogger(__name__)

# Number of hex characters of the sha256 digest used in blob filenames.
#
# 16 hex chars is 64 bits of the digest, so content addressing is exact only up
# to a truncated-digest collision: two *different* payloads sharing a prefix
# would map to one filename, and because a name that already exists is not
# rewritten, the second payload would silently load back as the first.  The
# birthday bound puts even odds at ~2**32 distinct blobs in a single cache dir,
# which no benchmark cache approaches, so the risk is accepted rather than
# mitigated -- raise this constant (new blobs simply get longer names; existing
# ones stay loadable, since load_blob dispatches on extension, not name length)
# if a cache ever grows near that scale.
_HASH_CHARS = 16

# Subdirectory of the cache dir that holds all blobs.  Cache tooling knows this
# folder as a content-addressed store (``cache_management._CONTENT_FOLDERS``):
# it is counted in cache stats and cleared wholesale, but never pruned per job
# key, since one deduplicated blob may back cells from many different jobs.
_BLOBS_SUBDIR = "blobs"

# The cache dir every caller means when it does not say otherwise: the same
# literal root the rest of collection uses (``gen_path``, ``cachedir/rrd``, the
# diskcaches), resolved against the process working directory.
DEFAULT_CACHE_DIR = "cachedir"

# Dataset attribute recording the cache dir a result's blobs were written to.
# It travels with ``BenchResult.ds`` through pickling and through ``to()``/
# ``from_existing()`` (both of which carry ``ds`` across), so a render process
# with a different working directory than the sweep can still find the blobs.
# See :func:`resolve_blob` for where it sits in the resolution order.
BLOB_CACHE_DIR_ATTR = "blob_cache_dir"

# Dtypes the scipy netCDF3 engine round-trips *exactly* — same dtype, same
# values, for every value of the type — determined empirically against this
# environment's only netCDF backend:
#
# - float32/float64, int8/int16/int32, bool: preserved exactly (whitelisted);
# - float16, complex64/128: raise ("NetCDF 3 does not support type ...");
# - int64 and every unsigned int: silently *narrowed* (int64→int32, uint8→int8,
#   ...) when the values happen to fit and raise ("could not safely cast")
#   when they do not — value-dependent, so excluded;
# - str (<U*): loads back as object dtype (values equal, dtype changed);
# - object: serializable only for all-str contents, raises otherwise;
# - datetime64[ns]/timedelta64[ns]: raise for values whose encoding does not
#   fit int32 (e.g. pre-1677 dates), so also value-dependent.
_NETCDF3_SAFE_DTYPES = frozenset(
    np.dtype(name) for name in ("float32", "float64", "int8", "int16", "int32", "bool")
)


def _netcdf3_unsafe_vars(obj: xr.Dataset | xr.DataArray) -> dict[str, str]:
    """Names → dtypes of every data var and coord netCDF3 cannot round-trip exactly."""
    if isinstance(obj, xr.Dataset):
        dtypes = {str(name): var.dtype for name, var in obj.variables.items()}
    else:
        dtypes = {str(obj.name) if obj.name is not None else "<unnamed>": obj.dtype}
        dtypes.update({str(name): coord.dtype for name, coord in obj.coords.items()})
    return {name: str(dtype) for name, dtype in dtypes.items() if dtype not in _NETCDF3_SAFE_DTYPES}


def _serialize(obj: Any) -> tuple[bytes, str]:
    """Serialize *obj* to bytes, returning ``(data, extension)``.

    The structured formats (parquet, netCDF) are attempted first; any payload
    they cannot represent *exactly* falls back to the pickle branch with a
    single warning, so collection never fails on an awkward payload and a
    loaded blob is always identical to what the worker stored.
    """
    if isinstance(obj, pd.DataFrame):
        try:
            # Requires a parquet engine (pyarrow is a bencher dependency).
            buffer = io.BytesIO()
            obj.to_parquet(buffer)
            return buffer.getvalue(), ".parquet"
        except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
            logger.warning(
                "blob_store: DataFrame payload could not be serialized to parquet "
                "(%s: %s); falling back to pickle",
                type(exc).__name__,
                exc,
            )
    elif isinstance(obj, (xr.Dataset, xr.DataArray)):
        # A DataArray gets its own suffix so load_blob can hand back a DataArray
        # (to_netcdf/load_dataarray is xarray's own convention, which also
        # covers unnamed arrays).
        extension = ".da.nc" if isinstance(obj, xr.DataArray) else ".nc"
        unsafe = _netcdf3_unsafe_vars(obj)
        if unsafe:
            logger.warning(
                "blob_store: %s payload has dtypes the scipy netCDF3 engine cannot "
                "round-trip exactly (%s); falling back to pickle",
                type(obj).__name__,
                ", ".join(f"{name}: {dtype}" for name, dtype in unsafe.items()),
            )
        else:
            try:
                # to_netcdf() with no target returns the serialized bytes
                # (memoryview on newer xarray versions).
                return bytes(obj.to_netcdf()), extension
            except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
                logger.warning(
                    "blob_store: %s payload could not be serialized to netCDF "
                    "(%s: %s); falling back to pickle",
                    type(obj).__name__,
                    type(exc).__name__,
                    exc,
                )
    if isinstance(obj, bytes):
        return obj, ".bin"
    # Pickle fallback — the surface plan A3 wants gone (see module docstring).
    return pickle.dumps(obj), ".pkl"


def _load_bytes(path: Path) -> bytes:
    return path.read_bytes()


def _load_pickle(path: Path) -> Any:
    return pickle.loads(path.read_bytes())


@dataclass(frozen=True)
class _BlobFormat:
    """One blob extension and the function that reads it back."""

    suffix: str
    load: Callable[[Path], Any]


# The one place a blob extension is written down.  ``blob_name``'s pattern, the
# suffix prefilter and ``load_blob``'s dispatch are all derived from this table,
# so adding a format is a single entry and cannot be half-added — the previous
# shape repeated the extension list in a prefilter tuple, a regex, an if-chain
# and an error message, and needed an "unreachable" raise to guard the drift
# between them.
#
# Longest suffix first, so ``.da.nc`` is matched before ``.nc``: a DataArray blob
# must load back as a DataArray, not as a single-variable Dataset (F4).
_BLOB_FORMATS: tuple[_BlobFormat, ...] = tuple(
    sorted(
        (
            _BlobFormat(".parquet", pd.read_parquet),
            # load_dataset/load_dataarray read eagerly and close the underlying
            # file handle, unlike open_* which keep it lazily open.
            _BlobFormat(".da.nc", xr.load_dataarray),
            _BlobFormat(".nc", xr.load_dataset),
            _BlobFormat(".bin", _load_bytes),
            _BlobFormat(".pkl", _load_pickle),
        ),
        key=lambda fmt: -len(fmt.suffix),
    )
)

_BLOB_SUFFIXES = tuple(fmt.suffix for fmt in _BLOB_FORMATS)

# A blob filename is a truncated sha256 in lowercase hex plus one of the format
# extensions.  The digest length is deliberately unpinned so ``_HASH_CHARS`` can
# be raised without invalidating existing blobs.
_BLOB_NAME_RE = re.compile(
    r"^[0-9a-f]+(?:" + "|".join(re.escape(fmt.suffix) for fmt in _BLOB_FORMATS) + r")$"
)


def _parse_blob_ref(value: str) -> tuple[str, _BlobFormat] | None:
    """The ``(name, format)`` *value* refers to, or None when it is not a blob ref.

    Parsing once, here, is what keeps :func:`load_blob` total: the format comes
    out of the same match that accepted the name, so there is no second dispatch
    that could fail to recognise a name this predicate already approved.
    """
    if not value.endswith(_BLOB_SUFFIXES):
        return None
    name = Path(value).name
    if not _BLOB_NAME_RE.match(name):
        return None
    # First match wins and the table is longest-suffix-first, so ``.da.nc``
    # cannot be read as ``.nc``.
    return name, next(fmt for fmt in _BLOB_FORMATS if name.endswith(fmt.suffix))


def blob_name(value: str) -> str | None:
    """The blob filename *value* names, or None when it is not a blob reference.

    Accepts both cell generations: a bare blob name (what collection stores now)
    and a path ending in one (what it stored before, and what a hand-written
    caller may still pass).  Matching is on the **basename**, because a blob's
    name *is* its content hash and so is a complete, location-independent
    identity — the directory a cell happens to carry says only where some past
    process kept its cache dir.

    This is the single predicate for "is this string a blob reference", shared by
    resolution here and by reachability GC in ``cache_management`` so the two can
    never disagree about what counts as one.
    """
    parsed = _parse_blob_ref(value)
    return None if parsed is None else parsed[0]


def _blob_candidates(
    name: str,
    text: str,
    cache_dir: str | Path,
    fallback_cache_dirs: Iterable[str | Path],
) -> list[Path]:
    """Every location *name* might live in, in the order they should be tried."""
    dirs = [cache_dir, *fallback_cache_dirs]
    candidates = [Path(directory) / _BLOBS_SUBDIR / name for directory in dirs]
    # Path(text) == Path(name) exactly when the cell is a bare name, in which
    # case it carries no location of its own to try.
    if Path(text) != Path(name):
        candidates.append(Path(text))
    # Dedupe while keeping order: a legacy cell that points into the active cache
    # dir would otherwise be listed twice, including in the failure message.
    return list(dict.fromkeys(candidates))


def _locate_blob(
    name: str,
    text: str,
    cache_dir: str | Path,
    fallback_cache_dirs: Iterable[str | Path],
) -> Path:
    """The first candidate location holding *name*, or FileNotFoundError."""
    candidates = _blob_candidates(name, text, cache_dir, fallback_cache_dirs)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    tried = ", ".join(repr(str(candidate)) for candidate in candidates)
    raise FileNotFoundError(
        f"blob store: no readable file for blob {name!r} (tried {tried}). "
        "The blob store holds primary storage, not a recomputable cache, so a "
        "missing blob is either a cache dir restored without its blobs/ folder "
        "or a clean_orphaned_blobs run that could not see this reference."
    )


def _parse_or_raise(text: str, caller: str) -> tuple[str, _BlobFormat]:
    """*text* as a ``(name, format)`` pair, or ValueError naming what was expected."""
    parsed = _parse_blob_ref(text)
    if parsed is None:
        raise ValueError(
            f"{caller}: {text!r} is not a blob reference; expected a "
            f"content-hash name ending in one of {', '.join(_BLOB_SUFFIXES)}"
        )
    return parsed


def resolve_blob(
    cell: str | Path,
    cache_dir: str | Path = DEFAULT_CACHE_DIR,
    *,
    fallback_cache_dirs: Iterable[str | Path] = (),
) -> Path:
    """Locate the blob file a dataset *cell* refers to.

    Three locations are tried, in this order:

    1. the active *cache_dir* — first, because that is what makes a relocated
       cache render.  Content addressing means every candidate holds identical
       bytes when several exist, so preferring the active cache dir costs nothing
       and stops a stale directory that happens to still exist (another checkout,
       a previous CI workspace) from shadowing the cache actually in use;
    2. each of *fallback_cache_dirs* — the cache dir the result recorded at
       collect time (``BLOB_CACHE_DIR_ATTR``).  This is what keeps a result
       renderable from a *different working directory* than the sweep ran in,
       which the documented collect/render split (``bencher result.pkl out/``)
       does by default.  Without it a bare-name cell would be resolvable only
       from the sweep's own cwd — trading the relocation failure for a cwd one;
    3. the cell's own literal path, for a cell collected before names became the
       cell format.

    Raises
    ------
    ValueError
        If *cell* is not a blob reference at all.
    FileNotFoundError
        If it is one but names no readable file, listing every location tried so
        the message says where to look rather than only that it failed.
    """
    text = str(cell)
    name, _ = _parse_or_raise(text, "resolve_blob")
    return _locate_blob(name, text, cache_dir, fallback_cache_dirs)


def collect_cache_dir() -> Path:
    """The cache dir collection writes blobs to: ``<cwd>/cachedir``, absolutised.

    Absolute rather than relative because it is also what gets recorded on the
    dataset (:func:`record_blob_cache_dir`), and a hint is only useful to a
    process whose working directory may differ from the one that wrote it.
    """
    return Path(DEFAULT_CACHE_DIR).absolute()


def record_blob_cache_dir(dataset: xr.Dataset, cache_dir: str | Path) -> None:
    """Record on *dataset* that its blob cells were written under *cache_dir*.

    One attribute for the whole dataset, not a directory per cell: the cell keeps
    the location-independent name, and this is a resolution *hint* for a reader
    whose own working directory is elsewhere.  Re-stamped on every collect, so it
    always names the cache dir of the process that last wrote blobs here — a
    stale value costs nothing, since the active cache dir is tried first.
    """
    dataset.attrs[BLOB_CACHE_DIR_ATTR] = str(cache_dir)


def blob_cache_dir_hints(dataset: xr.Dataset | None) -> tuple[str, ...]:
    """The recorded collect-time cache dir of *dataset*, as resolution fallbacks.

    Empty for a dataset collected before the attribute existed (or for no dataset
    at all), which resolves exactly as it did then.
    """
    recorded = getattr(dataset, "attrs", {}).get(BLOB_CACHE_DIR_ATTR)
    return (recorded,) if isinstance(recorded, str) and recorded else ()


def materialize_blob(obj: Any, cache_dir: str | Path) -> str:
    """Serialize *obj* under ``<cache_dir>/blobs/`` and return its blob name.

    The filename is the first 16 hex characters of the sha256 of the
    serialized bytes plus a format extension, so identical payloads map to
    identical paths (content addressing) and are written only once.

    A content hit (the blob already exists) does not rewrite the file, but it
    **does** refresh the file's mtime: a hit is a *new reference* to the
    payload, and ``cache_management.clean_orphaned_blobs`` uses mtime as its
    ``min_age_seconds`` grace-period signal.  A blob's mtime therefore means
    "last referenced", not "created" — which is what makes an age-based grace
    period a sound guard for a sweep that deduplicates onto an old blob, not
    just for one that writes a new one.

    A str/Path payload is pickled like any other object — even when it names
    an existing file — so loading the blob returns exactly what the worker
    stored and every blob lives under *cache_dir*.

    Parameters
    ----------
    obj:
        The payload to materialize.  See the module docstring for the
        type → format dispatch table.
    cache_dir:
        Root cache directory; blobs live in its ``blobs/`` subdirectory,
        which is created if needed.

    Returns
    -------
    str
        The blob's filename, which is what a dataset cell stores.  Join it onto
        ``<cache_dir>/blobs/`` for a path, or let :func:`resolve_blob` do it —
        see the module docstring for why the name travels and a path must not.
    """
    data, extension = _serialize(obj)
    digest = hashlib.sha256(data).hexdigest()[:_HASH_CHARS]

    blobs_dir = Path(cache_dir) / _BLOBS_SUBDIR
    blobs_dir.mkdir(parents=True, exist_ok=True)
    blob_path = blobs_dir / f"{digest}{extension}"

    if blob_path.exists():
        try:
            # A content hit is a new reference to this payload.  Refresh mtime
            # (never the bytes) so it reads as "last referenced" and an
            # age-based GC grace period protects the blob a concurrent sweep
            # just deduplicated onto, exactly as it protects one just written.
            os.utime(blob_path)
            return blob_path.name
        except OSError:
            # The blob vanished between the existence check and the touch
            # (e.g. a concurrent GC collected it): fall through and rewrite.
            pass

    # Write via a unique temp file + atomic rename so concurrent workers
    # materializing the same payload never observe a partial blob.
    tmp_path = blob_path.with_suffix(blob_path.suffix + f".tmp-{uuid.uuid4().hex}")
    tmp_path.write_bytes(data)
    tmp_path.replace(blob_path)

    return blob_path.name


def load_blob(
    path: str | Path,
    cache_dir: str | Path = DEFAULT_CACHE_DIR,
    *,
    fallback_cache_dirs: Iterable[str | Path] = (),
) -> Any:
    """Load a blob written by :func:`materialize_blob`, dispatching on extension.

    - ``.parquet`` → ``pandas.DataFrame``
    - ``.da.nc`` → ``xarray.DataArray`` (``name`` preserved, unnamed arrays
      included, via xarray's own DataArray netCDF convention)
    - ``.nc`` → ``xarray.Dataset`` (fully loaded into memory; the file handle
      is closed so the blob stays re-readable)
    - ``.bin`` → ``bytes``
    - ``.pkl`` → the unpickled object

    *path* is a blob name or any path ending in one; :func:`resolve_blob` turns it
    into a file against *cache_dir* and *fallback_cache_dirs*, so a cell collected
    under one cache dir location loads under another.

    The extension is matched once, by the same parse that accepts the name, so
    there is no second dispatch here that could fail on a name already approved
    as a blob reference.

    Raises
    ------
    ValueError
        If *path* is not a blob reference.
    FileNotFoundError
        If it names no readable file in any location tried.
    """
    text = str(path)
    name, blob_format = _parse_or_raise(text, "load_blob")
    return blob_format.load(_locate_blob(name, text, cache_dir, fallback_cache_dirs))
