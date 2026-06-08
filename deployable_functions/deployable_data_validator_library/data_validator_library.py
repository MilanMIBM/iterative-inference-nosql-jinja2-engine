def data_validator_library():
    """
    Flexible watsonx.ai deployable function for validating data (a parameter
    config) against the signature of an arbitrary Python callable (class,
    method or function) resolved from an installed library.

    This is the library/signature flavor of data validation: instead of
    validating data against a JSON Schema (see the data_validator_api
    function), it validates data against the *call signature* of a real
    Python object discovered by introspection.

    Where the marimo widget validator is hard-wired to the `mo.ui.*` family of
    widget classes, this function is generic: it accepts any dotted import path
    (e.g. "collections.OrderedDict", "json.JSONEncoder",
    "datetime.datetime.fromtimestamp") and uses `inspect` to introspect the
    target's signature. It then:
      - filters a supplied config down to parameters the target actually accepts
      - fills missing required parameters with a fallback default
      - coerces values to match simple type annotations (list / dict / str)
      - optionally instantiates / calls the target to confirm the config is
        accepted, returning the validated parameter set.

    It is not tied to any specific product or API: point it at any class,
    method or function and it returns a normalized parameter dict that the
    target will accept, plus (optionally) a description of its signature.

    Expected input payload format:
    {
        "input_data": [{
            "fields": ["target", "config", "type_mapping", "call_target", "verbose", "env_overrides"],
            "values": [[
                "collections.OrderedDict",
                {"key": "value"},
                {"int_field": "int", "tag_field": "list"},
                false,
                false,
                {"ENV_VAR": "new_value"}
            ]]
        }]
    }

    Or simplified format (positional):
    {
        "input_data": [{
            "values": [[
                "collections.OrderedDict",
                {...config...}
            ]]
        }]
    }

    Fields:
      target        Dotted import path to a class / method / function, OR an
                    alias key into `type_mapping` that resolves to one.
      config        Dict of keyword arguments / parameters to validate.
      type_mapping  Optional dict. Either:
                      - alias -> dotted path (resolves `target` like the marimo
                        widget_mapping), and/or
                      - param_name -> "int"|"float"|"str"|"list"|"dict"|"bool"
                        hints used to coerce specific config values.
      call_target   If True, actually call/instantiate the target with the
                    validated params to confirm acceptance (defaults False, so
                    the function only reasons from the signature).
      verbose       If True, collect debug info at each step.

    Returns:
    {
        "predictions": [{
            "fields": ["inspection_result"],
            "values": [[{...validated params...}]]
        }]
    }

    When verbose=true:
    {
        "predictions": [{
            "fields": ["inspection_result", "debug_logs"],
            "values": [[{...validated params...}, ["[1/7] ...", ...]]]
        }]
    }
    """

    # ============================================================================
    # IMPORTS SECTION
    # ============================================================================
    import os
    import importlib
    import inspect

    # ============================================================================
    # ENVIRONMENT & STATE MANAGEMENT
    # ============================================================================
    class FunctionState:
        """Manages environment variables and state with runtime overrides."""

        def __init__(self, load_all_env=True, specific_vars=None):
            """
            Initialize function state with environment variables.

            Args:
                load_all_env: If True (default), loads all environment variables.
                              If False, only loads specific_vars.
                specific_vars: Optional dict of specific environment variables to load.
                              Format: {"VAR_NAME": "default_value"}
                              If load_all_env is True, these will override/supplement all env vars.
            """
            self.env_vars = {}
            if load_all_env:
                self.env_vars = dict(os.environ)
            if specific_vars and isinstance(specific_vars, dict):
                for key, default in specific_vars.items():
                    self.env_vars[key] = os.getenv(key, default)

        def update(self, overrides):
            """Update environment variables with runtime overrides."""
            if overrides and isinstance(overrides, dict):
                self.env_vars.update(overrides)

        def get(self, key, default=None):
            """Get environment variable value."""
            return self.env_vars.get(key, default)

        def get_all(self):
            """Get all environment variables."""
            return self.env_vars.copy()

    # Initialize state (persists across invocations in deployment)
    state = FunctionState(load_all_env=True)

    # ============================================================================
    # HELPER FUNCTIONS SECTION
    # ============================================================================
    def parse_input_payload(payload):
        """
        Parse input payload and extract parameters.

        Supports both field-based and value-only formats.
        Returns a dictionary of parameters.
        """
        try:
            input_data = payload.get("input_data", [{}])[0]
            fields = input_data.get("fields", [])
            values = input_data.get("values", [[]])[0]

            if fields:
                params = dict(zip(fields, values))
            else:
                params = {f"param_{i}": v for i, v in enumerate(values)}

            return params

        except Exception as e:
            raise ValueError(f"Failed to parse input payload: {str(e)}")

    def create_success_response(fields, values):
        """
        Create a standardized success response.

        Args:
            fields: List of field names
            values: List of corresponding values

        Returns:
            Formatted prediction response
        """
        return {"predictions": [{"fields": fields, "values": [values]}]}

    def create_error_response(error_message, include_fields=None):
        """
        Create a standardized error response.

        Args:
            error_message: Error description
            include_fields: Optional list of additional fields to include

        Returns:
            Formatted error response
        """
        fields = ["status", "error"]
        values = ["error", str(error_message)]

        if include_fields:
            fields.extend(include_fields)
            values.extend([None] * len(include_fields))

        return {"predictions": [{"fields": fields, "values": [values]}]}

    # ============================================================================
    # TARGET RESOLUTION HELPERS
    # ============================================================================
    def resolve_target(dotted_path):
        """
        Resolve a dotted import path to a Python object (class / method /
        function).

        Tries progressively shorter import prefixes so that paths like
        "datetime.datetime.fromtimestamp" (where "datetime.datetime" is the
        module-level class and "fromtimestamp" is an attribute) resolve
        correctly. Returns the resolved object.
        """
        if not isinstance(dotted_path, str) or not dotted_path.strip():
            raise ValueError("target must be a non-empty dotted import path string")

        parts = dotted_path.strip().split(".")
        last_err = None

        # Try importing the longest possible module prefix, then walk attributes.
        for split in range(len(parts) - 1, 0, -1):
            module_path = ".".join(parts[:split])
            attr_path = parts[split:]
            try:
                obj = importlib.import_module(module_path)
            except Exception as e:  # not importable at this depth, try shorter
                last_err = e
                continue
            try:
                for attr in attr_path:
                    obj = getattr(obj, attr)
                return obj
            except AttributeError as e:
                last_err = e
                continue

        raise ValueError(
            f"Could not resolve target '{dotted_path}': {last_err}"
        )

    def describe_target(obj):
        """Human-readable kind for a resolved object (for logs)."""
        if inspect.isclass(obj):
            return "class"
        if inspect.ismethod(obj):
            return "method"
        if inspect.isfunction(obj):
            return "function"
        if inspect.isbuiltin(obj):
            return "builtin"
        if callable(obj):
            return "callable"
        return type(obj).__name__

    def get_signature(obj):
        """
        Get the inspect.Signature for a callable, tolerating builtins / C
        objects that do not expose one.
        """
        try:
            return inspect.signature(obj)
        except (ValueError, TypeError):
            return None

    # ============================================================================
    # CONFIG VALIDATION AGAINST A SIGNATURE
    # ============================================================================
    def inspect_target(
        target: str,
        config: dict,
        type_mapping: dict | None = None,
        call_target: bool = False,
        verbose: bool = False,
    ):
        """
        Resolve `target`, introspect its signature and validate `config`
        against it.

        Args:
            target: Dotted import path, or alias key into type_mapping that
                    maps to a dotted path.
            config: Dict of parameters to validate.
            type_mapping: Optional dict carrying alias->path resolution and/or
                          param_name->type-hint coercion entries.
            call_target: If True, instantiate / call the target to confirm the
                         params are accepted.
            verbose: If True, collect debug info at each step.

        Returns:
            validated parameters (dict), or (dict, list[str]) if verbose.
        """
        logs = []
        type_mapping = type_mapping or {}
        config = config or {}

        def log(step, msg):
            if verbose:
                logs.append(f"[{step}] {msg}")

        log("1/7", f"Received target: {target!r}, config keys: {list(config)}")

        # --- resolve target, honoring type_mapping aliases ---
        resolved_path = type_mapping.get(target, target)
        if resolved_path != target:
            log("2/7", f"Resolved alias '{target}' -> '{resolved_path}'")
        obj = resolve_target(resolved_path)
        log("2/7", f"Resolved {describe_target(obj)}: {resolved_path}")

        sig = get_signature(obj)
        if sig is None:
            # No introspectable signature (e.g. some C builtins). We cannot
            # filter or fill from a signature, but explicit type_mapping hints
            # were supplied deliberately, so still apply those.
            log("3/7", "Target exposes no signature; applying explicit hints only")
            filtered_params = coerce_params(
                dict(config), None, type_mapping, config, log
            )
            if call_target:
                _result = obj(**filtered_params)  # noqa: F841
                log("7/7", "Target called successfully with raw config")
            if verbose:
                return filtered_params, logs
            return filtered_params

        log("3/7", f"Signature: {sig}")

        # --- filter to accepted params, preserving config insertion order ---
        accepts_var_keyword = any(
            p.kind == inspect.Parameter.VAR_KEYWORD
            for p in sig.parameters.values()
        )
        valid_params = set(sig.parameters.keys())
        filtered_params = {}
        for k, v in config.items():
            if k in ("self", "cls"):
                continue
            if k in valid_params or accepts_var_keyword:
                filtered_params[k] = v
            else:
                log("4/7", f"Dropping '{k}': not accepted by target signature")

        log("4/7", f"Filtered params: {list(filtered_params)}")

        # --- fill missing required params with a fallback default ---
        for param_name, param in sig.parameters.items():
            if param_name in ("self", "cls") or param_name in filtered_params:
                continue
            if param.default is not inspect.Parameter.empty:
                continue  # has a usable default
            if param.kind in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            ):
                continue
            log(
                "4.5/7",
                f"Required param '{param_name}' missing, adding fallback default",
            )
            filtered_params[param_name] = None

        # --- coerce types from explicit hints and/or annotations ---
        filtered_params = coerce_params(
            filtered_params, sig, type_mapping, config, log
        )

        log("6/7", f"Final params: {filtered_params}")

        # --- optionally call/instantiate to confirm acceptance ---
        if call_target:
            try:
                _result = obj(**filtered_params)  # noqa: F841
                log("7/7", "Target accepted the validated params")
            except (KeyError, ValueError, TypeError) as e:
                # Mirror the marimo validator's value=None fallback.
                if "value" in filtered_params:
                    log(
                        "ERR",
                        f"Failed with value={filtered_params['value']!r}: {e}. "
                        f"Retrying with value=None",
                    )
                    filtered_params["value"] = None
                    _result = obj(**filtered_params)  # noqa: F841
                else:
                    raise
        else:
            log("7/7", "call_target is False; not instantiating target")

        if verbose:
            return filtered_params, logs
        return filtered_params

    def coerce_params(filtered_params, sig, type_mapping, original_config, log):
        """
        Coerce param values toward expected types.

        Explicit hints in `type_mapping` (param_name -> "int"/"float"/"str"/
        "list"/"dict"/"bool") take priority; otherwise simple list/dict/str
        annotations on the signature are used, matching the marimo validator's
        behavior. Booleans are never coerced.
        """
        explicit = {
            "int": int,
            "float": float,
            "str": str,
            "bool": bool,
            "list": list,
            "dict": dict,
        }

        for param_name, current_val in list(filtered_params.items()):
            # Never coerce booleans — preserve True/False as-is.
            if isinstance(current_val, bool):
                log("5/7", f"'{param_name}' is boolean, preserving as-is")
                continue

            # 1) Explicit hint wins.
            hint = type_mapping.get(param_name)
            if isinstance(hint, str) and hint in explicit:
                target_type = explicit[hint]
                if hint == "list" and not isinstance(current_val, (list, tuple)):
                    filtered_params[param_name] = [current_val]
                    log("5/7", f"'{param_name}' wrapped in list (hint)")
                elif hint == "dict" and not isinstance(current_val, dict):
                    log("5/7", f"'{param_name}' hinted dict but value is not; leaving as-is")
                elif not isinstance(current_val, target_type) and current_val is not None:
                    try:
                        filtered_params[param_name] = target_type(current_val)
                        log("5/7", f"'{param_name}' cast to {hint} (hint)")
                    except (ValueError, TypeError):
                        log("5/7", f"'{param_name}' could not cast to {hint}; leaving as-is")
                continue

            # 2) Fall back to annotation-driven coercion (list/dict/str).
            # Skipped entirely when no signature is available (hints only).
            param_sig = sig.parameters.get(param_name) if sig is not None else None
            if not param_sig or param_sig.annotation == inspect.Parameter.empty:
                continue

            ann_str = str(param_sig.annotation)
            expects_list = any(
                h in ann_str for h in ["List", "list", "Sequence", "sequence"]
            )
            expects_dict = any(
                h in ann_str for h in ["Dict", "dict", "Mapping", "mapping"]
            )
            expects_str = any(
                h in ann_str for h in ["'str'", "<class 'str'>", "str"]
            )

            # Skip coercion if current type is already accepted by the annotation.
            if isinstance(current_val, dict) and (expects_dict or expects_list):
                continue
            if isinstance(current_val, (list, tuple)) and (expects_list or expects_dict):
                continue
            if isinstance(current_val, str) and expects_str:
                continue

            if expects_list and not isinstance(current_val, (list, tuple)):
                filtered_params[param_name] = [current_val]
                log("5/7", f"'{param_name}' wrapped in list: {filtered_params[param_name]}")
            elif (
                expects_str
                and isinstance(current_val, list)
                and len(current_val) == 1
            ):
                filtered_params[param_name] = current_val[0]
                log("5/7", f"'{param_name}' unwrapped from list: {filtered_params[param_name]}")
            elif expects_str and not isinstance(current_val, str):
                filtered_params[param_name] = str(current_val)
                log("5/7", f"'{param_name}' cast to str: {filtered_params[param_name]}")

        # Rebuild in original config key order to preserve input ordering.
        ordered = {
            k: filtered_params[k] for k in original_config if k in filtered_params
        }
        # Append any params added by the validator (e.g. fallback defaults).
        for k, v in filtered_params.items():
            if k not in ordered:
                ordered[k] = v
        return ordered

    # ============================================================================
    # MAIN SCORE FUNCTION
    # ============================================================================
    def score(payload):
        """
        Main scoring function called for each prediction request.

        Args:
            payload: Input payload in watsonx.ai format

        Returns:
            Prediction results in watsonx.ai format
        """
        try:
            # Parse input payload
            params = parse_input_payload(payload)

            # Check for environment variable overrides
            env_overrides = params.get("env_overrides")
            if env_overrides:
                state.update(env_overrides)

            # ================================================================
            # CUSTOM LOGIC - Library Target Inspection
            # ================================================================
            target = params.get("target", params.get("param_0"))
            config = params.get("config", params.get("param_1"))
            type_mapping = params.get("type_mapping", params.get("param_2"))
            call_target = params.get("call_target", False)
            verbose = params.get("verbose", False)

            if not target:
                raise ValueError("'target' is required in the input payload")

            if config is None:
                config = {}

            result = inspect_target(
                target=target,
                config=config,
                type_mapping=type_mapping,
                call_target=call_target,
                verbose=verbose,
            )

            # ================================================================
            # END CUSTOM LOGIC
            # ================================================================

            if verbose:
                inspection_result, debug_logs = result
                return create_success_response(
                    fields=["inspection_result", "debug_logs"],
                    values=[inspection_result, debug_logs],
                )

            return create_success_response(
                fields=["inspection_result"],
                values=[result],
            )

        except Exception as e:
            return create_error_response(
                error_message=f"Error processing request: {str(e)}"
            )

    return score


# ============================================================================
# FUNCTION INITIALIZATION
# ============================================================================
score = library_inspector()
