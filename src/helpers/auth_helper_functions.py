# ================================================================================================================================================================
# Auth Helper Functions for IBM Platforms developed for the EMEA - IBM Build Engineering team by Milan Mrdenovic (milan.mrdenovic@ibm.com)
# Version: 1.1
# Date: 05.02.2026
# License: Apache 2.0 - https://www.apache.org/licenses/LICENSE-2.0
# Provides support for: inference_helper_functions.py, nosql_database_helper_functions.py, image_helper_functions.py, data_validation_helper_functions.py
# ================================================================================================================================================================
# Libraries: ibm-cloud-sdk-core, certifi, requests


import sys


def get_iam_token(api_key, only_token=True):
    """Get IBM Cloud IAM token using an HTTP request.

    Args:
        api_key: IBM Cloud API key
        only_token: If True, return only the access token string.
                    If False, return the full response object.

    Returns:
        str or Response: Access token string if only_token=True,
                        otherwise the full response object.
    """
    import requests
    import certifi

    token_response = requests.post(
        "https://iam.cloud.ibm.com/identity/token",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
            "apikey": api_key,
        },
        verify=certifi.where(),
    )
    print(token_response)

    if only_token:
        return token_response.json().get("access_token")
    else:
        return token_response


def auth_iam_token(api_key, only_token=True):
    """Get IBM Cloud IAM token using the IBM Cloud SDK.

    Args:
        api_key: IBM Cloud API key
        only_token: If True, return only the access token string.
                    If False, return the full token response dict.

    Returns:
        str or dict: Access token string if only_token=True,
                    otherwise the full token response dictionary.
    """
    from ibm_cloud_sdk_core.authenticators import IAMAuthenticator

    authenticator = IAMAuthenticator(api_key)
    token_response = authenticator.token_manager.request_token()

    if only_token:
        return token_response.get("access_token")
    else:
        return token_response


def generate_zen_auth_header(username, api_key):
    """Generate a Zen API authorization header.

    Args:
        username: Zen username
        api_key: Zen API key

    Returns:
        str: Authorization header value in format "ZenApiKey <encoded_credentials>"
    """
    import base64

    credentials = f"{username}:{api_key}"
    encoded = base64.b64encode(credentials.encode()).decode()

    return f"ZenApiKey {encoded}"


def get_wxo_token(
    api_key: str,
    instance_url: str = None,
    auth_type: str = "ibm_iam",
    iam_url: str = None,
    username: str = None,
    password: str = None,
) -> str:
    """Get a WXO bearer token, mirroring the ADK CLI auth flow.

    Corresponds to:
        orchestrate env add -n <name> -u <instance_url> --type <auth_type>
        orchestrate env activate <name> --api-key <api_key>

    Auth types:
        "ibm_iam"  (default) - IBM Cloud IAM; for .cloud.ibm.com instances.
        "mcsp"               - MCSP v1, falls back to v2; for orchestrate.ibm.com instances.
        "mcsp_v2"            - MCSP v2 explicit; requires instance_url with "instances/<id>".
        "cpd"                - Cloud Pak for Data (on-prem); requires username + api_key or password.

    Args:
        api_key:       WXO / IBM Cloud API key (--api-key).
        instance_url:  WXO service-instance URL (--url). Required for mcsp_v2 and cpd.
        auth_type:     One of "ibm_iam", "mcsp", "mcsp_v2", "cpd". Defaults to "ibm_iam".
        iam_url:       Optional override for the IAM/auth endpoint.
        username:      CPD username (cpd only).
        password:      CPD password (cpd only; mutually exclusive with api_key).

    Returns:
        str: Raw JWT access token (no "Bearer " prefix).

    Raises:
        ValueError: On invalid auth_type or missing required arguments.
    """
    auth_type = auth_type.lower()

    if auth_type == "ibm_iam":
        from ibm_cloud_sdk_core.authenticators import IAMAuthenticator

        kwargs = {"apikey": api_key}
        if iam_url:
            kwargs["url"] = iam_url
        authenticator = IAMAuthenticator(**kwargs)
        return authenticator.token_manager.get_token()

    elif auth_type == "mcsp":
        from ibm_cloud_sdk_core.authenticators import (
            MCSPAuthenticator,
            MCSPV2Authenticator,
        )

        try:
            url = iam_url or "https://iam.platform.saas.ibm.com"
            authenticator = MCSPAuthenticator(apikey=api_key, url=url)
            return authenticator.token_manager.get_token()
        except Exception:
            url = iam_url or "https://account-iam.platform.saas.ibm.com"
            instance_id = instance_url.split("instances/")[1]
            authenticator = MCSPV2Authenticator(
                apikey=api_key,
                url=url,
                scope_collection_type="services",
                scope_id=instance_id,
            )
            return authenticator.token_manager.get_token()

    elif auth_type == "mcsp_v2":
        from ibm_cloud_sdk_core.authenticators import MCSPV2Authenticator

        if not instance_url:
            raise ValueError("instance_url is required for mcsp_v2 auth.")
        url = iam_url or "https://account-iam.platform.saas.ibm.com"
        instance_id = instance_url.split("instances/")[1]
        authenticator = MCSPV2Authenticator(
            apikey=api_key,
            url=url,
            scope_collection_type="services",
            scope_id=instance_id,
        )
        return authenticator.token_manager.get_token()

    elif auth_type == "cpd":
        from ibm_cloud_sdk_core.authenticators import CloudPakForDataAuthenticator

        if not instance_url:
            raise ValueError("instance_url is required for cpd auth.")
        if not username:
            raise ValueError("username is required for cpd auth.")
        if api_key and password:
            raise ValueError(
                "Provide either api_key or password for cpd auth, not both."
            )
        if not api_key and not password:
            raise ValueError("Either api_key or password is required for cpd auth.")
        cpd_iam_url = iam_url or f"{instance_url.split('/orchestrate')[0]}/icp4d-api"
        authenticator = CloudPakForDataAuthenticator(
            username=username,
            password=password or None,
            apikey=api_key or None,
            url=cpd_iam_url,
            disable_ssl_verification=True,
        )
        return authenticator.token_manager.get_token()

    else:
        raise ValueError(
            f"Unsupported auth_type '{auth_type}'. Choose from: ibm_iam, mcsp, mcsp_v2, cpd."
        )


