import pandas as pd
from typing import Union, Optional
import marimo as mo
import json


def _infer_dtype(value) -> str:
    """Infer a pandas-compatible dtype string from a template value.

    Handles both type-name strings (e.g. ``"string"``, ``"boolean"``) and
    actual Python values (e.g. ``True``, ``42``, ``3.14``).
    """
    # Map explicit type-name strings
    _type_name_map = {
        "string": "str",
        "str": "str",
        "number": "float64",
        "float": "float64",
        "float64": "float64",
        "float32": "float32",
        "integer": "int64",
        "int": "int64",
        "int64": "int64",
        "int32": "int32",
        "boolean": "bool",
        "bool": "bool",
    }
    if isinstance(value, str) and value.strip().lower() in _type_name_map:
        return _type_name_map[value.strip().lower()]

    # Infer from actual Python type
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int64"
    if isinstance(value, float):
        return "float64"

    # Default to str
    return "str"


def _resolve_oneof(schema: dict, variant_index: int = 0) -> dict:
    """Resolve a ``oneOf`` schema node into columns.

    Supports two variant shapes:
    - ``{"type": "array", "items": <dtype>}`` → ``{"value": <dtype>}``
    - ``{"type": "object", "additionalProperties": <dtype>}`` →
      ``{"key": "str", "value": <dtype>}``

    Args:
        schema: A dict containing a ``"oneOf"`` key with a list of variants.
        variant_index: Which variant to select (0-based).

    Returns:
        A ``{column_name: dtype_string}`` mapping for the chosen variant.
    """
    variants = schema.get("oneOf", [])
    if not variants:
        return {}
    variant = variants[max(0, min(variant_index, len(variants) - 1))]
    vtype = variant.get("type", "")
    if vtype == "array":
        item_type = variant.get("items", "string")
        return {"value": _infer_dtype(item_type)}
    if vtype == "object":
        val_type = variant.get("additionalProperties", "string")
        return {"key": "str", "value": _infer_dtype(val_type)}
    return {}


def columns_from_template(
    template: Union[str, dict],
    context_key: str = "org_context",
    target_key: str = "terminology_mapping",
    variant_index: int = 0,
) -> dict:
    """Extract column names and dtypes from a JSON structure template.

    Inspects the value under ``template[context_key][target_key]``
    and derives a ``{column_name: dtype_string}`` mapping suitable for
    ``marimo_create_data_editor_df(columns=...)``.

    Supports ``oneOf`` schema nodes (e.g. ``offerings``). Use
    *variant_index* to choose which variant to materialise.

    Args:
        template: Either a file path (str) to a JSON file or an
            already-loaded dict.
        context_key: Top-level key that wraps the context data
            (e.g. ``"org_context"``).
        target_key: The nested key whose structure defines the columns
            (e.g. ``"terminology_mapping"``, ``"taxonomy"``).
        variant_index: When the target value is a ``oneOf`` schema,
            selects which variant to use (0-based, default ``0``).

    Returns:
        A dict mapping column names to pandas-compatible dtype strings.
        For a list-of-dicts structure like
        ``[{"original": "string", "replacement": "string"}]`` returns
        ``{"original": "str", "replacement": "str"}``.
        For a flat list like ``["string", "string"]`` returns
        ``{"value": "str"}``.
        For a ``oneOf`` with ``{"type": "array", "items": "string"}``
        returns ``{"value": "str"}``.
        For a ``oneOf`` with ``{"type": "object", "additionalProperties": "string"}``
        returns ``{"key": "str", "value": "str"}``.
        Returns an empty dict if the target key is missing or empty.
    """
    if isinstance(template, str):
        with open(template) as f:
            template = json.load(f)

    items = template.get(context_key, {}).get(target_key, [])
    if not items:
        return {}

    # Handle oneOf schema nodes
    if isinstance(items, dict) and "oneOf" in items:
        return _resolve_oneof(items, variant_index)

    sample = items[0]
    if isinstance(sample, dict):
        return {k: _infer_dtype(v) for k, v in sample.items()}

    return {"value": _infer_dtype(sample)}


