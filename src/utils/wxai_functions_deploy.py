"""
Deploy a previously uploaded function asset on IBM watsonx.ai.

Usage as module:
    python -m utils.sw_compatible.wxai_functions_deploy \
        --artifact_id <artifact_id> \
        --deployment_name my_deployment \
        --wx_api_key <key> \
        --wx_space_id <space_id>

Usage as module (CPD):
    python -m utils.sw_compatible.wxai_functions_deploy \
        --artifact_id <artifact_id> \
        --deployment_name my_deployment \
        --wx_api_key <key> \
        --wx_space_id <space_id> \
        --wx_user <username> \
        --wx_url <cpd-url> \
        --cpd

Usage as callable script:
    python src/utils/sw_compatible/wxai_functions_deploy.py \
        --artifact_id <artifact_id> \
        --deployment_name my_deployment \
        --wx_api_key <key> \
        --wx_space_id <space_id>

Usage as callable script (CPD):
    python src/utils/sw_compatible/wxai_functions_deploy.py \
        --artifact_id <artifact_id> \
        --deployment_name my_deployment \
        --wx_api_key <key> \
        --wx_space_id <space_id> \
        --wx_user <username> \
        --wx_url <cpd-url> \
        --cpd
"""

import argparse
import json
import uuid

from ibm_watsonx_ai import APIClient, Credentials

DEFAULT_HARDWARE_SPEC_ID = "e7ed1d6c-2e89-42d7-aed5-863b972c1d2b"


