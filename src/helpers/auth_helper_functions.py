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


def setup_watsonxai_client(
    api_key: str,
    project_id: str = None,
    space_id: str = None,
    url: str = "https://eu-de.ml.cloud.ibm.com",
):
    """Set up a watsonx.ai Python SDK client.

    Args:
        api_key: IBM Cloud API key
        project_id: Watson Studio project ID (optional if space_id provided)
        space_id: Watson Studio space ID (optional if project_id provided)
        url: watsonx.ai service URL. Defaults to EU-DE region.

    Returns:
        APIClient: Configured watsonx.ai client instance

    Raises:
        ValueError: If neither project_id nor space_id is provided
    """
    from ibm_watsonx_ai import APIClient, Credentials

    if not project_id and not space_id:
        raise ValueError("Either project_id or space_id must be provided")
    if project_id and space_id:
        print("Warning: Both project_id and space_id provided. Using project_id only.")

    wx_credentials = Credentials(url=url, api_key=api_key)
    client_args = {"project_id": project_id} if project_id else {"space_id": space_id}
    wxai_client = APIClient(wx_credentials, **client_args)

    return wxai_client


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


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python auth_helper_functions.py <command> [args]")
        print("\nAvailable commands:")
        print("  get_iam_token <api_key>")
        print("  auth_iam_token <api_key>")
        print("  setup_watsonxai_client <api_key> <project_id> [url]")
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

    elif command == "setup_watsonxai_client":
        if len(sys.argv) < 4:
            print("Error: api_key and project_id required")
            sys.exit(1)
        api_key = sys.argv[2]
        project_id = sys.argv[3]
        url = sys.argv[4] if len(sys.argv) > 4 else "https://eu-de.ml.cloud.ibm.com"
        client = setup_watsonxai_client(api_key, project_id=project_id, url=url)
        print("\nWatsonx.ai client created successfully")
        print(f"Project ID: {project_id}")

    elif command == "generate_zen_auth_header":
        if len(sys.argv) < 4:
            print("Error: username and api_key required")
            sys.exit(1)
        header = generate_zen_auth_header(sys.argv[2], sys.argv[3])
        print(f"\nZen Auth Header: {header}")

    else:
        print(f"Error: Unknown command '{command}'")
        sys.exit(1)
