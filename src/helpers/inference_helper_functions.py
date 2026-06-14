# ================================================================================================================================================================
# Inference Helper Functions developed for the EMEA - IBM Build Engineering team by Milan Mrdenovic (milan.mrdenovic@ibm.com)
# Version: 1.3
# Date: 13.05.2026
# License: Apache 2.0 - https://www.apache.org/licenses/LICENSE-2.0
# Supported providers - IBM watsonx.ai, IBM watsonx.orchestrate , Red Hat AI inference on IBM Cloud, OpenAI SDK compatible providers, IBM Consulting Advantage
# ================================================================================================================================================================
# Libraries: ibm-watsonx-ai, ibm-cloud-sdk-core, openai, certifi, requests

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional
import requests
import certifi

# Helper function imports:
from src.helpers.auth_helper_functions import get_wxo_token, build_wxo_call_meta
#

# ---------------------------------------------------------------------------
# Client initialisation
# ---------------------------------------------------------------------------


def initialize_inference_client(
    provider: str,
    api_key: str,
    # watsonx
    url: str = "",
    project_id: str = "",
    space_id: str = "",
    model_id: str = "",
    params: Optional[Dict[str, Any]] = None,
    # openai-compatible / rhai
    base_url: str = "",
    # rhai (builds base_url from these if base_url not given)
    project: str = "",
    region: str = "us-east",
    # wxo
    instance_url: str = "",
    auth_type: str = "ibm_iam",
    is_local: bool = False,
    api_version: str = "v1",
    **kwargs: Any,
):
    """
    Initialise an inference client for any supported provider.

    Parameters
    ----------
    provider:
        One of "watsonx", "openai", "rhai", "wxo", "ica".
    api_key:
        IBM Cloud API key shared across all IBM providers (WX_API_KEY /
        IBM_CLOUD_API_KEY / WXO_API_KEY). For ICA pass ICA_API_KEY. For
        generic OpenAI endpoints pass the endpoint-specific key here.

    watsonx-specific
    ----------------
    url:        watsonx.ai service URL.
    project_id: Watson Studio project ID (takes precedence over space_id).
    space_id:   Watson Studio deployment space ID.
    model_id:   Model to wrap in a ModelInference object.
    params:     Generation params passed to ModelInference.

    openai / rhai / ica-specific
    ----------------------------
    base_url:   Full OpenAI-compatible base URL.
                - rhai: built automatically from project + region if omitted.
                - ica: defaults to https://api.nextgen-beta.ica.ibm.com/ica/v1/chat-models
                        if omitted; override via ICA_BASE_URL env var.
    project:    RHAI project ID (rhai only).
    region:     RHAI region, default "us-east" (rhai only).

    wxo-specific
    ------------
    instance_url: WXO service-instance URL.
    auth_type:    One of:
                    "ibm_iam" (default) - IBM Cloud
                    "cpd" - IBM watsonx orchestrate software (cloud pak for data),
                    "mcsp",
                    "mcsp_v2"
    is_local:     True when targeting a local Developer Edition server.
    api_version:  WXO API version, default "v1".

    Returns
    -------
    - watsonx:       ibm_watsonx_ai.foundation_models.ModelInference (when model_id given)
                    or ibm_watsonx_ai.APIClient (when model_id omitted).
    - openai / rhai / ica: openai.OpenAI client instance.
    - wxo:           dict {"base_url": str, "headers": dict} for REST calls.
    - None if required credentials are missing.
    """
    provider = provider.strip().lower()

    if provider == "ica":
        if not api_key:
            print(
                "initialize_inference_client (ica): api_key is required. Returning None."
            )
            return None
        _base_url = (
            base_url or "https://api.nextgen-beta.ica.ibm.com/ica/v1/chat-models"
        )
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=_base_url, **kwargs)
        print(f"ICA client initialised with base_url: {_base_url}")
        return client

    if provider == "watsonx":
        if not (api_key and url and (project_id or space_id)):
            print(
                "initialize_inference_client (watsonx): api_key, url, and either "
                "project_id or space_id are required. Returning None."
            )
            return None

        from ibm_watsonx_ai import Credentials, APIClient

        credentials = Credentials(url=url, api_key=api_key)
        client = APIClient(credentials, **kwargs)

        if project_id:
            client.set.default_project(project_id)
            print(f"watsonx.ai client set to Project: {project_id}")
        else:
            client.set.default_space(space_id)
            print(f"watsonx.ai client set to Deployment Space: {space_id}")

        if model_id:
            from ibm_watsonx_ai.foundation_models import ModelInference

            return ModelInference(
                api_client=client,
                model_id=model_id,
                params=params or {},
            )

        return client

    if provider in ("openai", "rhai"):
        if provider == "rhai" and not base_url:
            if not (api_key and project):
                print(
                    "initialize_inference_client (rhai): api_key and project are "
                    "required. Returning None."
                )
                return None
            base_url = f"https://{region}.rhai.ibm.com/v1/projects/{project}/inference"

        if not (api_key and base_url):
            print(
                f"initialize_inference_client ({provider}): api_key and base_url "
                "are required. Returning None."
            )
            return None

        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=base_url, **kwargs)
        print(f"{provider} client initialised with base_url: {base_url}")
        return client

    if provider == "wxo":
        if not (api_key and instance_url):
            print(
                "initialize_inference_client (wxo): api_key and instance_url are "
                "required. Returning None."
            )
            return None

        token = get_wxo_token(
            api_key=api_key,
            instance_url=instance_url,
            auth_type=auth_type,
        )
        meta = build_wxo_call_meta(
            instance_url=instance_url,
            token=token,
            is_local=is_local,
            api_version=api_version,
        )
        meta["headers"]["Content-Type"] = "application/json"
        print(f"WXO client initialised - base_url: {meta['base_url']}")
        return meta

    print(
        f"initialize_inference_client: unknown provider '{provider}'. Returning None."
    )
    return None