def marimo_autorefresh(
    interval: Union[int, float, str] = "5s",
    *,
    mo=mo,
):
    """Create a hidden auto-refresh ticker that periodically re-runs a cell.

    Marimo does not allow reading ``ui.refresh.value`` in the same cell that
    creates the widget.  This helper works around that constraint via
    ``mo.state``: an ``on_change`` callback increments a state counter each
    time the ticker fires, and reading the state getter in a *separate* cell
    is what triggers that cell to re-run.

    **Two-cell usage (required by marimo's reactive model)**::

        # ── Cell 1 ──────────────────────────────────────────────────────────
        ticker, get_tick = marimo_autorefresh("10s", mo=mo)
        # Nothing else needed here; ticker is already hidden.

        # ── Cell 2 ──────────────────────────────────────────────────────────
        get_tick()          # reading this re-runs the cell every 10 s
        # your polling / display logic here …

    ``get_tick()`` returns the cumulative fire count (0 on first run, 1 after
    the first interval, etc.).  You can use it to skip work on the initial
    render::

        count = get_tick()
        if count == 0:
            mo.stop(True, "waiting for first tick…")

    Args:
        interval: Refresh cadence.  Accepts the same formats as
            ``mo.ui.refresh``: a number in seconds (``int`` or ``float``) or a
            human-readable string such as ``"5s"``, ``"1m"``, ``"1m 30s"``.
            Defaults to ``"5s"``.
        mo: The ``marimo`` module injected into every notebook cell.  Must be
            passed explicitly because it is not importable outside the marimo
            runtime.

    Returns:
        A ``(ticker, get_tick)`` tuple where *ticker* is the hidden
        ``mo.ui.refresh`` widget (already appended to cell output as an
        invisible element) and *get_tick* is the ``mo.state`` getter whose
        value increments on every refresh fire.

    Raises:
        ValueError: If *mo* is not provided.
    """
    if mo is None:
        raise ValueError(
            "marimo_autorefresh() requires the marimo module: pass `mo=mo`."
        )

    get_tick, set_tick = mo.state(0)

    ticker = mo.ui.refresh(
        default_interval=interval,
        on_change=lambda _: set_tick(lambda n: n + 1),
    )

    # Append the widget as an invisible element so marimo registers it as a
    # reactive dependency of this cell without showing anything to the user.
    mo.output.append(
        mo.Html(
            '<div style="display:none;height:0;overflow:hidden" '
            f'aria-hidden="true">{ticker}</div>'
        )
    )

    return ticker, get_tick


def marimo_create_data_editor_df(
    num_rows: int,
    columns: Union[list, dict],
    fill_value: str = "",
) -> pd.DataFrame:
    """Create a DataFrame with empty rows and specified columns.

    Useful for dynamically initialising ``mo.ui.data_editor`` widgets where
    the number of rows is driven by a ``mo.ui.number`` input.

    Args:
        num_rows: Number of empty rows to create. Values <= 0 return a
            zero-row DataFrame with the requested columns.
        columns: Column specification. Accepts either:
            - A **list of column names** (all columns default to ``str``).
            - A **dict** mapping column names to pandas-compatible dtype
            strings (e.g. ``{"age": "int64", "name": "str"}``).
        fill_value: Default cell value used when *columns* is a list.
            Defaults to ``""`` (empty string).

    Returns:
        A ``pd.DataFrame`` with the requested shape and dtypes.
    """
    num_rows = max(int(num_rows), 0)

    if isinstance(columns, list):
        data = {col: [fill_value] * num_rows for col in columns}
        return pd.DataFrame(data)

    # dict path: respect requested dtypes
    data = {}
    for col, dtype in columns.items():
        dtype_str = str(dtype).lower()
        if dtype_str in ("int", "int64", "int32"):
            data[col] = pd.array([0] * num_rows, dtype=dtype)
        elif dtype_str in ("float", "float64", "float32"):
            data[col] = pd.array([0.0] * num_rows, dtype=dtype)
        elif dtype_str in ("bool",):
            data[col] = pd.array([False] * num_rows, dtype="bool")
        else:
            data[col] = pd.array([fill_value] * num_rows, dtype="str")
    return pd.DataFrame(data)
