"""Client-side helpers for calling the deployable data validators.

These helpers are the counterpart to the two deployable watsonx.ai functions
in this repo:

  - ``deployable_functions/deployable_data_validator_api/data_validator.py``
    validates a data payload against a JSON Schema. Its score function accepts
    the fields ``data, schema, key_mapping, strip_unknown, verbose,
    env_overrides`` and returns ``validation_result``.

  - ``deployable_functions/deployable_data_validator_library/data_validator_library.py``
    validates a config dict against the *call signature* of an arbitrary Python
    callable. Its score function accepts the fields ``target, config,
    type_mapping, call_target, verbose, env_overrides`` and returns
    ``validation_result``.

Both functions speak the standard watsonx.ai scoring envelope (``input_data``
-> ``predictions``). The helpers here build that envelope and unpack the
``validation_result`` (plus optional ``debug_logs`` when ``verbose=True``) in
one of two interchangeable modes:

  - ``mode="remote"`` authenticates via IAM and POSTs to the deployment's
    ``/predictions`` endpoint.
  - ``mode="local"`` loads the validator's source file and calls its
    module-level ``score`` callable in-process, with no network round-trip -
    handy for development, offline use, or testing without a live deployment.
  - ``mode="auto"`` (the default) uses remote when both an ``endpoint_url`` and
    ``api_key`` are supplied, and falls back to local otherwise.

Because both modes share the identical scoring envelope, the return shape is
the same either way. The helpers are deliberately generic and carry no
survey/widget-specific assumptions, matching the design of the deployable
functions they call.
"""

from __future__ import annotations

import importlib.util
import json
import os
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import certifi
import requests

DEFAULT_IAM_TOKEN_URL = "https://iam.cloud.ibm.com/identity/token"
DEFAULT_API_VERSION = "2021-05-01"

# Default locations of the deployable validator source files, resolved relative
# to the repo root (this file lives at <root>/src/helpers/). Used by local mode
# to load each function's `score` callable directly, with no network round-trip.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_LOCAL_VALIDATOR_PATHS: Dict[str, str] = {
    "api": os.path.join(
        _REPO_ROOT,
        "deployable_functions",
        "deployable_data_validator_api",
        "data_validator.py",
    ),
    "library": os.path.join(
        _REPO_ROOT,
        "deployable_functions",
        "deployable_data_validator_library",
        "data_validator_library.py",
    ),
}

# Simple process-local cache of IAM tokens keyed by api_key. watsonx.ai IAM
# tokens are valid for ~1h; we refresh a little early to stay safe.
_TOKEN_CACHE: Dict[str, Tuple[str, float]] = {}
_TOKEN_TTL_SECONDS = 50 * 60

# Cache of locally loaded `score` callables keyed by absolute source path, so a
# notebook validating many configs only imports each validator module once.
_LOCAL_SCORE_CACHE: Dict[str, Callable[[dict], dict]] = {}


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
def _get_iam_token(
    api_key: str,
    iam_token_url: str = DEFAULT_IAM_TOKEN_URL,
    use_cache: bool = True,
) -> str:
    """Obtain (and optionally cache) an IBM Cloud IAM access token.

    Args:
        api_key: IBM Cloud API key.
        iam_token_url: IAM token endpoint. Defaults to the public IBM Cloud URL.
        use_cache: If ``True`` reuse a recently issued token for the same key.

    Returns:
        The bearer access token string.

    Raises:
        requests.HTTPError: If the token request fails.
    """
    if use_cache:
        cached = _TOKEN_CACHE.get(api_key)
        if cached and (time.time() - cached[1]) < _TOKEN_TTL_SECONDS:
            return cached[0]

    response = requests.post(
        iam_token_url,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
            "apikey": api_key,
        },
        verify=certifi.where(),
    )
    response.raise_for_status()
    token = response.json()["access_token"]

    if use_cache:
        _TOKEN_CACHE[api_key] = (token, time.time())
    return token