def deploy_watsonxai_function(
    artifact_id,
    deployment_name=None,
    wx_api_key=None,
    wx_space_id=None,
    deployment_type="online",
    hardware_spec_id=DEFAULT_HARDWARE_SPEC_ID,
    auto_assign_serving_name=True,
    wx_url="https://eu-de.ml.cloud.ibm.com",
    wx_user=None,
    cpd=False,
):
    """
    Deploys a function asset to watsonx.ai.

    Parameters:
        artifact_id (str): ID of the function artifact to deploy.
        deployment_name (str, optional): Name for the deployment. If not provided,
            derived from the asset name (lowercased, spaces/hyphens replaced with underscores).
        wx_api_key (str): IBM watsonx.ai API key.
        wx_space_id (str): IBM watsonx.ai deployment space ID.
        deployment_type (str): Type of deployment - "online" or "batch".
            Defaults to "online".
        hardware_spec_id (str): ID of the hardware specification for the deployment.
            Defaults to "e7ed1d6c-2e89-42d7-aed5-863b972c1d2b" ("S" - 2vCPU/8GB Ram).
        auto_assign_serving_name (bool): Automatically assigns a serving name to online
            deployments based on the deployment_name. Defaults to True.
        wx_url (str): watsonx.ai URL. Defaults to "https://eu-de.ml.cloud.ibm.com".
        wx_user (str, optional): Username for CPD (Cloud Pak for Data) authentication.
        cpd (bool, optional): If True, uses CPD credentials (url + username + api_key).
            Also triggered automatically when wx_user is provided.

    Returns:
        dict: Details of the deployed function, or None on failure.
    """
    if not artifact_id:
        print("Error: No artifact ID provided. Please upload a function first.")
        return None

    # --- Initialize watsonx.ai client ---
    if cpd or wx_user:
        wx_credentials = Credentials(url=wx_url, username=wx_user, api_key=wx_api_key)
    else:
        wx_credentials = Credentials(url=wx_url, api_key=wx_api_key)
    client = APIClient(wx_credentials)
    client.set.default_space(wx_space_id)
    print(f"watsonx.ai client targeting deployment space: {wx_space_id}")

    # --- Derive deployment_name from asset if not provided ---
    if not deployment_name:
        asset_details = client.repository.get_details(artifact_id)
        asset_name = asset_details.get("metadata", {}).get("name", artifact_id)
        suffix = uuid.uuid4().hex[:4]
        deployment_name = (
            f"{asset_name.lower().replace(' ', '_').replace('-', '_')}_{suffix}"
        )
        print(f"Derived deployment name from asset: {deployment_name}")

    # --- Build deployment properties ---
    if deployment_type == "online" and auto_assign_serving_name:
        deployment_props = {
            client.deployments.ConfigurationMetaNames.NAME: str(deployment_name)[:36],
            client.deployments.ConfigurationMetaNames.ONLINE: {},
            client.deployments.ConfigurationMetaNames.HARDWARE_SPEC: {
                "id": hardware_spec_id
            },
            client.deployments.ConfigurationMetaNames.SERVING_NAME: str(
                deployment_name
            )[:36],
        }
    elif deployment_type == "online":
        deployment_props = {
            client.deployments.ConfigurationMetaNames.NAME: str(deployment_name)[:36],
            client.deployments.ConfigurationMetaNames.ONLINE: {},
            client.deployments.ConfigurationMetaNames.HARDWARE_SPEC: {
                "id": hardware_spec_id
            },
        }
    else:  # batch / runnable job
        deployment_props = {
            client.deployments.ConfigurationMetaNames.NAME: str(deployment_name)[:36],
            client.deployments.ConfigurationMetaNames.BATCH: {},
            client.deployments.ConfigurationMetaNames.HARDWARE_SPEC: {
                "id": hardware_spec_id
            },
        }

    # --- Deploy ---
    try:
        print(f"Deployment properties: {deployment_props}")
        asset_details = client.repository.get_details(artifact_id)
        print(
            f"Asset found: {asset_details.get('metadata').get('name')} "
            f"with ID: {asset_details.get('metadata').get('id')}"
        )

        deployed_function = client.deployments.create(artifact_id, deployment_props)
        print(f"Deployment created from asset: {artifact_id}")
        return deployed_function
    except Exception as e:
        if (
            "serving_name" in str(e).lower()
            and client.deployments.ConfigurationMetaNames.SERVING_NAME
            in deployment_props
        ):
            print("Serving name conflict detected, retrying without serving name...")
            del deployment_props[client.deployments.ConfigurationMetaNames.SERVING_NAME]
            try:
                deployed_function = client.deployments.create(
                    artifact_id, deployment_props
                )
                return deployed_function
            except Exception as retry_e:
                print(f"Deployment error on retry: {str(retry_e)}")
                return None
        print(f"Deployment error: {str(e)}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Deploy a function asset on IBM watsonx.ai"
    )
    parser.add_argument(
        "--artifact_id", required=True, help="ID of the uploaded function artifact"
    )
    parser.add_argument(
        "--deployment_name",
        default=None,
        help="Name for the deployment (derived from asset name if omitted)",
    )
    parser.add_argument("--wx_api_key", required=True, help="IBM watsonx.ai API key")
    parser.add_argument(
        "--wx_space_id", required=True, help="IBM watsonx.ai deployment space ID"
    )
    parser.add_argument(
        "--deployment_type",
        default="online",
        choices=["online", "batch"],
        help="Type of deployment (default: online)",
    )
    parser.add_argument(
        "--hardware_spec_id",
        default=DEFAULT_HARDWARE_SPEC_ID,
        help="Hardware specification ID (default: S - 2vCPU/8GB Ram)",
    )
    parser.add_argument(
        "--no_serving_name",
        action="store_true",
        help="Do not auto-assign a serving name for online deployments",
    )
    parser.add_argument(
        "--wx_url",
        default="https://eu-de.ml.cloud.ibm.com",
        help="watsonx.ai URL",
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

    result = deploy_watsonxai_function(
        artifact_id=args.artifact_id,
        deployment_name=args.deployment_name,
        wx_api_key=args.wx_api_key,
        wx_space_id=args.wx_space_id,
        deployment_type=args.deployment_type,
        hardware_spec_id=args.hardware_spec_id,
        auto_assign_serving_name=not args.no_serving_name,
        wx_url=args.wx_url,
        wx_user=args.wx_user,
        cpd=args.cpd,
    )

    if result:
        print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
