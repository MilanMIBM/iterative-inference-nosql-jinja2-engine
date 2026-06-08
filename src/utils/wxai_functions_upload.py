"""
Upload a deployable Python function to IBM watsonx.ai.

Usage as module:
    python -m utils.sw_compatible.wxai_functions_upload \
        --folder_path ./my_function_folder \
        --function_file score.py \
        --wx_api_key <key> \
        --wx_space_id <space_id>

Usage as module (CPD):
    python -m utils.sw_compatible.wxai_functions_upload \
        --folder_path ./my_function_folder \
        --function_file score.py \
        --wx_api_key <key> \
        --wx_space_id <space_id> \
        --wx_user <username> \
        --wx_url <cpd-url> \
        --cpd

Usage as callable script:
    python src/utils/wxai_functions_upload.py \
        --folder_path ./my_function_folder \
        --function_file score.py \
        --wx_api_key <key> \
        --wx_space_id <space_id>

Usage as callable script (CPD):
    python src/utils/wxai_functions_upload.py \
        --folder_path ./my_function_folder \
        --function_file score.py \
        --wx_api_key <key> \
        --wx_space_id <space_id> \
        --wx_user <username> \
        --wx_url <cpd-url> \
        --cpd
"""

import argparse
import gzip
import json
import os
import re
import shutil
import uuid

from ibm_watsonx_ai import APIClient, Credentials

DEFAULT_SOFTWARE_SPEC_ID = "f47ae1c3-198e-5718-b59d-2ea471561e9e"


