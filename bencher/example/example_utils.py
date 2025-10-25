"""Internal utilities for examples and documentation generation."""

from pathlib import Path


def resolve_example_path(filename: str) -> Path:
    """Locate example assets when running as a script, notebook, or installed package."""
    import bencher as bch

    module_file = globals().get("__file__")
    search_roots = []
    if module_file:
        search_roots.append(Path(module_file).resolve().parent)

    search_roots.append(Path.cwd())
    search_roots.append(Path(bch.__file__).resolve().parent / "example")

    for root in search_roots:
        candidate = Path(root) / filename
        if candidate.exists():
            return candidate

    searched = ", ".join(str(Path(root)) for root in search_roots)
    raise FileNotFoundError(f"Unable to locate {filename}. Searched: {searched}")
