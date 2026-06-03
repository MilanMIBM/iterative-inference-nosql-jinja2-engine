def your_ai_service_name(context, **custom):
    """
    Flexible watsonx.ai deployable AI service template.

    This template provides a stateful environment for deployable AI services with:
    - Context-based token and request management
    - Environment variable management with runtime overrides
    - Support for generate, generate_stream, and generate_batch functions
    - Flexible input/output handling
    - Standardized error handling

    The outer function handles the REST call to the deployment endpoint
    POST /ml/v4/deployments

        context.generate_token() - generate a token from the task credentials

    To use `generate` and `generate_stream`, the deployment must be ONLINE.
    To use `generate_batch`, the deployment must be BATCH.

    Expected input payload format for generate/generate_stream:
    {
        "param1": "value1",
        "param2": "value2",
        "env_overrides": {"ENV_VAR": "new_value"}
    }

    Returns from generate:
    {
        "headers": {"Content-Type": "application/json"},
        "body": {
            "fields": ["field1", "field2"],
            "values": [[result1, result2]]
        }
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
    class ServiceState:
        """Manages environment variables and state with runtime overrides."""

        def __init__(self, load_all_env=True, specific_vars=None):
            """
            Initialize service state with environment variables.

            Args:
                load_all_env:   If True (default), loads all environment variables.
                                If False, only loads specific_vars.
                specific_vars:  Optional dict of specific environment variables to load.
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
    state = ServiceState(load_all_env=True)

    # Alternative initialization options:
    # state = ServiceState(load_all_env=False, specific_vars={
    #     "API_KEY": "",
    #     "ENDPOINT_URL": "",
    #     "MODEL_ID": "default-model",
    #     "TIMEOUT": "30",
    # })

    # Generate task token from context (available to all nested functions)
    task_token = context.generate_token()

    # Store custom deployment parameters (passed at deployment creation time)
    deployment_custom = custom

    # ============================================================================
    # HELPER FUNCTIONS SECTION
    # ============================================================================

    def parse_request_body(json_body):
        """
        Parse request JSON body and extract parameters.

        Args:
            json_body: The JSON body from context.get_json()

        Returns a dictionary of parameters.
        """
        if json_body is None:
            return {}
        if isinstance(json_body, dict):
            return json_body
        raise ValueError(f"Unexpected request body type: {type(json_body)}")

    def create_success_response(
        fields, values, content_type="application/json", extra_headers=None
    ):
        """
        Create a standardized success response.

        Args:
            fields: List of field names
            values: List of corresponding values
            content_type: Response content type header
            extra_headers: Optional dict of additional response headers

        Returns:
            Formatted AI service response dict with headers and body
        """
        headers = {"Content-Type": content_type}
        if extra_headers:
            headers.update(extra_headers)

        return {
            "headers": headers,
            "body": {
                "fields": fields,
                "values": [values],
            },
        }

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

        return {
            "headers": {"Content-Type": "application/json"},
            "body": {
                "fields": fields,
                "values": [values],
            },
        }

    # ============================================================================
    # CUSTOM SUB-FUNCTIONS SECTION
    # ============================================================================
    # Add your custom sub-functions here
    # These functions can be called from within generate/generate_stream/generate_batch

    def example_subfunction(input_string):
        """Example sub-function - replace with your own logic."""
        return f"Processed: {input_string}"

    # def your_custom_function(param1, param2):
    #     """Your custom logic here."""
    #     pass

    # ============================================================================
    # GENERATE FUNCTION (Online deployment - synchronous)
    # ============================================================================

    def generate(context):
        """
        Handles REST calls to the inference endpoint:
        POST /ml/v4/deployments/{id_or_name}/ai_service

            context.get_token()   - get the Bearer token from the request header
            context.get_json()    - get the body of the request
            context.get_headers() - get the headers of the request

        Must return a dict with optional 'headers' and 'body' keys.
        """
        try:
            user_token = context.get_token()
            json_body = context.get_json()

            # Parse request body
            params = parse_request_body(json_body)

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

            # Use deployment custom parameters
            # Example:
            # space_id = deployment_custom.get("space_id")

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

            return create_success_response(
                fields=["result"],  # Customize your output fields
                values=[result],  # Customize your output values
            )

        except Exception as e:
            return create_error_response(
                error_message=f"Error processing request: {str(e)}"
            )

    # ============================================================================
    # GENERATE STREAM FUNCTION (Online deployment - streaming/SSE)
    # ============================================================================

    def generate_stream(context):
        """
        Handles REST calls to the SSE inference endpoint:
        POST /ml/v4/deployments/{id_or_name}/ai_service_stream

            context.get_token()   - get the Bearer token from the request header
            context.get_json()    - get the body of the request
            context.get_headers() - get the headers of the request

        Must be a Python generator (use yield).
        Each yielded value becomes the 'data' field of an SSE event.
        The stream ends with an 'eos' (End of Stream) event automatically.
        """
        try:
            user_token = context.get_token()
            json_body = context.get_json()

            # Parse request body
            params = parse_request_body(json_body)

            # Check for environment variable overrides
            env_overrides = params.get("env_overrides")
            if env_overrides:
                state.update(env_overrides)

            # ================================================================
            # YOUR CUSTOM STREAMING LOGIC HERE
            # ================================================================
            # Example: Stream results one at a time
            # for chunk in your_streaming_function(params):
            #     yield chunk

            # ---
            # Placeholder logic (replace this)
            for chunk in ["Hello", "from", "AI", "service"]:
                yield chunk

            # ================================================================
            # END CUSTOM STREAMING LOGIC
            # ================================================================

        except Exception as e:
            yield f"Error: {str(e)}"

    # ============================================================================
    # GENERATE BATCH FUNCTION (Batch deployment)
    # ============================================================================

    def generate_batch(input_data_references, output_data_reference):
        """
        Handles REST calls to the jobs endpoint:
        POST /ml/v4/deployments_jobs

        Args:
            input_data_references: list[dict] - scoring.input_data_references from request
            output_data_reference: dict - scoring.output_data_reference from request

        The context object from the outer function is accessible for token generation.
        """
        try:
            batch_token = context.generate_token()

            # ================================================================
            # YOUR CUSTOM BATCH LOGIC HERE
            # ================================================================
            # Process input_data_references and write results to output_data_reference
            # Example:
            # for ref in input_data_references:
            #     data = load_data(ref)
            #     results = process_data(data)
            #     save_results(results, output_data_reference)

            # ---
            # Placeholder logic (replace this)
            print(
                f"generate_batch:\n{input_data_references=}\n{output_data_reference=}",
                flush=True,
            )

            # ================================================================
            # END CUSTOM BATCH LOGIC
            # ================================================================

        except Exception as e:
            print(f"Batch error: {str(e)}", flush=True)
            raise

    return generate, generate_stream, generate_batch
