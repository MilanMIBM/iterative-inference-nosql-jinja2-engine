def data_validator():
    """
    Flexible watsonx.ai deployable function for validating arbitrary data
    against a JSON Schema.

    This is a generic, schema-driven validator. It is not tied to any specific
    product or API: it accepts any data payload and any JSON Schema and returns
    a normalized/validated copy of the data (defaults applied, unknown
    properties optionally stripped).

    The schema may be provided as:
      - a parsed object (dict / list)
      - a JSON string
      - a YAML string (when PyYAML is available)
      - a JavaScript / JSON5-style object literal string (unquoted keys, single
        quotes, trailing commas, // and /* */ comments). This is the form most
        commonly copied out of JavaScript/TypeScript API definitions.

    Supported JSON Schema keywords:
      type, enum, const, properties, required, additionalProperties, items,
      $ref (local "#/..." pointers), allOf, anyOf, oneOf, not, default,
      minLength, maxLength, minimum, maximum, minItems, maxItems.

    Expected input payload format:
    {
        "input_data": [{
            "fields": ["data", "schema", "key_mapping", "strip_unknown", "verbose", "env_overrides"],
            "values": [[
                {"type": "selection", "name": "How satisfied are you?", ...},
                {...schema as dict / JSON / YAML / JS string...},
                {"open_ended": "openEnded"},
                true,
                false,
                {"ENV_VAR": "new_value"}
            ]]
        }]
    }

    Or simplified format (positional, schema-only):
    {
        "input_data": [{
            "values": [[
                {"name": "Any comments?"},
                {...schema...}
            ]]
        }]
    }

    Returns:
    {
        "predictions": [{
            "fields": ["validation_result"],
            "values": [[{...validated data...}]]
        }]
    }

    When verbose=true:
    {
        "predictions": [{
            "fields": ["validation_result", "debug_logs"],
            "values": [[{...validated data...}, ["[1/5] ...", ...]]]
        }]
    }
    """

    # ============================================================================
    # IMPORTS SECTION
    # ============================================================================
    import os
    import re
    import copy
    import json

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
    # DEFAULT SCHEMA (permissive object - used only when no schema is supplied)
    # ============================================================================
    DEFAULT_SCHEMA = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
    }

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
    # SCHEMA PARSING HELPERS (JSON / YAML / JavaScript object literals)
    # ============================================================================
    def _strip_js_comments(text):
        """Remove // line comments and /* */ block comments outside of strings."""
        out = []
        i = 0
        n = len(text)
        in_string = None  # holds the active quote char when inside a string
        while i < n:
            ch = text[i]
            if in_string:
                out.append(ch)
                if ch == "\\" and i + 1 < n:
                    out.append(text[i + 1])
                    i += 2
                    continue
                if ch == in_string:
                    in_string = None
                i += 1
                continue
            if ch in ("'", '"', "`"):
                in_string = ch
                out.append(ch)
                i += 1
                continue
            if ch == "/" and i + 1 < n and text[i + 1] == "/":
                i += 2
                while i < n and text[i] not in ("\n", "\r"):
                    i += 1
                continue
            if ch == "/" and i + 1 < n and text[i + 1] == "*":
                i += 2
                while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                    i += 1
                i += 2
                continue
            out.append(ch)
            i += 1
        return "".join(out)

    def _js_object_to_json(text):
        """
        Best-effort conversion of a JavaScript / JSON5-style object literal into
        strict JSON, then parse it. Handles unquoted keys, single quotes and
        trailing commas. Comments must already be stripped.
        """
        s = text.strip()
        # Single-quoted strings -> double-quoted (escape inner double quotes).
        def _requote(match):
            inner = match.group(1)
            inner = inner.replace("\\'", "'").replace('"', '\\"')
            return '"' + inner + '"'

        s = re.sub(r"'((?:[^'\\]|\\.)*)'", _requote, s)
        # Quote unquoted object keys:  { key:  ->  { "key":
        s = re.sub(
            r'([{\[,]\s*)([A-Za-z_$][A-Za-z0-9_$]*)(\s*:)',
            r'\1"\2"\3',
            s,
        )
        # Remove trailing commas before } or ].
        s = re.sub(r",(\s*[}\]])", r"\1", s)
        return json.loads(s)

    def parse_schema(schema):
        """
        Normalize a schema given as a dict/list or as a string in JSON, YAML or
        JavaScript object-literal form into a Python object.
        """
        if schema is None:
            return None
        if isinstance(schema, (dict, list)):
            return schema
        if not isinstance(schema, str):
            raise ValueError(
                f"Unsupported schema type: {type(schema).__name__}. "
                f"Provide a dict/list or a JSON/YAML/JS string."
            )

        text = schema.strip()
        if not text:
            return None

        # 1) Strict JSON first (fast path, also valid YAML for flow style).
        try:
            return json.loads(text)
        except Exception:
            pass

        # 2) YAML, if available (covers block-style schemas).
        try:
            import yaml  # type: ignore

            return yaml.safe_load(text)
        except ImportError:
            pass
        except Exception:
            pass

        # 3) JavaScript / JSON5-style object literal.
        try:
            return _js_object_to_json(_strip_js_comments(text))
        except Exception as e:
            raise ValueError(
                f"Could not parse schema as JSON, YAML or JS object literal: {str(e)}"
            )

    # ============================================================================
    # SCHEMA RESOLUTION HELPERS
    # ============================================================================
    def resolve_ref(ref_path, root_schema):
        """Resolve a $ref pointer within the schema (supports #/... JSON Pointer paths)."""
        if not ref_path.startswith("#/") and ref_path != "#":
            raise ValueError(
                f"Only local $ref pointers are supported, got: {ref_path}"
            )
        if ref_path == "#":
            return root_schema
        parts = ref_path.lstrip("#/").split("/")
        node = root_schema
        for part in parts:
            # JSON Pointer unescaping
            part = part.replace("~1", "/").replace("~0", "~")
            if isinstance(node, list):
                node = node[int(part)]
            else:
                node = node[part]
        return node

    # ============================================================================
    # GENERIC JSON SCHEMA VALIDATION
    # ============================================================================
    def validate_node(data, schema, root_schema, path, logs, verbose, strip_unknown):
        """
        Validate `data` against `schema`, returning a (possibly normalized) copy.

        Applies defaults, checks required fields, enforces enum/const/type and
        numeric/length bounds, and recurses through properties, items, $ref and
        the combinator keywords (allOf / anyOf / oneOf / not). Unknown object
        properties may be stripped when `strip_unknown` is True and the schema
        sets additionalProperties to False (or strip_unknown is forced).
        """

        def log(step, msg):
            if verbose:
                logs.append(f"[{step}] {msg}")

        loc = path or "<root>"

        # --- $ref ---
        if isinstance(schema, dict) and "$ref" in schema:
            resolved = resolve_ref(schema["$ref"], root_schema)
            log("ref", f"{loc}: resolved $ref {schema['$ref']}")
            return validate_node(
                data, resolved, root_schema, path, logs, verbose, strip_unknown
            )

        if not isinstance(schema, dict):
            # Boolean schemas: True accepts anything, False rejects.
            if schema is False:
                raise ValueError(f"{loc}: schema is 'false', value not allowed")
            return data

        # --- combinators ---
        if "allOf" in schema:
            for sub in schema["allOf"]:
                data = validate_node(
                    data, sub, root_schema, path, logs, verbose, strip_unknown
                )

        if "oneOf" in schema:
            matched = None
            errors = []
            for idx, sub in enumerate(schema["oneOf"]):
                try:
                    candidate = validate_node(
                        copy.deepcopy(data), sub, root_schema, path,
                        [], False, strip_unknown,
                    )
                    if matched is not None:
                        raise ValueError(
                            f"{loc}: matched more than one schema in 'oneOf'"
                        )
                    matched = candidate
                except ValueError as e:
                    errors.append(f"  oneOf[{idx}]: {str(e)}")
            if matched is None:
                detail = "\n".join(errors)
                raise ValueError(
                    f"{loc}: value did not match any schema in 'oneOf':\n{detail}"
                )
            log("oneOf", f"{loc}: matched one branch")
            data = matched

        if "anyOf" in schema:
            matched = None
            errors = []
            for idx, sub in enumerate(schema["anyOf"]):
                try:
                    matched = validate_node(
                        copy.deepcopy(data), sub, root_schema, path,
                        [], False, strip_unknown,
                    )
                    break
                except ValueError as e:
                    errors.append(f"  anyOf[{idx}]: {str(e)}")
            if matched is None:
                detail = "\n".join(errors)
                raise ValueError(
                    f"{loc}: value did not match any schema in 'anyOf':\n{detail}"
                )
            log("anyOf", f"{loc}: matched a branch")
            data = matched

        if "not" in schema:
            try:
                validate_node(
                    copy.deepcopy(data), schema["not"], root_schema, path,
                    [], False, strip_unknown,
                )
                negated = True
            except ValueError:
                negated = False
            if negated:
                raise ValueError(f"{loc}: value must not match 'not' schema")

        # --- const / enum ---
        if "const" in schema and data != schema["const"]:
            raise ValueError(
                f"{loc}: value {data!r} does not equal const {schema['const']!r}"
            )
        if "enum" in schema and data not in schema["enum"]:
            raise ValueError(
                f"{loc}: value {data!r} not in enum {schema['enum']}"
            )

        # --- type ---
        schema_type = schema.get("type")
        if schema_type is not None:
            check_type(data, schema_type, loc)

        # --- object ---
        if isinstance(data, dict) and (
            "properties" in schema
            or "required" in schema
            or "additionalProperties" in schema
            or schema_type == "object"
        ):
            data = validate_object(
                data, schema, root_schema, path, logs, verbose, strip_unknown
            )

        # --- array ---
        if isinstance(data, list):
            if "minItems" in schema and len(data) < schema["minItems"]:
                raise ValueError(
                    f"{loc}: array has {len(data)} items, minimum is {schema['minItems']}"
                )
            if "maxItems" in schema and len(data) > schema["maxItems"]:
                raise ValueError(
                    f"{loc}: array has {len(data)} items, maximum is {schema['maxItems']}"
                )
            if "items" in schema:
                item_schema = schema["items"]
                new_items = []
                for idx, item in enumerate(data):
                    new_items.append(
                        validate_node(
                            item, item_schema, root_schema,
                            f"{path}[{idx}]", logs, verbose, strip_unknown,
                        )
                    )
                data = new_items

        # --- string bounds ---
        if isinstance(data, str):
            if "minLength" in schema and len(data) < schema["minLength"]:
                raise ValueError(
                    f"{loc}: string length {len(data)} < minLength {schema['minLength']}"
                )
            if "maxLength" in schema and len(data) > schema["maxLength"]:
                raise ValueError(
                    f"{loc}: string length {len(data)} > maxLength {schema['maxLength']}"
                )

        # --- numeric bounds ---
        if isinstance(data, (int, float)) and not isinstance(data, bool):
            if "minimum" in schema and data < schema["minimum"]:
                raise ValueError(
                    f"{loc}: value {data} < minimum {schema['minimum']}"
                )
            if "maximum" in schema and data > schema["maximum"]:
                raise ValueError(
                    f"{loc}: value {data} > maximum {schema['maximum']}"
                )

        return data

    def validate_object(data, schema, root_schema, path, logs, verbose, strip_unknown):
        """Validate a dict against object-related schema keywords."""
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        additional = schema.get("additionalProperties", True)

        # Apply defaults for missing optional properties.
        for key, prop_schema in properties.items():
            if key not in data and isinstance(prop_schema, dict) and "default" in prop_schema:
                data[key] = copy.deepcopy(prop_schema["default"])

        # Required fields.
        missing = [k for k in required if k not in data]
        if missing:
            loc = path or "<root>"
            raise ValueError(f"{loc}: missing required fields: {missing}")

        result = {}
        for key, value in data.items():
            child_path = f"{path}.{key}" if path else key
            if key in properties:
                result[key] = validate_node(
                    value, properties[key], root_schema,
                    child_path, logs, verbose, strip_unknown,
                )
            else:
                # Unknown property.
                if additional is False:
                    if strip_unknown:
                        continue  # drop it
                    raise ValueError(
                        f"{child_path}: additional property not allowed"
                    )
                if isinstance(additional, dict):
                    result[key] = validate_node(
                        value, additional, root_schema,
                        child_path, logs, verbose, strip_unknown,
                    )
                else:
                    result[key] = value

        return result

    def check_type(data, schema_type, loc):
        """Enforce the JSON Schema 'type' keyword (string or list of strings)."""
        type_map = {
            "object": dict,
            "array": list,
            "string": str,
            "boolean": bool,
            "null": type(None),
        }
        types = schema_type if isinstance(schema_type, list) else [schema_type]

        def matches(t):
            if t == "integer":
                return isinstance(data, int) and not isinstance(data, bool)
            if t == "number":
                return isinstance(data, (int, float)) and not isinstance(data, bool)
            py = type_map.get(t)
            if py is None:
                return True  # unknown type keyword -> don't block
            if t == "boolean":
                return isinstance(data, bool)
            if py is int:
                return isinstance(data, int) and not isinstance(data, bool)
            return isinstance(data, py)

        if not any(matches(t) for t in types):
            raise ValueError(
                f"{loc}: value {data!r} is not of type {schema_type}"
            )

    # ============================================================================
    # TOP-LEVEL VALIDATION ENTRY
    # ============================================================================
    def validate_data(
        data,
        schema=None,
        key_mapping: dict | None = None,
        strip_unknown: bool = True,
        verbose: bool = False,
    ):
        """
        Validate `data` against `schema` (JSON Schema).

        Args:
            data: The value to validate (usually a dict).
            schema: JSON Schema as a dict/list or a JSON/YAML/JS string.
                    Falls back to a permissive object schema if not provided.
            key_mapping: Optional mapping applied to top-level dict keys before
                         validation (e.g. {"open_ended": "openEnded"}). Useful
                         when upstream systems use different naming conventions.
            strip_unknown: If True (default), drop properties not declared in the
                           schema when additionalProperties is False, instead of
                           raising.
            verbose: If True, collect debug info at each step.

        Returns:
            validated data, or (data, list[str]) if verbose.
        """
        logs = []

        def log(step, msg):
            if verbose:
                logs.append(f"[{step}] {msg}")

        parsed_schema = parse_schema(schema)
        if parsed_schema is None:
            parsed_schema = DEFAULT_SCHEMA
            log("1/4", "No schema supplied; using permissive default schema")
        else:
            log("1/4", "Schema parsed successfully")

        working = copy.deepcopy(data)

        # Optional top-level key remapping.
        if key_mapping and isinstance(working, dict):
            remapped = {}
            for k, v in working.items():
                new_k = key_mapping.get(k, k)
                remapped[new_k] = v
            if remapped != working:
                log("2/4", f"Applied key_mapping: {key_mapping}")
            working = remapped
        else:
            log("2/4", "No key_mapping applied")

        log("3/4", f"Validating data against schema (strip_unknown={strip_unknown})")
        result = validate_node(
            working, parsed_schema, parsed_schema, "", logs, verbose, strip_unknown
        )
        log("4/4", "Validation complete")

        if verbose:
            return result, logs
        return result

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
            # CUSTOM LOGIC - Generic Data Validation
            # ================================================================
            data = params.get("data", params.get("param_0"))
            schema = params.get("schema", params.get("param_1"))
            key_mapping = params.get("key_mapping", params.get("param_2"))
            strip_unknown = params.get("strip_unknown", True)
            verbose = params.get("verbose", False)

            if data is None:
                raise ValueError("'data' is required in the input payload")

            result = validate_data(
                data=data,
                schema=schema,
                key_mapping=key_mapping,
                strip_unknown=strip_unknown,
                verbose=verbose,
            )

            # ================================================================
            # END CUSTOM LOGIC
            # ================================================================

            if verbose:
                validation_result, debug_logs = result
                return create_success_response(
                    fields=["validation_result", "debug_logs"],
                    values=[validation_result, debug_logs],
                )

            return create_success_response(
                fields=["validation_result"],
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
score = data_validator()
