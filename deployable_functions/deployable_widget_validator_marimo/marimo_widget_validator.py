def marimo_widget_validator():
    """
    Flexible watsonx.ai deployable function template.

    This template provides a stateful environment for deployable functions with:
    - Environment variable management with runtime overrides
    - Flexible input/output handling
    - Support for custom sub-functions
    - Standardized error handling

    Expected input payload format:
    {
        "input_data": [{
            "fields": ["widget_config", "widget_mapping", "verbose", "env_overrides"],
            "values": [[
                {"type": "slider", "start": 0, "stop": 100},
                {"slider": "mo.ui.slider"},
                false,
                {"ENV_VAR": "new_value"}
            ]]
        }]
    }

    Or simplified format:
    {
        "input_data": [{
            "values": [[
                {"type": "slider", "start": 0, "stop": 100},
                {"slider": "mo.ui.slider"}
            ]]
        }]
    }

    Returns:
    {
        "predictions": [{
            "fields": ["widget_result"],
            "values": [[{...validated params...}]]
        }]
    }

    When verbose=true:
    {
        "predictions": [{
            "fields": ["widget_result", "debug_logs"],
            "values": [[{...validated params...}, ["[1/6] ...", ...]]]
        }]
    }
    """

    # ============================================================================
    # IMPORTS SECTION
    # ============================================================================
    import os
    import marimo as mo
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
    # CUSTOM SUB-FUNCTIONS SECTION
    # ============================================================================
    def create_marimo_widget(
        widget_config: dict,
        widget_mapping: dict,
        verbose: bool = False,
    ):
        """
        Create a marimo widget from a configuration dictionary.

        Args:
            widget_config (dict): Configuration containing 'type' and other widget parameters
            widget_mapping (dict): Mapping of widget type IDs to widget names
            verbose (bool): If True, collect debug info at each step

        Returns:
            validated input parameters (dict), or (dict, list[str]) if verbose
        """
        logs = []

        def log(step, msg):
            if verbose:
                logs.append(f"[{step}] {msg}")

        def coerce_params(filtered_params, sig):
            """Coerce all param types based on widget signature annotations."""
            for param_name, current_val in list(filtered_params.items()):
                param_sig = sig.parameters.get(param_name)
                if not param_sig or param_sig.annotation == inspect.Parameter.empty:
                    continue

                # Never coerce booleans — preserve True/False as-is
                if isinstance(current_val, bool):
                    log("5/6", f"'{param_name}' is boolean, preserving as-is")
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

                # Skip coercion if the current type is already accepted
                # by any branch of a union annotation (e.g. Sequence[str] | dict[str, Any]).
                if isinstance(current_val, dict) and (expects_dict or expects_list):
                    log("5/6", f"'{param_name}' already valid as dict (accepted by annotation), skipping")
                    continue
                if isinstance(current_val, (list, tuple)) and (expects_list or expects_dict):
                    log("5/6", f"'{param_name}' already valid as list (accepted by annotation), skipping")
                    continue
                if isinstance(current_val, str) and expects_str:
                    log("5/6", f"'{param_name}' already valid as str, skipping")
                    continue

                # Coerce only if current type doesn't match any accepted type
                if expects_list and not isinstance(current_val, (list, tuple)):
                    filtered_params[param_name] = [current_val]
                    log(
                        "5/6",
                        f"'{param_name}' wrapped in list: {filtered_params[param_name]}",
                    )
                elif (
                    expects_str
                    and isinstance(current_val, list)
                    and len(current_val) == 1
                ):
                    filtered_params[param_name] = current_val[0]
                    log(
                        "5/6",
                        f"'{param_name}' unwrapped from list: {filtered_params[param_name]}",
                    )
                elif expects_str and not isinstance(current_val, str):
                    filtered_params[param_name] = str(current_val)
                    log(
                        "5/6",
                        f"'{param_name}' cast to str: {filtered_params[param_name]}",
                    )

            # Rebuild in original widget_config key order to preserve input ordering
            return {
                k: filtered_params[k] for k in widget_config if k in filtered_params
            }

        log("1/6", f"Received widget_config: {widget_config}")

        # Resolve widget type and class
        widget_type = widget_config.get("type")
        if not widget_type:
            raise ValueError("Widget configuration must include 'type' key")

        if widget_type not in widget_mapping:
            raise ValueError(f"Unknown widget type: {widget_type}")

        widget_name = widget_mapping[widget_type]
        log("2/6", f"Resolved: {widget_type} -> {widget_name}")

        widget_class = mo
        for part in widget_name.split(".")[1:]:
            widget_class = getattr(widget_class, part)

        sig = inspect.signature(widget_class)
        log("3/6", f"Widget class: {widget_class}\nExpected schema: {sig}")

        # Filter to valid params only, preserving widget_config insertion order
        valid_params = set(sig.parameters.keys())
        filtered_params = {}
        for k, v in widget_config.items():
            if k != "type" and k in valid_params:
                filtered_params[k] = v

        log("4/6", f"Filtered params: {filtered_params}")

        # Fill missing required parameters with defaults from the signature
        for param_name, param in sig.parameters.items():
            if param_name in ("self",) or param_name in filtered_params:
                continue
            if param.default is not inspect.Parameter.empty:
                # Has a default - only fill if missing and default is meaningful
                continue
            if param.kind in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            ):
                continue
            # This parameter is required but missing from input
            log(
                "4.5/6",
                f"Required param '{param_name}' missing, adding fallback default",
            )
            filtered_params[param_name] = []

        # Coerce types
        filtered_params = coerce_params(filtered_params, sig)

        log("6/6", f"Final params: {filtered_params}")

        # Create widget with fallback to value=None on error
        try:
            _widget = widget_class(**filtered_params)  # noqa: F841
        except (KeyError, ValueError, TypeError) as e:
            if "value" in filtered_params:
                log(
                    "ERR",
                    f"Failed with value={filtered_params['value']!r}: {e}. Retrying with value=None",
                )
                filtered_params["value"] = None
                _widget = widget_class(**filtered_params)  # noqa: F841
            else:
                raise

        def ensure_original_data_order(value, original):
            """Recursively reorder nested dicts/lists to match original ordering, only if out of order."""
            if isinstance(value, dict) and isinstance(original, dict):
                # Check if keys already match original order
                original_order = [k for k in original if k in value]
                value_order = [k for k in value if k in original]
                if original_order == value_order:
                    # Keys already in order, just recurse into nested values
                    return {
                        k: ensure_original_data_order(v, original.get(k, v))
                        for k, v in value.items()
                    }
                # Keys are out of order, rebuild
                reordered = {}
                for k in original:
                    if k in value:
                        reordered[k] = ensure_original_data_order(value[k], original[k])
                for k in value:
                    if k not in reordered:
                        reordered[k] = value[k]
                return reordered
            if isinstance(value, list) and isinstance(original, list):
                # Only recurse into list elements when lengths match AND
                # elements are dicts (key-order restoration is meaningful).
                # When items were reordered, added, or removed, positional
                # correspondence no longer holds - return value as-is.
                if len(value) == len(original) and all(
                    isinstance(v, dict) and isinstance(o, dict)
                    for v, o in zip(value, original)
                ):
                    return [
                        ensure_original_data_order(v, original[i])
                        for i, v in enumerate(value)
                    ]
                return value
            return value

        # Reorder filtered_params to match original widget_config ordering (including nested)
        filtered_params = ensure_original_data_order(filtered_params, widget_config)

        if verbose:
            return filtered_params, logs
        return filtered_params

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
            # CUSTOM LOGIC - Widget Validation
            # ================================================================
            widget_config = params.get("widget_config")
            widget_mapping = params.get("widget_mapping")
            verbose = params.get("verbose", False)

            if not widget_config:
                raise ValueError("'widget_config' is required in the input payload")

            if not widget_mapping:
                widget_mapping = {
                    "opendended_questions": "mo.ui.text_area",
                    "scale_selection_questions": "mo.ui.radio",
                    "text_field_questions": "mo.ui.text",
                    "numeric_questions": "mo.ui.number",
                    "dropdown_list_questions": "mo.ui.dropdown",
                    "multiple_selection_questions": "mo.ui.multiselect",
                    "nps": "mo.ui.radio",
                }

            result = create_marimo_widget(
                widget_config=widget_config,
                widget_mapping=widget_mapping,
                verbose=verbose,
            )

            # ================================================================
            # END CUSTOM LOGIC
            # ================================================================

            if verbose:
                widget_result, debug_logs = result
                return create_success_response(
                    fields=["widget_result", "debug_logs"],
                    values=[widget_result, debug_logs],
                )

            return create_success_response(
                fields=["widget_result"],
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
score = marimo_widget_validator()