def upload_watsonxai_function(
    folder_path,
    function_file=None,
    wx_api_key=None,
    wx_space_id=None,
    function_name=None,
    software_spec_id=DEFAULT_SOFTWARE_SPEC_ID,
    input_schema_path=None,
    output_schema_path=None,
    requirements=None,
    wx_url="https://eu-de.ml.cloud.ibm.com",
    wx_user=None,
    cpd=False,
):
    """
    Uploads a Python function to watsonx.ai as a deployable asset.

    Parameters:
        folder_path (str): Path to the folder containing the function file and optional schemas.
        function_file (str, optional): Name of the .py file to upload (e.g. "my_func.py").
            If not provided, auto-discovers the first .py file in the folder that contains
            a score function (e.g. "score = ..." or "def score").
        wx_api_key (str): IBM watsonx.ai API key.
        wx_space_id (str): IBM watsonx.ai deployment space ID.
        function_name (str, optional): Name for the deployed function. If not provided,
            defaults to the .py filename without extension.
        software_spec_id (str, optional): Software specification ID.
            Defaults to "f47ae1c3-198e-5718-b59d-2ea471561e9e" (runtime-25.1-py3.12).
            If a non-default value is provided, requirements are ignored and this spec is used directly.
        input_schema_path (str, optional): Filename of the input schema JSON in the folder.
            If not provided, auto-discovers a JSON file containing "input_schema" in its name.
        output_schema_path (str, optional): Filename of the output schema JSON in the folder.
            If not provided, auto-discovers a JSON file containing "output_schema" in its name.
        requirements (str, optional): Filename of a requirements file in the folder.
            If not provided, auto-discovers "requirements.txt" in the folder. If found and
            software_spec_id is the default, creates a custom package extension and software spec.
        wx_url (str, optional): watsonx.ai URL. Defaults to "https://eu-de.ml.cloud.ibm.com".
        wx_user (str, optional): Username for CPD (Cloud Pak for Data) authentication.
        cpd (bool, optional): If True, uses CPD credentials (url + username + api_key).
            Also triggered automatically when wx_user is provided.

    Returns:
        dict: Details of the uploaded function.
    """
    # --- Resolve paths ---
    folder_path = os.path.abspath(folder_path)

    # Auto-discover function file if not provided
    if function_file is None:
        score_pattern = re.compile(r"^(?:def\s+score\b|score\s*=)", re.MULTILINE)
        for f in sorted(os.listdir(folder_path)):
            if not f.endswith(".py"):
                continue
            with open(os.path.join(folder_path, f), "r", encoding="utf-8") as fh:
                if score_pattern.search(fh.read()):
                    function_file = f
                    print(f"Auto-discovered function file: {function_file}")
                    break
        if function_file is None:
            raise FileNotFoundError(
                f"No .py file with a score function found in: {folder_path}"
            )

    function_file_path = os.path.join(folder_path, function_file)
    if not os.path.isfile(function_file_path):
        raise FileNotFoundError(f"Function file not found: {function_file_path}")

    # --- Determine function_name from the .py filename if not provided ---
    if not function_name:
        function_name = os.path.splitext(function_file)[0]

    # --- Auto-discover files ---
    folder_files = os.listdir(folder_path)

    def _find_file(keyword, extension=".json"):
        matches = [
            f for f in folder_files if f.endswith(extension) and keyword in f.lower()
        ]
        return matches[0] if matches else None

    if input_schema_path is None:
        input_schema_path = _find_file("input_schema")
    if output_schema_path is None:
        output_schema_path = _find_file("output_schema")

    # Auto-discover requirements file
    if requirements is None:
        if "requirements.txt" in folder_files:
            requirements = "requirements.txt"

    requirements_file_path = None
    if requirements:
        requirements_file_path = os.path.join(folder_path, requirements)
        if not os.path.isfile(requirements_file_path):
            print(f"Requirements file not found: {requirements_file_path}, skipping.")
            requirements_file_path = None
        elif os.path.getsize(requirements_file_path) == 0:
            print(f"Requirements file is empty: {requirements_file_path}, skipping.")
            requirements_file_path = None

    # --- Load schemas ---
    input_schema = None
    output_schema = None
    if input_schema_path:
        with open(os.path.join(folder_path, input_schema_path), "r") as f:
            input_schema = json.load(f)
    if output_schema_path:
        with open(os.path.join(folder_path, output_schema_path), "r") as f:
            output_schema = json.load(f)

    # --- Initialize watsonx.ai client ---
    if cpd or wx_user:
        wx_credentials = Credentials(url=wx_url, username=wx_user, api_key=wx_api_key)
    else:
        wx_credentials = Credentials(url=wx_url, api_key=wx_api_key)
    client = APIClient(wx_credentials)
    client.set.default_space(wx_space_id)
    print(f"watsonx.ai client targeting deployment space: {wx_space_id}")

    # --- Create custom package extension + software spec if requirements found and using default spec ---
    use_spec_id = software_spec_id
    if requirements_file_path and software_spec_id == DEFAULT_SOFTWARE_SPEC_ID:
        spec_suffix = str(uuid.uuid4())[:4]

        # Upload package extension
        pe_suffix = f"_pkg_{spec_suffix}"
        pe_base = function_name[: 36 - len(pe_suffix)]
        pe_metadata = {
            client.package_extensions.ConfigurationMetaNames.NAME: f"{pe_base}{pe_suffix}",
            client.package_extensions.ConfigurationMetaNames.TYPE: "requirements_txt",
        }
        print(
            f"Creating package extension: {pe_metadata[client.package_extensions.ConfigurationMetaNames.NAME]}"
        )
        pe_asset_details = client.package_extensions.store(
            meta_props=pe_metadata, file_path=requirements_file_path
        )
        package_id = pe_asset_details.get("metadata").get("asset_id")
        print(f"Package extension created - id: {package_id}")

        # Create custom software spec with the package extension
        ss_suffix = f"_sw_sp_{spec_suffix}"
        ss_base = function_name[: 36 - len(ss_suffix)]
        ss_metadata = {
            client.software_specifications.ConfigurationMetaNames.NAME: f"{ss_base}{ss_suffix}",
            client.software_specifications.ConfigurationMetaNames.BASE_SOFTWARE_SPECIFICATION: {
                "guid": DEFAULT_SOFTWARE_SPEC_ID
            },
            client.software_specifications.ConfigurationMetaNames.PACKAGE_EXTENSIONS: [
                {"guid": package_id}
            ],
        }
        print(
            f"Creating software spec: {ss_metadata[client.software_specifications.ConfigurationMetaNames.NAME]}"
        )
        ss_asset_details = client.software_specifications.store(meta_props=ss_metadata)
        use_spec_id = ss_asset_details.get("metadata").get("asset_id")
        print(f"Software spec created - id: {use_spec_id}")

    # --- Build function metadata ---
    function_meta = {
        client.repository.FunctionMetaNames.NAME: function_name[:36],
        client.repository.FunctionMetaNames.SOFTWARE_SPEC_ID: use_spec_id,
    }

    if input_schema is not None:
        function_meta[client.repository.FunctionMetaNames.INPUT_DATA_SCHEMAS] = (
            input_schema if isinstance(input_schema, list) else [input_schema]
        )
    if output_schema is not None:
        function_meta[client.repository.FunctionMetaNames.OUTPUT_DATA_SCHEMAS] = (
            output_schema if isinstance(output_schema, list) else [output_schema]
        )

    # --- Gzip the function file and upload ---
    original_dir = os.getcwd()
    try:
        tmp_dir = "/tmp/notebook_functions"
        os.makedirs(tmp_dir, exist_ok=True)
        gz_path = os.path.join(tmp_dir, f"{function_name}.py.gz")

        with open(function_file_path, "rb") as f_in:
            with gzip.open(gz_path, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)

        os.chdir(tmp_dir)
        print(f"Uploading function '{function_name}' from: {gz_path}")
        func_details = client.repository.store_function(gz_path, function_meta)
        print(f"Upload successful - id: {func_details.get('metadata').get('id')}")
        return func_details
    finally:
        os.chdir(original_dir)


