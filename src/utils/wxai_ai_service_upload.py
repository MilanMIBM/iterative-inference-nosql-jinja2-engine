"""
Upload a deployable AI service to IBM watsonx.ai.

Usage as module:
    python -m utils.sw_compatible.wxai_ai_service_upload \
        --folder_path ./my_ai_service_folder \
        --ai_service_file service.py \
        --wx_api_key <key> \
        --wx_space_id <space_id>

Usage as module (CPD):
    python -m utils.sw_compatible.wxai_ai_service_upload \
        --folder_path ./my_ai_service_folder \
        --ai_service_file service.py \
        --wx_api_key <key> \
        --wx_space_id <space_id> \
        --wx_user <username> \
        --wx_url <cpd-url> \
        --cpd

Usage as callable script:
    python src/utils/sw_compatible/wxai_ai_service_upload.py \
        --folder_path ./my_ai_service_folder \
        --ai_service_file service.py \
        --wx_api_key <key> \
        --wx_space_id <space_id>

Usage as callable script (CPD):
    python src/utils/sw_compatible/wxai_ai_service_upload.py \
        --folder_path ./my_ai_service_folder \
        --ai_service_file service.py \
        --wx_api_key <key> \
        --wx_space_id <space_id> \
        --wx_user <username> \
        --wx_url <cpd-url> \
        --cpd
"""

import argparse
import ast
import gzip
import json
import os
import re
import shutil
import uuid

from ibm_watsonx_ai import APIClient, Credentials

GENAI_SOFTWARE_SPEC_ID = "60ddf4d9-65ac-562d-aa8d-9f26da5dfc76"  # genai-A25-py3.12
RUNTIME_SOFTWARE_SPEC_ID = "f47ae1c3-198e-5718-b59d-2ea471561e9e"  # runtime-25.1-py3.12


