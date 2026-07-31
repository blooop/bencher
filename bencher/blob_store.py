"""Content-addressed blob store for materializing result payloads at collect time.

This module implements design D1 of the grammar phase-1 data model
(plans/22-grammar-phase-1-data-model.md, A6 Law 1): result payloads that
cannot live directly in a dataset cell are serialized under
``<cache_dir>/blobs/`` and the cell stores the returned **path string**
instead of a run-local index.  Filenames are derived from the sha256 of the
serialized bytes, so identical payloads across repeats and time points
deduplicate to a single file for free.

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
import pickle
import uuid
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


def materialize_blob(obj: Any, cache_dir: str | Path) -> str:
    """Serialize *obj* under ``<cache_dir>/blobs/`` and return the file path.

    The filename is the first 16 hex characters of the sha256 of the
    serialized bytes plus a format extension, so identical payloads map to
    identical paths (content addressing) and are written only once.

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
        Path to the blob file.
    """
    data, extension = _serialize(obj)
    digest = hashlib.sha256(data).hexdigest()[:_HASH_CHARS]

    blobs_dir = Path(cache_dir) / _BLOBS_SUBDIR
    blobs_dir.mkdir(parents=True, exist_ok=True)
    blob_path = blobs_dir / f"{digest}{extension}"

    if not blob_path.exists():
        # Write via a unique temp file + atomic rename so concurrent workers
        # materializing the same payload never observe a partial blob.
        tmp_path = blob_path.with_suffix(blob_path.suffix + f".tmp-{uuid.uuid4().hex}")
        tmp_path.write_bytes(data)
        tmp_path.replace(blob_path)

    return str(blob_path)


def load_blob(path: str | Path) -> Any:
    """Load a blob written by :func:`materialize_blob`, dispatching on extension.

    - ``.parquet`` → ``pandas.DataFrame``
    - ``.da.nc`` → ``xarray.DataArray`` (``name`` preserved, unnamed arrays
      included, via xarray's own DataArray netCDF convention)
    - ``.nc`` → ``xarray.Dataset`` (fully loaded into memory; the file handle
      is closed so the blob stays re-readable)
    - ``.bin`` → ``bytes``
    - ``.pkl`` → the unpickled object

    Raises
    ------
    ValueError
        If the extension is not one of the known blob formats.
    """
    blob_path = Path(path)
    # .da.nc must be checked before the plain .nc suffix dispatch below.
    if blob_path.name.endswith(".da.nc"):
        # load_dataarray reads eagerly, like load_dataset below.
        return xr.load_dataarray(blob_path)
    extension = blob_path.suffix
    if extension == ".parquet":
        return pd.read_parquet(blob_path)
    if extension == ".nc":
        # load_dataset reads eagerly and closes the underlying file handle,
        # unlike open_dataset which keeps it lazily open.
        return xr.load_dataset(blob_path)
    if extension == ".bin":
        return blob_path.read_bytes()
    if extension == ".pkl":
        return pickle.loads(blob_path.read_bytes())
    raise ValueError(
        f"load_blob: unknown blob extension {extension!r} for {blob_path}; "
        "expected one of .parquet, .da.nc, .nc, .bin, .pkl"
    )