def build_wxo_call_meta(
    instance_url: str,
    token: str = None,
    is_local: bool = False,
    api_version: str = "v1",
    append_orchestrate: bool = True,
    is_onprem: bool = False,
    onprem_host: str = None,
    onprem_port: str = None,
    onprem_namespace: str = None,
    onprem_instance_id: str = None,
    zen_username: str = None,
    zen_api_key: str = None,
) -> dict:
    """Build the base URL and Authorization header for WXO REST calls.

    Mirrors the ADK's BaseAPIClient setup: appends "/v1/orchestrate" for remote
    instances or "/v1" for local Developer Edition servers, and formats the
    bearer token header.

    For on-premises deployments, the base URL is constructed as:
        https://{onprem_host}:{port}/orchestrate/{namespace}/instances/{instanceid}/v1
    and the Authorization header uses the Zen API key scheme.

    Args:
        instance_url:        WXO service-instance URL (trailing slash stripped).
                            Not used when is_onprem=True.
        token:               Raw JWT bearer token from get_wxo_token(). Not used
                            when is_onprem=True (Zen API key is used instead).
        is_local:            True when targeting a local Developer Edition server
                            (localhost / 127.0.0.1 / etc.).
        api_version:         Version of the API (currently v1 or v2) for different calls.
        append_orchestrate:  When True (default), appends "/orchestrate" to the base URL
                            for remote instances. Set to False for endpoints that do not
                            use the /orchestrate path segment. Ignored when is_onprem=True.
        is_onprem:           True when targeting an on-premises IBM Software Hub deployment.
                            When True, onprem_host, onprem_namespace, onprem_instance_id,
                            zen_username, and zen_api_key are required.
        onprem_host:         Hostname or IP of the IBM Software Hub cluster
                            (e.g. "api.example.com" or "cpd.example.com:31843").
        onprem_port:         Optional port number. Can also be embedded in onprem_host.
        onprem_namespace:    Namespace where the WXO instance is deployed.
        onprem_instance_id:  Unique identifier of the WXO instance (the number after
                            "orchestrate-" in the instance details URL).
        zen_username:        IBM Software Hub username for Zen API key encoding.
        zen_api_key:         IBM Software Hub API key for Zen API key encoding.

    Returns:
        dict with keys:
            "base_url" - versioned API base URL (str)
            "headers"  - {"Authorization": "Bearer <token>"} or
                        {"Authorization": "ZenApiKey <encoded>"} (dict)

    Raises:
        ValueError: When is_onprem=True and required on-prem arguments are missing,
                    or when is_onprem=False and token is not provided.
    """
    if is_onprem:
        if not all(
            [
                onprem_host,
                onprem_namespace,
                onprem_instance_id,
                zen_username,
                zen_api_key,
            ]
        ):
            raise ValueError(
                "is_onprem=True requires: onprem_host, onprem_namespace, "
                "onprem_instance_id, zen_username, and zen_api_key."
            )
        host = onprem_host.rstrip("/")
        if onprem_port and ":" not in host:
            host = f"{host}:{onprem_port}"
        base_url = (
            f"https://{host}/orchestrate/{onprem_namespace}"
            f"/instances/{onprem_instance_id}/{api_version}"
        )
        auth_header = generate_zen_auth_header(zen_username, zen_api_key)
        return {
            "base_url": base_url,
            "headers": {"Authorization": auth_header},
        }

    if token is None:
        raise ValueError("token is required when is_onprem=False.")

    base = instance_url.rstrip("/")
    if is_local or not append_orchestrate:
        base_url = f"{base}/{api_version}"
    else:
        base_url = f"{base}/{api_version}/orchestrate"
    return {
        "base_url": base_url,
        "headers": {"Authorization": f"Bearer {token}"},
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python auth_helper_functions.py <command> [args]")
        print("\nAvailable commands:")
        print("  get_iam_token <api_key>")
        print("  auth_iam_token <api_key>")
        print("  generate_zen_auth_header <username> <api_key>")
        sys.exit(1)

    command = sys.argv[1]

    if command == "get_iam_token":
        if len(sys.argv) < 3:
            print("Error: api_key required")
            sys.exit(1)
        token = get_iam_token(sys.argv[2])
        print(f"\nIAM Token: {token}")

    elif command == "auth_iam_token":
        if len(sys.argv) < 3:
            print("Error: api_key required")
            sys.exit(1)
        token = auth_iam_token(sys.argv[2])
        print(f"\nIAM Token: {token}")

    elif command == "generate_zen_auth_header":
        if len(sys.argv) < 4:
            print("Error: username and api_key required")
            sys.exit(1)
        header = generate_zen_auth_header(sys.argv[2], sys.argv[3])
        print(f"\nZen Auth Header: {header}")

    else:
        print(f"Error: Unknown command '{command}'")
        sys.exit(1)