# ---------------------------------------------------------------------------
# Model / agent listing
# ---------------------------------------------------------------------------


def get_models(
    client,
    provider: str,
) -> List[str]:
    """
    Return available model IDs for any supported provider.

    For ICA, use get_ica_models() instead if you need the creditless /
    consumptive split.

    Parameters
    ----------
    client:
        - watsonx: ibm_watsonx_ai.APIClient
        - openai / rhai / ica: openai.OpenAI client instance
        - wxo: dict returned by initialize_inference_client
    provider:
        One of "watsonx", "openai", "rhai", "wxo", "ica".

    Returns
    -------
    List of model ID strings, empty list on failure or missing client.
    """
    if client is None:
        return []

    provider = provider.strip().lower()

    try:
        if provider == "watsonx":
            import pandas as pd

            specs = client.foundation_models.get_chat_function_calling_model_specs()
            return pd.DataFrame(specs.get("resources", [])).model_id.to_list()

        if provider in ("openai", "rhai", "ica"):
            return [m.id for m in client.models.list().data]

        if provider == "wxo":
            url = f"{client['base_url']}/models/list"
            response = requests.get(
                url, headers=client["headers"], verify=certifi.where()
            )
            response.raise_for_status()
            resources = response.json().get("resources", [])
            return [m["id"] for m in resources if m.get("id")]

    except Exception as e:
        print(f"get_models ({provider}) error: {e}")

    return []


def get_ica_models(
    ica_client,
) -> Dict[str, List[str]]:
    """
    Return ICA model lists split by cost tier.

    Returns
    -------
    Dict with keys:
        "all"         - every model except advantage_assist
        "creditless"  - models with x_ica_info.cost_tier == "0x"
        "consumptive" - all minus creditless
    """
    if ica_client is None:
        return {"all": [], "creditless": [], "consumptive": []}
    try:
        import pandas as pd

        data = ica_client.models.list().to_dict().get("data", [])
        df = pd.json_normalize(data)
        all_models = sorted(
            df.query("id != 'advantage_assist.advantage-assist'")["id"].tolist()
        )
        creditless = sorted(
            df.query(
                "id != 'advantage_assist.advantage-assist' and `x_ica_info.cost_tier` == '0x'"
            )["id"].tolist()
        )
        consumptive = sorted([m for m in all_models if m not in creditless])
        return {"all": all_models, "creditless": creditless, "consumptive": consumptive}
    except Exception as e:
        print(f"get_ica_models error: {e}")
        return {"all": [], "creditless": [], "consumptive": []}


def get_wxo_agents(wxo_client: Dict[str, Any]) -> Dict[str, str]:
    """
    Return a {display_name: agent_id} mapping of agents in a WXO instance.

    Uses GET /v2/orchestrate/agents (separate from the v1 base_url).

    Parameters
    ----------
    wxo_client:
        Dict returned by initialize_inference_client for the "wxo" provider.
    """
    if not wxo_client:
        return {}
    try:
        url = f"{wxo_client['base_url']}/agents"
        response = requests.get(
            url, headers=wxo_client["headers"], verify=certifi.where()
        )
        response.raise_for_status()
        agents = response.json()
        if isinstance(agents, dict):
            agents = agents.get("resources", []) or []
        return {
            a.get("display_name") or a.get("name") or a.get("id", ""): a.get("id", "")
            for a in agents
            if a.get("id")
        }
    except Exception as e:
        print(f"get_wxo_agents error: {e}")
        return {}


# ---------------------------------------------------------------------------
# Unified single-turn chat
# ---------------------------------------------------------------------------