def main():
    parser = argparse.ArgumentParser(
        description="Upload a deployable Python function to IBM watsonx.ai"
    )
    parser.add_argument(
        "--folder_path",
        required=True,
        help="Path to the folder containing the function file",
    )
    parser.add_argument(
        "--function_file",
        default=None,
        help="Name of the .py file to upload (auto-discovers a file with a score function if omitted)",
    )
    parser.add_argument("--wx_api_key", required=True, help="IBM watsonx.ai API key")
    parser.add_argument(
        "--wx_space_id", required=True, help="IBM watsonx.ai deployment space ID"
    )
    parser.add_argument(
        "--function_name",
        default=None,
        help="Name for the deployed function (defaults to .py filename)",
    )
    parser.add_argument(
        "--software_spec_id",
        default=DEFAULT_SOFTWARE_SPEC_ID,
        help="Software specification ID",
    )
    parser.add_argument(
        "--input_schema_path",
        default=None,
        help="Filename of input schema JSON in the folder",
    )
    parser.add_argument(
        "--output_schema_path",
        default=None,
        help="Filename of output schema JSON in the folder",
    )
    parser.add_argument(
        "--requirements",
        default=None,
        help="Filename of requirements file in the folder",
    )
    parser.add_argument(
        "--wx_url", default="https://eu-de.ml.cloud.ibm.com", help="watsonx.ai URL"
    )
    parser.add_argument(
        "--wx_user",
        default=None,
        help="Username for CPD (Cloud Pak for Data) authentication",
    )
    parser.add_argument(
        "--cpd",
        action="store_true",
        help="Use CPD credentials (url + username + api_key) instead of cloud credentials",
    )

    args = parser.parse_args()

    result = upload_watsonxai_function(
        folder_path=args.folder_path,
        function_file=args.function_file,
        wx_api_key=args.wx_api_key,
        wx_space_id=args.wx_space_id,
        function_name=args.function_name,
        software_spec_id=args.software_spec_id,
        input_schema_path=args.input_schema_path,
        output_schema_path=args.output_schema_path,
        requirements=args.requirements,
        wx_url=args.wx_url,
        wx_user=args.wx_user,
        cpd=args.cpd,
    )

    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
