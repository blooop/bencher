"""Content-addressed blob store for materializing result payloads at collect time.

This module implements design D1 of the grammar phase-1 data model
(plans/22-grammar-phase-1-data-model.md, A6 Law 1): result payloads that
cannot live directly in a dataset cell are serialized under
``<cache_dir>/blobs/`` and the cell stores the returned **path string**
instead of a run-local index.  Filenames are derived from the sha256 of the
serialized bytes, so identical payloads across repeats and time points
deduplicate to a single file for free.

Supported formats, dispatched on the payload type:

- ``pandas.DataFrame`` → ``.parquet``
- ``xarray.Dataset`` / ``xarray.DataArray`` → ``.nc`` (netCDF; a DataArray
  loads back as a single-variable Dataset)
- ``bytes`` → ``.bin`` (raw)
- an existing file path (str/Path) → returned unchanged, never copied
- anything else picklable → ``.pkl``

.. warning::
    The ``.pkl`` fallback is the pickle surface that architecture plan A3
    wants gone.  It exists only because ``ResultDataSet`` documents its
    payload as "any picklable object"; the A3 migration should tighten this
    to the structured formats above with its own deprecation story.
"""

import hashlib
import pickle
import uuid
from pathlib import Path
from typing import Any

import pandas as pd
import xarray as xr

# Number of hex characters of the sha256 digest used in blob filenames.
_HASH_CHARS = 16

# Subdirectory of the cache dir that holds all blobs.
_BLOBS_SUBDIR = "blobs"


def _serialize(obj: Any) -> tuple[bytes, str]:
    """Serialize *obj* to bytes, returning ``(data, extension)``."""
    if isinstance(obj, pd.DataFrame):
        # Requires a parquet engine (pyarrow is a bencher dependency).
        import io  # pylint: disable=import-outside-toplevel

        buffer = io.BytesIO()
        obj.to_parquet(buffer)
        return buffer.getvalue(), ".parquet"
    if isinstance(obj, (xr.Dataset, xr.DataArray)):
        # to_netcdf() with no target returns the serialized bytes
        # (memoryview on newer xarray versions).
        return bytes(obj.to_netcdf()), ".nc"
    if isinstance(obj, bytes):
        return obj, ".bin"
    # Pickle fallback — the surface plan A3 wants gone (see module docstring).
    return pickle.dumps(obj), ".pkl"


def materialize_blob(obj: Any, cache_dir: str | Path) -> str:
    """Serialize *obj* under ``<cache_dir>/blobs/`` and return the file path.

    The filename is the first 16 hex characters of the sha256 of the
    serialized bytes plus a format extension, so identical payloads map to
    identical paths (content addressing) and are written only once.

    If *obj* is a str/Path pointing at an existing file, it is treated as an
    already-materialized blob and returned unchanged as ``str``.

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
        Path to the blob file (or the input path itself for path-like input).
    """
    if isinstance(obj, (str, Path)) and Path(obj).is_file():
        return str(obj)

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
        "expected one of .parquet, .nc, .bin, .pkl"
    )