# ---------------------------------------------------------------------------
# Ordering / parsing helpers
# ---------------------------------------------------------------------------
def _restore_order(value: Any, original: Any) -> Any:
    """Recursively reorder dicts/lists in *value* to match *original*'s keys.

    The watsonx.ai serving layer may serialize dictionaries with sorted keys.
    This restores the key order found in *original* while preserving any extra
    keys that appear only in *value*. Lists are only reordered element-wise
    when lengths match and elements are dicts; otherwise they are returned
    as-is to avoid silently mismatching items the validator added or removed.
    """
    if isinstance(value, dict) and isinstance(original, dict):
        reordered: Dict[Any, Any] = {}
        for key in original:
            if key in value:
                reordered[key] = _restore_order(value[key], original[key])
        for key in value:
            if key not in reordered:
                reordered[key] = value[key]
        return reordered
    if isinstance(value, list) and isinstance(original, list):
        if len(value) == len(original) and all(
            isinstance(v, dict) and isinstance(o, dict) for v, o in zip(value, original)
        ):
            return [_restore_order(v, original[i]) for i, v in enumerate(value)]
        return value
    return value


def _load_schema(schema: Union[str, dict, list, None]) -> Union[dict, list, str, None]:
    """Load a JSON Schema from a file path when a path-like string is given.

    Accepts an already-parsed dict/list (returned unchanged), ``None``
    (returned unchanged), or a string. A string ending in ``.json`` is treated
    as a file path and loaded; any other string is passed through untouched so
    the endpoint can parse JSON/YAML/JS-literal schemas itself.
    """
    if schema is None or isinstance(schema, (dict, list)):
        return schema
    if isinstance(schema, str) and schema.strip().lower().endswith(".json"):
        with open(schema, encoding="utf-8-sig") as handle:
            return json.load(handle)
    return schema


def _build_scoring_payload(input_record: Dict[str, Any]) -> Dict[str, Any]:
    """Wrap a field->value mapping in the watsonx.ai ``input_data`` envelope.

    ``None``-valued optional fields are stripped so the deployed function falls
    back to its own defaults.
    """
    input_record = {k: v for k, v in input_record.items() if v is not None}
    fields = list(input_record.keys())
    values = [list(input_record.values())]
    return {"input_data": [{"fields": fields, "values": values}]}


def _unpack_prediction(
    result: Dict[str, Any],
    result_key: str,
    order_reference: Any = None,
) -> Dict[str, Any]:
    """Unpack a watsonx.ai ``predictions`` envelope into a flat result dict.

    Shared by remote (HTTP) and local (in-process) scoring, since both the
    deployed function and its local ``score`` callable return the identical
    envelope shape.

    Args:
        result: The raw ``{"predictions": [...]}`` mapping.
        result_key: Name of the prediction field to extract.
        order_reference: Optional original object to restore key order against.

    Returns:
        ``{result_key: <value>, "debug_logs": <list|None>, "error": <str|None>}``.

    Raises:
        ValueError: If the envelope cannot be parsed.
    """
    try:
        prediction = result["predictions"][0]
        output_fields = prediction["fields"]
        output_values = prediction["values"][0]
        parsed = dict(zip(output_fields, output_values))
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError(
            f"Unexpected validator response structure: {exc}\nRaw response: {result}"
        )

    # Both validators emit {"status": "error", "error": ...} on failure.
    if parsed.get("status") == "error":
        return {
            result_key: None,
            "debug_logs": parsed.get("debug_logs"),
            "error": parsed.get("error"),
        }

    validation_result = parsed.get(result_key, {})
    if (
        order_reference is not None
        and isinstance(validation_result, dict)
        and isinstance(order_reference, dict)
    ):
        validation_result = _restore_order(validation_result, order_reference)

    return {
        result_key: validation_result,
        "debug_logs": parsed.get("debug_logs"),
        "error": None,
    }


