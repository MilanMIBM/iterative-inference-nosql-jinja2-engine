def ai_service_runtime_debugger(context, **custom):
    """
    watsonx.ai deployable AI service that inspects the runtime environment.
    Returns installed packages and their versions, and optionally
    pip-installs packages on demand.

    The outer function handles the REST call to the deployment endpoint
    POST /ml/v4/deployments

    Expected input payload format:
    {
        "return_packages": true,
        "install_packages": ["transformers", "torch>=2.0"],
        "upgrade": false
    }

    Returns:
    {
        "headers": {"Content-Type": "application/json"},
        "body": {
            "fields": ["installed_packages", "install_command", "install_result", "install_success"],
            "values": [[{...}, "pip install ...", "...", true]]
        }
    }
    """

    import os
    import subprocess
    import json

    task_token = context.generate_token()

    def create_success_response(fields, values):
        return {
            "headers": {"Content-Type": "application/json"},
            "body": {
                "fields": fields,
                "values": [values],
            },
        }

    def create_error_response(error_message):
        return {
            "headers": {"Content-Type": "application/json"},
            "body": {
                "fields": ["status", "error"],
                "values": [["error", str(error_message)]],
            },
        }

    def generate(context):
        """
        Handles REST calls to the inference endpoint:
        POST /ml/v4/deployments/{id_or_name}/ai_service

        Expected JSON body:
        {
            "return_packages": true,
            "install_packages": ["transformers", "torch>=2.0"],
            "upgrade": false
        }

        - return_packages (optional, bool): If true, return all installed packages with versions.
        - install_packages (optional, list[str]): List of packages to pip install.
        - upgrade (optional, bool): If true, add --upgrade flag to pip install. Defaults to false.
        """
        try:
            json_body = context.get_json() or {}

            return_packages = json_body.get("return_packages", False)
            install_packages = json_body.get("install_packages", [])
            upgrade = json_body.get("upgrade", False)

            install_result = None
            install_error = None

            # Pip install requested packages
            if install_packages and isinstance(install_packages, list):
                cmd = "pip install " + " ".join(install_packages)
                if upgrade:
                    cmd += " --upgrade"
                try:
                    output = subprocess.check_output(
                        cmd, shell=True, stderr=subprocess.STDOUT
                    )
                    install_result = output.decode("utf-8").strip()
                except subprocess.CalledProcessError as e:
                    install_error = e.output.decode("utf-8").strip()

            # Get installed packages
            packages = None
            if return_packages:
                try:
                    output = subprocess.check_output(
                        "pip list --format=json", shell=True, stderr=subprocess.STDOUT
                    )
                    packages = {
                        p["name"]: p["version"]
                        for p in json.loads(output.decode("utf-8"))
                    }
                except Exception as e:
                    packages = {"error": str(e)}

            # Build response fields/values dynamically based on what was requested
            response_fields = []
            response_values = []

            if return_packages:
                response_fields.append("installed_packages")
                response_values.append(packages)

            if install_packages:
                response_fields.append("install_command")
                response_values.append(
                    "pip install "
                    + " ".join(install_packages)
                    + (" --upgrade" if upgrade else "")
                )
                response_fields.append("install_result")
                response_values.append(
                    install_result if install_result else install_error
                )
                response_fields.append("install_success")
                response_values.append(install_error is None)

            if not response_fields:
                response_fields = ["message"]
                response_values = [
                    "No action requested. Set return_packages=true or provide install_packages."
                ]

            return create_success_response(response_fields, response_values)

        except Exception as e:
            return create_error_response(f"Error processing request: {str(e)}")

    def generate_stream(context):
        """
        Handles REST calls to the SSE inference endpoint:
        POST /ml/v4/deployments/{id_or_name}/ai_service_stream

        Streams installed packages as newline-delimited JSON chunks.
        """
        try:
            json_body = context.get_json() or {}

            return_packages = json_body.get("return_packages", False)
            install_packages = json_body.get("install_packages", [])
            upgrade = json_body.get("upgrade", False)

            # Pip install requested packages
            if install_packages and isinstance(install_packages, list):
                cmd = "pip install " + " ".join(install_packages)
                if upgrade:
                    cmd += " --upgrade"
                yield f"Running: {cmd}"
                try:
                    output = subprocess.check_output(
                        cmd, shell=True, stderr=subprocess.STDOUT
                    )
                    yield output.decode("utf-8").strip()
                except subprocess.CalledProcessError as e:
                    yield f"Install error: {e.output.decode('utf-8').strip()}"

            # Stream installed packages one by one
            if return_packages:
                try:
                    output = subprocess.check_output(
                        "pip list --format=json", shell=True, stderr=subprocess.STDOUT
                    )
                    packages = json.loads(output.decode("utf-8"))
                    for p in packages:
                        yield json.dumps({p["name"]: p["version"]})
                except Exception as e:
                    yield json.dumps({"error": str(e)})

            if not install_packages and not return_packages:
                yield "No action requested. Set return_packages=true or provide install_packages."

        except Exception as e:
            yield f"Error: {str(e)}"

    def generate_batch(input_data_references, output_data_reference):
        """
        Handles REST calls to the jobs endpoint:
        POST /ml/v4/deployments_jobs

        Not applicable for a runtime debugger - raises an informative error.
        """
        raise NotImplementedError(
            "generate_batch is not supported for the runtime debugger AI service. "
            "Use the online deployment and call the ai_service endpoint instead."
        )

    return generate, generate_stream, generate_batch