def _detect_documentation_functions(file_path):
    """
    Parse a Python AI service file and detect which of generate, generate_stream,
    and generate_batch are present and functional (have a return/yield without
    only raising errors).

    A function is flagged True if it exists and contains at least one return or
    yield statement that is not exclusively inside a raise statement.
    It is flagged False if it is absent, contains no return/yield, or only raises.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        source = f.read()

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {"generate": False, "generate_stream": False, "generate_batch": False}

    def _has_return_or_yield(func_node):
        for node in ast.walk(func_node):
            if isinstance(node, (ast.Return, ast.Yield, ast.YieldFrom)):
                # Exclude bare `return` with no value (same as return None - still valid)
                return True
        return False

    def _only_raises(func_node):
        """True if the function body consists of nothing but a raise (and optional docstring)."""
        stmts = [
            s
            for s in func_node.body
            if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant))
        ]
        return len(stmts) == 1 and isinstance(stmts[0], ast.Raise)

    target_names = {"generate", "generate_stream", "generate_batch"}
    found = {}

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in target_names:
            if _only_raises(node):
                found[node.name] = False
            else:
                found[node.name] = _has_return_or_yield(node)

    result = {
        name: found.get(name, False)
        for name in ("generate", "generate_stream", "generate_batch")
    }
    print(f"Detected DOCUMENTATION_FUNCTIONS: {result}")
    return result


def upload_watsonxai_ai_service(
    folder_path,
    ai_service_file=None,
    wx_api_key=None,
    wx_space_id=None,
    ai_service_name=None,
    software_spec_id=None,
    use_genai_spec=True,
    request_documentation_path=None,
    response_documentation_path=None,
    requirements=None,
    wx_url="https://eu-de.ml.cloud.ibm.com",
    wx_user=None,
    cpd=False,
):
    """
    Uploads a Python AI service to watsonx.ai as a deployable asset.

    Parameters:
        folder_path (str): Path to the folder containing the AI service file and optional schemas.
        ai_service_file (str, optional): Name of the .py file to upload (e.g. "my_service.py").
            If not provided, auto-discovers the first .py file in the folder that returns
            a generate function (e.g. "return generate" or "def generate").
        wx_api_key (str): IBM watsonx.ai API key.
        wx_space_id (str): IBM watsonx.ai deployment space ID.
        ai_service_name (str, optional): Name for the deployed AI service. If not provided,
            defaults to the .py filename without extension.
        software_spec_id (str, optional): Explicit software specification ID. If provided,
            overrides use_genai_spec and requirements are ignored.
        use_genai_spec (bool, optional): If True (default), uses "genai-A25-py3.12"
            (60ddf4d9-65ac-562d-aa8d-9f26da5dfc76). If False, uses "runtime-25.1-py3.12"
            (f47ae1c3-198e-5718-b59d-2ea471561e9e). Ignored if software_spec_id is provided.
        request_documentation_path (str, optional): Filename of the request documentation JSON in the folder.
            If not provided, auto-discovers a JSON file containing "request" in its name.
        response_documentation_path (str, optional): Filename of the response documentation JSON in the folder.
            If not provided, auto-discovers a JSON file containing "response" in its name.
        requirements (str, optional): Filename of a requirements file in the folder.
            If not provided, auto-discovers "requirements.txt" in the folder. If found and
            software_spec_id is the default, creates a custom package extension and software spec.
        wx_url (str, optional): watsonx.ai URL. Defaults to "https://eu-de.ml.cloud.ibm.com".
        wx_user (str, optional): Username for CPD (Cloud Pak for Data) authentication.
        cpd (bool, optional): If True, uses CPD credentials (url + username + api_key).
            Also triggered automatically when wx_user is provided.

    Returns:
        dict: Details of the uploaded AI service.
    """
    # --- Resolve software spec ---
    if software_spec_id is None:
        base_spec_id = (
            GENAI_SOFTWARE_SPEC_ID if use_genai_spec else RUNTIME_SOFTWARE_SPEC_ID
        )
    else:
        base_spec_id = software_spec_id

    # --- Resolve paths ---
    folder_path = os.path.abspath(folder_path)

    # Auto-discover AI service file if not provided
    if ai_service_file is None:
        generate_pattern = re.compile(
            r"(?:def\s+generate\b|return\s+generate)", re.MULTILINE
        )
        for f in sorted(os.listdir(folder_path)):
            if not f.endswith(".py"):
                continue
            with open(os.path.join(folder_path, f), "r", encoding="utf-8") as fh:
                if generate_pattern.search(fh.read()):
                    ai_service_file = f
                    print(f"Auto-discovered AI service file: {ai_service_file}")
                    break
        if ai_service_file is None:
            raise FileNotFoundError(
                f"No .py file with a generate function found in: {folder_path}"
            )

    ai_service_file_path = os.path.join(folder_path, ai_service_file)
    if not os.path.isfile(ai_service_file_path):
        raise FileNotFoundError(f"AI service file not found: {ai_service_file_path}")

    # --- Determine ai_service_name from the .py filename if not provided ---
    if not ai_service_name:
        ai_service_name = os.path.splitext(ai_service_file)[0]

    # --- Auto-discover files ---
    folder_files = os.listdir(folder_path)

    def _find_file(keyword, extension=".json"):
        matches = [
            f for f in folder_files if f.endswith(extension) and keyword in f.lower()
        ]
        return matches[0] if matches else None

    if request_documentation_path is None:
        request_documentation_path = _find_file("request")
    if response_documentation_path is None:
        response_documentation_path = _find_file("response")

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

    # --- Load documentation schemas ---
    def _load_schema(path):
        with open(path, "r") as f:
            data = json.load(f)
        return data[0] if isinstance(data, list) else data

    request_documentation = None
    response_documentation = None
    if request_documentation_path:
        request_documentation = _load_schema(
            os.path.join(folder_path, request_documentation_path)
        )
    if response_documentation_path:
        response_documentation = _load_schema(
            os.path.join(folder_path, response_documentation_path)
        )

    # --- Initialize watsonx.ai client ---
    if cpd or wx_user:
        wx_credentials = Credentials(url=wx_url, username=wx_user, api_key=wx_api_key)
    else:
        wx_credentials = Credentials(url=wx_url, api_key=wx_api_key)
    client = APIClient(wx_credentials)
    client.set.default_space(wx_space_id)
    print(f"watsonx.ai client targeting deployment space: {wx_space_id}")

    # --- Create custom package extension + software spec if requirements found and using default spec ---
    use_spec_id = base_spec_id
    if requirements_file_path and software_spec_id is None:
        spec_suffix = str(uuid.uuid4())[:4]

        # Upload package extension
        pe_suffix = f"_pkg_{spec_suffix}"
        pe_base = ai_service_name[: 36 - len(pe_suffix)]
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
        ss_base = ai_service_name[: 36 - len(ss_suffix)]
        ss_metadata = {
            client.software_specifications.ConfigurationMetaNames.NAME: f"{ss_base}{ss_suffix}",
            client.software_specifications.ConfigurationMetaNames.BASE_SOFTWARE_SPECIFICATION: {
                "guid": base_spec_id
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

    # --- Build AI service metadata ---
    ai_service_meta = {
        client.repository.AIServiceMetaNames.NAME: ai_service_name[:36],
        client.repository.AIServiceMetaNames.SOFTWARE_SPEC_ID: use_spec_id,
    }

    if request_documentation is not None:
        ai_service_meta[client.repository.AIServiceMetaNames.DOCUMENTATION_REQUEST] = (
            request_documentation
        )
    if response_documentation is not None:
        ai_service_meta[client.repository.AIServiceMetaNames.DOCUMENTATION_RESPONSE] = (
            response_documentation
        )

    doc_functions = _detect_documentation_functions(ai_service_file_path)
    ai_service_meta[client.repository.AIServiceMetaNames.DOCUMENTATION_FUNCTIONS] = (
        doc_functions
    )

    # --- Gzip the AI service file and upload ---
    original_dir = os.getcwd()
    try:
        tmp_dir = "/tmp/notebook_ai_services"
        os.makedirs(tmp_dir, exist_ok=True)
        gz_path = os.path.join(tmp_dir, f"{ai_service_name}.py.gz")

        with open(ai_service_file_path, "rb") as f_in:
            with gzip.open(gz_path, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)

        os.chdir(tmp_dir)
        print(f"Uploading AI service '{ai_service_name}' from: {gz_path}")
        ai_service_details = client.repository.store_ai_service(
            gz_path, ai_service_meta
        )
        print(f"Upload successful - id: {ai_service_details.get('metadata').get('id')}")
        return ai_service_details
    finally:
        os.chdir(original_dir)


def main():
    parser = argparse.ArgumentParser(
        description="Upload a deployable AI service to IBM watsonx.ai"
    )
    parser.add_argument(
        "--folder_path",
        required=True,
        help="Path to the folder containing the AI service file",
    )
    parser.add_argument(
        "--ai_service_file",
        default=None,
        help="Name of the .py file to upload (auto-discovers a file with a generate function if omitted)",
    )
    parser.add_argument("--wx_api_key", required=True, help="IBM watsonx.ai API key")
    parser.add_argument(
        "--wx_space_id", required=True, help="IBM watsonx.ai deployment space ID"
    )
    parser.add_argument(
        "--ai_service_name",
        default=None,
        help="Name for the deployed AI service (defaults to .py filename)",
    )
    parser.add_argument(
        "--software_spec_id",
        default=None,
        help="Explicit software specification ID (overrides --use_runtime_spec)",
    )
    parser.add_argument(
        "--use_runtime_spec",
        action="store_true",
        help="Use runtime-25.1-py3.12 spec instead of the default genai-A25-py3.12",
    )
    parser.add_argument(
        "--request_documentation_path",
        default=None,
        help="Filename of request documentation JSON in the folder",
    )
    parser.add_argument(
        "--response_documentation_path",
        default=None,
        help="Filename of response documentation JSON in the folder",
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

    result = upload_watsonxai_ai_service(
        folder_path=args.folder_path,
        ai_service_file=args.ai_service_file,
        wx_api_key=args.wx_api_key,
        wx_space_id=args.wx_space_id,
        ai_service_name=args.ai_service_name,
        software_spec_id=args.software_spec_id,
        use_genai_spec=not args.use_runtime_spec,
        request_documentation_path=args.request_documentation_path,
        response_documentation_path=args.response_documentation_path,
        requirements=args.requirements,
        wx_url=args.wx_url,
        wx_user=args.wx_user,
        cpd=args.cpd,
    )

    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