def _load_local_score(
    validator: str,
    local_path: Optional[str] = None,
    local_score: Optional[Callable[[dict], dict]] = None,
) -> Callable[[dict], dict]:
    """Resolve a local ``score`` callable for a validator, loading by file path.

    Args:
        validator: ``"api"`` or ``"library"``; selects the default source path.
        local_path: Optional explicit path to a validator source file. Overrides
            the default for *validator*.
        local_score: Optional already-loaded ``score`` callable. If given it is
            returned directly (no file loading).

    Returns:
        The module-level ``score`` callable from the chosen validator source.

    Raises:
        ValueError: If *validator* is unknown and no explicit source is given.
        FileNotFoundError: If the resolved source file does not exist.
        AttributeError: If the loaded module exposes no ``score`` callable.
    """
    if local_score is not None:
        return local_score

    path = local_path or DEFAULT_LOCAL_VALIDATOR_PATHS.get(validator)
    if not path:
        raise ValueError(
            f"No local source path for validator {validator!r}; pass local_path."
        )
    path = os.path.abspath(path)

    cached = _LOCAL_SCORE_CACHE.get(path)
    if cached is not None:
        return cached

    if not os.path.isfile(path):
        raise FileNotFoundError(f"Validator source not found: {path}")

    spec = importlib.util.spec_from_file_location(f"_local_validator_{validator}", path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Could not load validator module from: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    score = getattr(module, "score", None)
    if not callable(score):
        raise AttributeError(f"Validator module at {path} exposes no callable 'score'.")

    _LOCAL_SCORE_CACHE[path] = score
    return score


def _score_remote(
    endpoint_url: str,
    api_key: str,
    input_record: Dict[str, Any],
    result_key: str,
    order_reference: Any = None,
    iam_token_url: str = DEFAULT_IAM_TOKEN_URL,
    api_version: str = DEFAULT_API_VERSION,
    use_token_cache: bool = True,
) -> Dict[str, Any]:
    """Authenticate, score a deployed endpoint and unpack its prediction.

    Args:
        endpoint_url: Full deployment ``/predictions`` URL. A ``?version=``
            query parameter is appended if missing.
        api_key: IBM Cloud API key for IAM authentication.
        input_record: Field->value mapping to wrap in the scoring envelope.
        result_key: Name of the prediction field to return.
        order_reference: Optional original object used to restore key order.
        iam_token_url: IAM token endpoint.
        api_version: ``version`` query parameter for the scoring call.
        use_token_cache: Reuse cached IAM tokens when available.

    Returns:
        ``{result_key: <value>, "debug_logs": <list|None>, "error": <str|None>}``.

    Raises:
        requests.HTTPError: If the IAM or scoring request fails.
        ValueError: If the endpoint response cannot be parsed.
    """
    token = _get_iam_token(api_key, iam_token_url, use_cache=use_token_cache)

    scoring_url = endpoint_url
    if "?" not in scoring_url:
        scoring_url = f"{scoring_url}?version={api_version}"

    response = requests.post(
        scoring_url,
        json=_build_scoring_payload(input_record),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        verify=certifi.where(),
    )
    response.raise_for_status()
    return _unpack_prediction(response.json(), result_key, order_reference)


def _score_local(
    score: Callable[[dict], dict],
    input_record: Dict[str, Any],
    result_key: str,
    order_reference: Any = None,
) -> Dict[str, Any]:
    """Score a locally loaded validator ``score`` callable in-process.

    Builds the same ``input_data`` envelope used for remote scoring and unpacks
    the returned ``predictions`` envelope identically, so callers cannot tell
    the two modes apart from the result shape.

    Args:
        score: The validator's ``score`` callable.
        input_record: Field->value mapping to wrap in the scoring envelope.
        result_key: Name of the prediction field to return.
        order_reference: Optional original object used to restore key order.

    Returns:
        ``{result_key: <value>, "debug_logs": <list|None>, "error": <str|None>}``.

    Raises:
        ValueError: If the returned envelope cannot be parsed.
    """
    payload = _build_scoring_payload(input_record)
    return _unpack_prediction(score(payload), result_key, order_reference)


def _dispatch_validation(
    validator: str,
    input_record: Dict[str, Any],
    result_key: str,
    order_reference: Any,
    mode: str,
    endpoint_url: Optional[str],
    api_key: Optional[str],
    local_path: Optional[str],
    local_score: Optional[Callable[[dict], dict]],
    iam_token_url: str,
    api_version: str,
    use_token_cache: bool,
) -> Dict[str, Any]:
    """Route a validation request to remote or local scoring.

    Args:
        validator: ``"api"`` or ``"library"`` (selects the local default path).
        input_record: Field->value mapping for the scoring envelope.
        result_key: Prediction field to extract.
        order_reference: Original object for key-order restoration.
        mode: ``"remote"`` to call the deployed endpoint, ``"local"`` to run the
            validator's ``score`` in-process, or ``"auto"`` to prefer remote when
            an ``endpoint_url`` is supplied and fall back to local otherwise.
        endpoint_url: Deployment ``/predictions`` URL (required for remote).
        api_key: IBM Cloud API key (required for remote).
        local_path: Optional override path to the validator source file.
        local_score: Optional pre-loaded ``score`` callable for local mode.
        iam_token_url: IAM token endpoint (remote only).
        api_version: ``version`` query parameter (remote only).
        use_token_cache: Reuse cached IAM tokens (remote only).

    Returns:
        The unpacked result dict.

    Raises:
        ValueError: If *mode* is invalid, or remote mode lacks endpoint/api_key.
    """
    if mode not in ("remote", "local", "auto"):
        raise ValueError(
            f"Unknown mode {mode!r}; expected 'remote', 'local' or 'auto'."
        )

    if mode == "auto":
        mode = "remote" if (endpoint_url and api_key) else "local"

    if mode == "local":
        score = _load_local_score(validator, local_path, local_score)
        return _score_local(score, input_record, result_key, order_reference)

    if not endpoint_url or not api_key:
        raise ValueError("remote mode requires both 'endpoint_url' and 'api_key'.")
    return _score_remote(
        endpoint_url=endpoint_url,
        api_key=api_key,
        input_record=input_record,
        result_key=result_key,
        order_reference=order_reference,
        iam_token_url=iam_token_url,
        api_version=api_version,
        use_token_cache=use_token_cache,
    )


# ---------------------------------------------------------------------------
# Public API: JSON-Schema validator (data_validator)
# ---------------------------------------------------------------------------
def validate_data_via_endpoint(
    data: dict,
    endpoint_url: Optional[str] = None,
    api_key: Optional[str] = None,
    schema: Union[str, dict, list, None] = None,
    key_mapping: Optional[dict] = None,
    strip_unknown: bool = True,
    verbose: bool = False,
    env_overrides: Optional[dict] = None,
    mode: str = "auto",
    local_path: Optional[str] = None,
    local_score: Optional[Callable[[dict], dict]] = None,
    iam_token_url: str = DEFAULT_IAM_TOKEN_URL,
    api_version: str = DEFAULT_API_VERSION,
    use_token_cache: bool = True,
) -> Dict[str, Any]:
    """Validate a data payload against a JSON Schema (remote or local).

    Mirrors the ``data_validator`` deployable function's ``score`` contract:
    fields ``data, schema, key_mapping, strip_unknown, verbose, env_overrides``
    in, ``validation_result`` out. The same contract is used whether the
    validator runs as a deployed endpoint or in-process (local mode), so the
    return shape is identical either way.

    Args:
        data: The payload to validate (usually a dict).
        endpoint_url: Deployment ``/predictions`` URL (remote mode).
        api_key: IBM Cloud API key for IAM authentication (remote mode).
        schema: JSON Schema as a dict/list, a JSON/YAML/JS string, a path to a
            ``.json`` file, or ``None`` to use the validator's permissive default.
        key_mapping: Optional top-level key remapping applied before validation
            (e.g. ``{"open_ended": "openEnded"}``).
        strip_unknown: Drop properties not declared in the schema when
            ``additionalProperties`` is ``False`` (default ``True``).
        verbose: If ``True`` the validator returns per-step debug logs.
        env_overrides: Optional runtime environment overrides for the validator.
        mode: ``"remote"`` to call the deployed endpoint, ``"local"`` to run the
            ``data_validator`` source in-process, or ``"auto"`` (default) to use
            remote when ``endpoint_url`` and ``api_key`` are both supplied and
            fall back to local otherwise.
        local_path: Optional override path to the validator source file for local
            mode (defaults to the in-repo ``data_validator.py``).
        local_score: Optional pre-loaded ``score`` callable for local mode.
        iam_token_url: IAM token endpoint (remote mode).
        api_version: ``version`` query parameter for the scoring call (remote).
        use_token_cache: Reuse cached IAM tokens when available (remote mode).

    Returns:
        dict with keys:
            - ``validation_result`` (dict | None): normalized/validated data,
              or ``None`` if the validator reported an error.
            - ``debug_logs`` (list[str] | None): present when ``verbose=True``.
            - ``error`` (str | None): error message if validation failed.

    Raises:
        requests.HTTPError: If the IAM or scoring request fails (remote mode).
        ValueError: If the response cannot be parsed, or mode/arguments are
            invalid.
        FileNotFoundError: If the local validator source is missing (local mode).
    """
    input_record = {
        "data": data,
        "schema": _load_schema(schema),
        "key_mapping": key_mapping,
        # strip_unknown/verbose are real booleans; only None-valued fields are
        # stripped from the envelope so the validator uses its own defaults.
        "strip_unknown": strip_unknown,
        "verbose": verbose,
        "env_overrides": env_overrides,
    }

    return _dispatch_validation(
        validator="api",
        input_record=input_record,
        result_key="validation_result",
        order_reference=data,
        mode=mode,
        endpoint_url=endpoint_url,
        api_key=api_key,
        local_path=local_path,
        local_score=local_score,
        iam_token_url=iam_token_url,
        api_version=api_version,
        use_token_cache=use_token_cache,
    )


# ---------------------------------------------------------------------------
# Public API: library/signature validator (data_validator_library)
# ---------------------------------------------------------------------------
def validate_config_via_endpoint(
    target: str,
    config: dict,
    endpoint_url: Optional[str] = None,
    api_key: Optional[str] = None,
    type_mapping: Optional[dict] = None,
    call_target: bool = False,
    verbose: bool = False,
    env_overrides: Optional[dict] = None,
    mode: str = "auto",
    local_path: Optional[str] = None,
    local_score: Optional[Callable[[dict], dict]] = None,
    iam_token_url: str = DEFAULT_IAM_TOKEN_URL,
    api_version: str = DEFAULT_API_VERSION,
    use_token_cache: bool = True,
) -> Dict[str, Any]:
    """Validate a config against a Python callable's signature (remote or local).

    Mirrors the ``data_validator_library`` deployable function's ``score``
    contract: fields ``target, config, type_mapping, call_target, verbose,
    env_overrides`` in, ``validation_result`` out. The same contract is used
    whether the validator runs as a deployed endpoint or in-process (local
    mode), so the return shape is identical either way.

    Args:
        target: Dotted import path to a class/method/function (e.g.
            ``"collections.OrderedDict"``), or an alias key into
            ``type_mapping`` that resolves to one.
        config: Dict of keyword parameters to validate against the signature.
        endpoint_url: Deployment ``/predictions`` URL (remote mode).
        api_key: IBM Cloud API key for IAM authentication (remote mode).
        type_mapping: Optional dict carrying alias->path resolution and/or
            ``param_name -> "int"|"float"|"str"|"list"|"dict"|"bool"`` coercion
            hints.
        call_target: If ``True`` the validator instantiates/calls the target to
            confirm the params are accepted (default ``False``).
        verbose: If ``True`` the validator returns per-step debug logs.
        env_overrides: Optional runtime environment overrides for the validator.
        mode: ``"remote"`` to call the deployed endpoint, ``"local"`` to run the
            ``data_validator_library`` source in-process, or ``"auto"`` (default)
            to use remote when ``endpoint_url`` and ``api_key`` are both supplied
            and fall back to local otherwise.
        local_path: Optional override path to the validator source file for local
            mode (defaults to the in-repo ``data_validator_library.py``).
        local_score: Optional pre-loaded ``score`` callable for local mode.
        iam_token_url: IAM token endpoint (remote mode).
        api_version: ``version`` query parameter for the scoring call (remote).
        use_token_cache: Reuse cached IAM tokens when available (remote mode).

    Returns:
        dict with keys:
            - ``validation_result`` (dict | None): validated parameter set, or
              ``None`` if the validator reported an error.
            - ``debug_logs`` (list[str] | None): present when ``verbose=True``.
            - ``error`` (str | None): error message if validation failed.

    Raises:
        requests.HTTPError: If the IAM or scoring request fails (remote mode).
        ValueError: If the response cannot be parsed, or mode/arguments are
            invalid.
        FileNotFoundError: If the local validator source is missing (local mode).
    """
    input_record = {
        "target": target,
        "config": config,
        "type_mapping": type_mapping,
        "call_target": call_target,
        "verbose": verbose,
        "env_overrides": env_overrides,
    }

    return _dispatch_validation(
        validator="library",
        input_record=input_record,
        result_key="validation_result",
        order_reference=config,
        mode=mode,
        endpoint_url=endpoint_url,
        api_key=api_key,
        local_path=local_path,
        local_score=local_score,
        iam_token_url=iam_token_url,
        api_version=api_version,
        use_token_cache=use_token_cache,
    )


# ---------------------------------------------------------------------------
# Convenience: validate a batch of parsed configs from one model response
# ---------------------------------------------------------------------------
def validate_parsed_configs(
    configs: List[dict],
    endpoint_url: Optional[str] = None,
    api_key: Optional[str] = None,
    validator: str = "api",
    schema: Union[str, dict, list, None] = None,
    target: Optional[str] = None,
    key_mapping: Optional[dict] = None,
    type_mapping: Optional[dict] = None,
    strip_unknown: bool = True,
    call_target: bool = False,
    verbose: bool = False,
    mode: str = "auto",
    local_path: Optional[str] = None,
    local_score: Optional[Callable[[dict], dict]] = None,
    on_error: str = "passthrough",
    **endpoint_kwargs: Any,
) -> List[Dict[str, Any]]:
    """Validate a list of parsed configs against one of the validators.

    Convenience wrapper for the iterative-generation flow, where each model
    iteration parses to one or more config dicts that need validating before
    storage/render. Works in both remote and local modes (see *mode*).

    Args:
        configs: List of config/data dicts to validate.
        endpoint_url: Deployment ``/predictions`` URL (remote mode).
        api_key: IBM Cloud API key for IAM authentication (remote mode).
        validator: ``"api"`` (JSON-Schema validator) or ``"library"``
            (signature validator). Selects which validator contract is used.
        schema: JSON Schema (or path) for the ``"api"`` validator.
        target: Dotted import path / alias for the ``"library"`` validator.
        key_mapping: Top-level key remap for the ``"api"`` validator.
        type_mapping: Alias/coercion hints for the ``"library"`` validator.
        strip_unknown: ``strip_unknown`` flag for the ``"api"`` validator.
        call_target: ``call_target`` flag for the ``"library"`` validator.
        verbose: Request per-step debug logs from the validator.
        mode: ``"remote"``, ``"local"`` or ``"auto"`` (default). Forwarded to the
            underlying call; ``"auto"`` uses remote when an endpoint + api_key are
            given, else local.
        local_path: Optional override path to the validator source (local mode).
        local_score: Optional pre-loaded ``score`` callable (local mode). Reused
            across all *configs*, so a batch loads the module at most once.
        on_error: ``"passthrough"`` keeps the original config when an item
            fails to validate; ``"none"`` substitutes ``None``; ``"raise"``
            re-raises the exception.
        **endpoint_kwargs: Forwarded to the underlying call
            (e.g. ``iam_token_url``, ``api_version``, ``use_token_cache``).

    Returns:
        A list (parallel to *configs*) of per-config result dicts as returned
        by the underlying ``validate_*_via_endpoint`` call. On a handled error
        the ``validation_result`` is the original config (``"passthrough"``) or
        ``None`` (``"none"``), with the exception text in ``"error"``.

    Raises:
        ValueError: If *validator* is not ``"api"`` or ``"library"``, or if a
            required argument for the chosen validator is missing.
        Exception: Re-raised per-item failures when ``on_error="raise"``.
    """
    if validator not in ("api", "library"):
        raise ValueError(
            f"Unknown validator {validator!r}; expected 'api' or 'library'."
        )
    if validator == "library" and not target:
        raise ValueError("validator='library' requires a 'target' dotted path.")

    # Pre-load the local score once for the whole batch so each config doesn't
    # re-resolve the module (the path cache also covers this, but this avoids
    # re-checking on every item and lets an explicit local_score pass straight
    # through).
    resolved_mode = mode
    if resolved_mode == "auto":
        resolved_mode = "remote" if (endpoint_url and api_key) else "local"
    if resolved_mode == "local" and local_score is None:
        local_score = _load_local_score(validator, local_path)

    results: List[Dict[str, Any]] = []
    for config in configs:
        try:
            if validator == "api":
                result = validate_data_via_endpoint(
                    data=config,
                    endpoint_url=endpoint_url,
                    api_key=api_key,
                    schema=schema,
                    key_mapping=key_mapping,
                    strip_unknown=strip_unknown,
                    verbose=verbose,
                    mode=resolved_mode,
                    local_path=local_path,
                    local_score=local_score,
                    **endpoint_kwargs,
                )
            else:
                result = validate_config_via_endpoint(
                    target=target,
                    config=config,
                    endpoint_url=endpoint_url,
                    api_key=api_key,
                    type_mapping=type_mapping,
                    call_target=call_target,
                    verbose=verbose,
                    mode=resolved_mode,
                    local_path=local_path,
                    local_score=local_score,
                    **endpoint_kwargs,
                )
        except Exception as exc:  # noqa: BLE001 - surfaced per on_error policy
            if on_error == "raise":
                raise
            fallback = config if on_error == "passthrough" else None
            result = {
                "validation_result": fallback,
                "debug_logs": None,
                "error": str(exc),
            }
        results.append(result)

    return results