def run_chat_inference(
    client,
    messages: List[Dict[str, str]],
    provider: str = "watsonx",
    model_id: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
    agent_id: Optional[str] = None,
    **kwargs: Any,
) -> Optional[Dict[str, Any]]:
    """
    Run a single chat inference call and return a normalised response dict.

    All providers are normalised to the OpenAI chat-completions shape:
        {"choices": [{"message": {"role": ..., "content": ...}}], "usage": {...}}

    Parameters
    ----------
    client:
        - "watsonx": ibm_watsonx_ai ModelInference instance
        - "openai" / "rhai" / "ica": openai.OpenAI client instance
        - "wxo": dict returned by initialize_inference_client
    messages:
        List of {"role": ..., "content": ...} dicts.
    provider:
        One of "watsonx", "openai", "rhai", "wxo", "ica".
    model_id:
        Required for openai / rhai / ica; used for wxo when no agent_id is given.
    params:
        Extra generation params forwarded to the provider.
    agent_id:
        WXO agent ID (wxo provider only). Takes precedence over model_id.
    """
    if client is None or not messages:
        return None

    params = params or {}
    provider = provider.strip().lower()

    try:
        if provider == "watsonx":
            return client.chat(messages=messages, **kwargs)

        if provider == "wxo":
            base_url = client["base_url"]
            headers = client["headers"]

            if not agent_id:
                raise ValueError("run_chat_inference (wxo): agent_id is required")
            # POST /v1/orchestrate/{agent_id}/chat/completions
            url = f"{base_url}/{agent_id}/chat/completions"
            payload: Dict[str, Any] = {
                "messages": messages,
                "stream": False,
                **params,
                **kwargs,
            }
            response = requests.post(
                url, headers=headers, json=payload, verify=certifi.where()
            )
            response.raise_for_status()
            return response.json()

        # OpenAI-compatible path (openai, rhai, ica)
        if model_id is None:
            raise ValueError(f"run_chat_inference ({provider}): model_id is required")

        extra = {k: v for k, v in params.items() if k != "model_id"}
        response = client.chat.completions.create(
            model=model_id,
            messages=messages,
            **extra,
            **kwargs,
        )
        return (
            response.model_dump() if hasattr(response, "model_dump") else dict(response)
        )

    except Exception as e:
        print(f"run_chat_inference ({provider}) error: {e}")
        return None


# ---------------------------------------------------------------------------
# Iterative inference loop
# ---------------------------------------------------------------------------


def run_iterative_inference(
    client,
    messages: List[Dict[str, str]],
    number_of_iterations: int,
    provider: str = "watsonx",
    model_id: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
    agent_id: Optional[str] = None,
    continuation_message: str = "Generate Next Output.",
    on_iteration_complete: Optional[Callable[[int, Dict, List], None]] = None,
    **kwargs: Any,
) -> List[Dict[str, Any]]:
    """
    Run the iterative inference loop (provider-agnostic).

    After each assistant turn the continuation_message is appended as a user
    message so the model produces the next iteration.

    Parameters
    ----------
    client:
        Initialised client - ModelInference (watsonx), OpenAI (openai/rhai/ica),
        or dict (wxo).
    messages:
        Initial rendered message list (system + user context).
    number_of_iterations:
        How many assistant turns to generate.
    provider:
        One of "watsonx", "openai", "rhai", "wxo", "ica".
    model_id:
        Required for openai / rhai / ica; optional for wxo when agent_id is set.
    params:
        Extra generation params forwarded per call.
    agent_id:
        WXO agent ID (wxo provider only).
    continuation_message:
        User message injected between iterations.
    on_iteration_complete:
        Optional callback(iteration_index, result, current_messages) called after
        each successful assistant turn - use this to persist results to a database.

    Returns
    -------
    List of raw response dicts, one per completed iteration.
    """
    all_results: List[Dict[str, Any]] = []
    current_messages = list(messages)

    if client is None or not messages or not number_of_iterations:
        return all_results

    for i in range(number_of_iterations):
        result = run_chat_inference(
            client=client,
            messages=current_messages,
            provider=provider,
            model_id=model_id,
            params=params,
            agent_id=agent_id,
            **kwargs,
        )

        if result is None:
            break

        all_results.append(result)

        choices = result.get("choices", [])
        if not choices:
            break

        assistant_message = choices[0].get("message", {})
        current_messages.append(assistant_message)

        if on_iteration_complete:
            try:
                on_iteration_complete(i, result, current_messages)
            except Exception as e:
                print(f"on_iteration_complete callback error (iteration {i + 1}): {e}")

        if i < number_of_iterations - 1:
            current_messages.append({"role": "user", "content": continuation_message})

    return all_results


# ---------------------------------------------------------------------------
# Token aggregation
# ---------------------------------------------------------------------------


def aggregate_token_counts(
    all_inference_results: List[Dict[str, Any]],
) -> Optional[Dict[str, int]]:
    """
    Sum prompt/completion/total token counts across all iteration results.

    Returns None if no usage data is present.
    """
    if not all_inference_results:
        return None

    total_prompt = total_completion = total = 0
    has_usage = False

    for result in all_inference_results:
        usage = result.get("usage") if result else None
        if usage:
            has_usage = True
            total_prompt += usage.get("prompt_tokens", 0)
            total_completion += usage.get("completion_tokens", 0)
            total += usage.get("total_tokens", 0)

    if not has_usage:
        return None

    return {
        "prompt_tokens": total_prompt,
        "completion_tokens": total_completion,
        "total_tokens": total,
    }
