def runtime_debugger_function():
    """
    watsonx.ai deployable function that inspects the runtime environment.
    Returns installed packages and their versions, and optionally
    pip-installs packages on demand.
    """

    import subprocess

    def score(input_data):
        """
        Score function that inspects and optionally modifies the runtime environment.

        Expected input_data format:
        {
            "input_data": [{
                "fields": ["return_packages", "install_packages", "upgrade"],
                "values": [[true, ["transformers", "torch>=2.0"], true]]
            }]
        }

        - return_packages (optional, bool): If true, return all installed packages with versions.
        - install_packages (optional, list[str]): List of packages to pip install (e.g. ["transformers", "numpy>=2.0"]).
        - upgrade (optional, bool): If true, add --upgrade flag to pip install. Defaults to false.
        """
        try:
            input_entry = input_data.get("input_data")[0]
            fields = input_entry.get("fields", [])
            values = input_entry.get("values", [[]])[0]

            if fields:
                params = dict(zip(fields, values))
            else:
                params = {}

            return_packages = params.get("return_packages", False)
            install_packages = params.get("install_packages", [])
            upgrade = params.get("upgrade", False)

            install_result = None
            install_error = None

            # Pip install requested packages
            if install_packages and isinstance(install_packages, list):
                cmd = "pip install " + " ".join(install_packages)
                if upgrade:
                    cmd += " --upgrade"
                try:
                    output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
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
                    import json
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
                    "pip install " + " ".join(install_packages) + (" --upgrade" if upgrade else "")
                )
                response_fields.append("install_result")
                response_values.append(install_result if install_result else install_error)
                response_fields.append("install_success")
                response_values.append(install_error is None)

            if not response_fields:
                response_fields = ["message"]
                response_values = ["No action requested. Set return_packages=true or provide install_packages."]

            return {
                "predictions": [{
                    "fields": response_fields,
                    "values": [response_values],
                }]
            }

        except Exception as e:
            return {
                "predictions": [{
                    "fields": ["error", "error_details"],
                    "values": [["processing_error", str(e)]],
                }]
            }

    return score


# Create the score function instance
score = runtime_debugger_function()
