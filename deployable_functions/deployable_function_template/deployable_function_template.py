def your_function_name():
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
            "fields": ["param1", "param2", "env_overrides", ...],
            "values": [[value1, value2, {"ENV_VAR": "new_value"}, ...]]
        }]
    }

    Or simplified format:
    {
        "input_data": [{
            "values": [[value1, value2, ...]]
        }]
    }

    Returns:
    {
        "predictions": [{
            "fields": ["field1", "field2", ...],
            "values": [[result1, result2, ...]]
        }]
    }
    """

    # ============================================================================
    # IMPORTS SECTION
    # ============================================================================
    # Add your imports here (they will be available throughout the function)
    # Import with full dot notation if you need specific methods/classes, e.g.  from transformers.models.auto.processing_auto import AutoProcessor to avoid errors.
    import os
    # Example additional imports:
    # import requests
    # import json
    # from datetime import datetime

    # ============================================================================
    # ENVIRONMENT & STATE MANAGEMENT
    # ============================================================================
    class FunctionState:
        """Manages environment variables and state with runtime overrides."""

        def __init__(self, load_all_env=True, specific_vars=None):
            """
            Initialize function state with environment variables.

            Args:
                load_all_env:   If True (default), loads all environment variables.
                                If False, only loads specific_vars.
                specific_vars:  Optional dict of specific environment variables to load.
                                Format: {"VAR_NAME": "default_value"}
                                If load_all_env is True, these will override/supplement all env vars.
            """
            self.env_vars = {}

            if load_all_env:
                # Load all environment variables
                self.env_vars = dict(os.environ)

            # Add or override with specific variables if provided
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
    # Default: loads all environment variables
    state = FunctionState(load_all_env=True)

    # Alternative initialization options:
    # Load only specific variables:
    # state = FunctionState(load_all_env=False, specific_vars={
    #     "API_KEY": "",
    #     "ENDPOINT_URL": "",
    #     "MODEL_ID": "default-model",
    #     "TIMEOUT": "30",
    # })

    # Load all env vars but ensure specific ones exist with defaults:
    # state = FunctionState(load_all_env=True, specific_vars={
    #     "API_KEY": "",
    #     "MODEL_ID": "default-model",
    # })

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
                # Field-based format
                params = dict(zip(fields, values))
            else:
                # Value-only format - return as indexed dict
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
    # Add your custom sub-functions here
    # These functions can be called from within the score() function

    def example_subfunction(input_string):
        """Example sub-function - replace with your own logic."""
        return f"Processed: {input_string}"

    # def your_custom_function(param1, param2):
    #     """Your custom logic here."""
    #     pass

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
            # YOUR CUSTOM LOGIC HERE
            # ================================================================
            # Extract your parameters
            # Example:
            # param1 = params.get("param1")
            # param2 = params.get("param2")

            # Use environment variables from state
            # Example:
            # api_key = state.get("API_KEY")
            # model_id = state.get("MODEL_ID")

            # Call your sub-functions
            # Example:
            # result = example_subfunction(param1)
            # ---

            # ---
            # Placeholder logic (replace this)
            result = "Your result here"

            # ================================================================
            # END CUSTOM LOGIC
            # ================================================================

            # Return success response
            return create_success_response(
                fields=["result"],  # Customize your output fields
                values=[result],  # Customize your output values
            )

        except Exception as e:
            # Return error response
            return create_error_response(
                error_message=f"Error processing request: {str(e)}"
            )

    return score


# ============================================================================
# FUNCTION INITIALIZATION
# ============================================================================
score = your_function_name()
