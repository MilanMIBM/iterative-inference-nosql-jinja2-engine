import marimo

__generated_with = "0.23.8"
app = marimo.App(width="full")

with app.setup:
    import marimo as mo
    import pandas as pd
    import time
    import uuid
    import os


@app.cell
def _():
    from src.helpers.inference_helper_functions import (
        initialize_inference_client,
        get_models,
        get_ica_models,
        get_wxo_agents,
        run_iterative_inference,
        # aggregate_token_counts,
    )

    return (
        get_ica_models,
        get_models,
        get_wxo_agents,
        initialize_inference_client,
        run_iterative_inference,
    )


@app.cell
def _():
    import sys

    parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

    from src.helpers.nosql_database_helper_functions import (
        initialize_cloudant_database,
        initialize_astradb_database,
        initialize_mongodb_database,
        initialize_hcd_database,
        create_iteration_document,
        update_iteration_document,
        render_jinja2_templates,
        check_database_status,
        parse_yaml_documents,
        retrieve_documents,
        upload_documents_from_mapping,
    )

    from src.utils.load_all_dotenv import (
        load_all_dotenv,
    )

    try:
        load_all_dotenv(os.path.join(parent_dir, "config"), verbose=True)
    except:  # noqa: E722
        load_all_dotenv("config", verbose=True)
    return (
        check_database_status,
        create_iteration_document,
        initialize_astradb_database,
        initialize_cloudant_database,
        initialize_hcd_database,
        initialize_mongodb_database,
        parse_yaml_documents,
        render_jinja2_templates,
        retrieve_documents,
        update_iteration_document,
        upload_documents_from_mapping,
    )


@app.cell
def _():
    # Shared inference API key - first non-empty value across all providers wins
    inference_api_key = (
        os.getenv("IBM_CLOUD_API_KEY")
        or os.getenv("WX_API_KEY")
        or os.getenv("WXO_API_KEY")
        or ""
    )
    default_chat_model = os.getenv("CHAT_MODEL", "mistralai/mistral-medium-2505")
    # watsonx.ai
    wx_project_id = os.getenv("WX_PROJECT_ID", "")
    wx_space_id = os.getenv("WX_SPACE_ID", "")
    wx_url = os.getenv("WX_URL", "https://eu-de.ml.cloud.ibm.com")
    # Red Hat AI Inference
    rhai_project = os.getenv("RHAI_INF_PROJECT", "")
    rhai_region = os.getenv("RHAI_INF_REGION", "us-east")
    rhai_default_model = os.getenv("RHAI_INF_DEFAULT_MODEL", "gpt-oss-120b")
    # watsonx Orchestrate
    wxo_instance_url = os.getenv("WXO_INSTANCE_URL", "")
    wxo_auth_type = os.getenv("WXO_AUTH_TYPE", "ibm_iam")
    # AstraDB
    astradb_api_endpoint = os.getenv("ASTRA_DB_API_ENDPOINT", "")
    astradb_application_token = os.getenv("ASTRA_DB_APPLICATION_TOKEN", "")
    astradb_keyspace = os.getenv("ASTRA_DB_KEYSPACE", "default_keyspace")
    # IBM Cloudant
    cloudant_url = os.getenv("CLOUDANT_URL", "")
    cloudant_apikey = os.getenv("CLOUDANT_APIKEY", "")
    # MongoDB
    mongodb_endpoint = os.getenv("MONGODB_ENDPOINT", "")
    mongodb_username = os.getenv("MONGODB_USERNAME", "")
    mongodb_password = os.getenv("MONGODB_PASSWORD", "")
    mongodb_cert_path = os.getenv("MONGODB_CERT_PATH", "")
    # HCD
    hcd_api_endpoint = os.getenv("DATASTAX_HCD_ENDPOINT", "")
    hcd_api_username = os.getenv("DATASTAX_HCD_API_USER", "")
    hcd_api_password = os.getenv("DATASTAX_HCD_API_PASSWORD", "")
    hcd_keyspace = os.getenv("DATASTAX_HCD_KEYSPACE", "default_keyspace")
    # IBM Consulting Advantage
    ica_api_key = os.getenv("ICA_API_KEY", "")
    ica_base_url = os.getenv(
        "ICA_BASE_URL", "https://api.nextgen-beta.ica.ibm.com/ica/v1/chat-models"
    )
    return (
        astradb_api_endpoint,
        astradb_application_token,
        astradb_keyspace,
        cloudant_apikey,
        cloudant_url,
        default_chat_model,
        hcd_api_endpoint,
        hcd_api_password,
        hcd_api_username,
        hcd_keyspace,
        ica_api_key,
        ica_base_url,
        inference_api_key,
        mongodb_cert_path,
        mongodb_endpoint,
        mongodb_password,
        mongodb_username,
        rhai_default_model,
        rhai_project,
        rhai_region,
        wx_project_id,
        wx_space_id,
        wx_url,
        wxo_auth_type,
        wxo_instance_url,
    )


@app.cell
def _(db_provider):
    db_org_context = (
        "organization_context".replace("_", "-")
        if db_provider.value == "cloudant"
        else "organization_context"
    )
    print(db_org_context)
    db_messages = (
        "generation_context".replace("_", "-")
        if db_provider.value == "cloudant"
        else "generation_context"
    )
    print(db_messages)
    db_model_params = (
        "model_parameters".replace("_", "-")
        if db_provider.value == "cloudant"
        else "model_parameters"
    )
    print(db_model_params)
    db_system_templates = (
        "system_templates".replace("_", "-")
        if db_provider.value == "cloudant"
        else "system_templates"
    )
    print(db_system_templates)
    return db_messages, db_model_params, db_org_context, db_system_templates


@app.cell
def _(cloudant_apikey, cloudant_url, initialize_cloudant_database):
    cloudant = (
        initialize_cloudant_database(cloudant_url, cloudant_apikey)
        if cloudant_url and cloudant_apikey
        else None
    )
    return (cloudant,)


@app.cell
def _(
    astradb_api_endpoint,
    astradb_application_token,
    astradb_keyspace,
    initialize_astradb_database,
):
    astradb = (
        initialize_astradb_database(
            astradb_api_endpoint, astradb_application_token, astradb_keyspace
        )
        if astradb_api_endpoint and astradb_application_token and astradb_keyspace
        else None
    )
    return (astradb,)


@app.cell
def _(
    hcd_api_endpoint,
    hcd_api_password,
    hcd_api_username,
    hcd_keyspace,
    initialize_hcd_database,
):
    hcd = (
        initialize_hcd_database(
            hcd_api_endpoint, hcd_api_username, hcd_api_password, hcd_keyspace
        )
        if hcd_api_endpoint and hcd_api_username and hcd_api_password and hcd_keyspace
        else None
    )
    return (hcd,)


@app.cell
def _(
    initialize_mongodb_database,
    mongodb_cert_path,
    mongodb_endpoint,
    mongodb_password,
    mongodb_username,
):
    mongodb = (
        initialize_mongodb_database(
            mongodb_endpoint, mongodb_username, mongodb_password, mongodb_cert_path
        )
        if mongodb_endpoint and mongodb_username and mongodb_password
        else None
    )
    return (mongodb,)


@app.cell
def _():
    inference_provider = mo.ui.dropdown(
        [
            "watsonx-ai",
            "redhat-ai-inference",
            "watsonx-orchestrate",
            "ibm-consulting-advantage",
        ],
        value="redhat-ai-inference",
        allow_select_none=False,
        label="**Select Inference Provider Backend:**",
        full_width=True,
    )
    return (inference_provider,)


@app.cell
def _():
    db_provider = mo.ui.dropdown(
        ["cloudant", "astradb", "hcd", "mongodb"],
        value="cloudant",
        allow_select_none=False,
        label="**Select Context Database Backend:**",
        full_width=True,
    )
    return (db_provider,)


@app.cell
def _(astradb, cloudant, db_provider, hcd, mongodb):
    active_db_provider = db_provider.value
    if active_db_provider == "astradb":
        active_db_client = astradb
    elif active_db_provider == "hcd":
        active_db_client = hcd
    elif active_db_provider == "mongodb":
        active_db_client = mongodb
    else:
        active_db_client = cloudant
    return active_db_client, active_db_provider


@app.cell
def _(
    ica_api_key,
    ica_base_url,
    inference_api_key,
    inference_provider,
    initialize_inference_client,
    rhai_project,
    rhai_region,
    wx_project_id,
    wx_space_id,
    wx_url,
    wxo_auth_type,
    wxo_instance_url,
):
    _p = inference_provider.value
    if _p == "watsonx-ai":
        client = initialize_inference_client(
            provider="watsonx",
            api_key=inference_api_key,
            url=wx_url,
            project_id=wx_project_id,
            space_id=wx_space_id,
        )
    elif _p == "redhat-ai-inference":
        client = initialize_inference_client(
            provider="rhai",
            api_key=inference_api_key,
            project=rhai_project,
            region=rhai_region,
        )
    elif _p == "watsonx-orchestrate":
        client = initialize_inference_client(
            provider="wxo",
            api_key=inference_api_key,
            instance_url=wxo_instance_url,
            auth_type=wxo_auth_type,
        )
    elif _p == "ibm-consulting-advantage":
        client = initialize_inference_client(
            provider="ica",
            api_key=ica_api_key,
            base_url=ica_base_url,
        )
    else:
        client = None
    return (client,)


@app.cell
def _(inference_provider):
    ica_consumptive_toggle = (
        mo.ui.switch(label="**Use consumptive models**", value=False)
        if inference_provider.value == "ibm-consulting-advantage"
        else None
    )
    return (ica_consumptive_toggle,)


@app.cell
def _(
    client,
    default_chat_model,
    get_ica_models,
    get_models,
    get_wxo_agents,
    ica_consumptive_toggle,
    inference_provider,
    rhai_default_model,
):
    _p = inference_provider.value
    if _p == "watsonx-orchestrate":
        model_options = get_wxo_agents(client) or {"No Agents To Select": None}
    elif _p == "redhat-ai-inference":
        model_options = get_models(client, provider="rhai") or [rhai_default_model]
    elif _p == "ibm-consulting-advantage":
        _ica_lists = get_ica_models(client)
        _use_consumptive = ica_consumptive_toggle and ica_consumptive_toggle.value
        model_options = (
            (
                _ica_lists["consumptive"]
                if _use_consumptive
                else _ica_lists["creditless"]
            )
            or _ica_lists["all"]
            or [default_chat_model]
        )
    else:
        model_options = get_models(client, provider="watsonx") or [default_chat_model]
    return (model_options,)


@app.cell
def _(
    active_db_client,
    active_db_provider,
    db_model_params,
    default_model_params,
    param_target,
    retrieve_documents,
):
    _model_param_results = (
        retrieve_documents(
            provider=active_db_provider,
            db_client=active_db_client,
            db_name=db_model_params,
            selectors={"parameter_set_name": {"$eq": param_target.value}},
            fields=["parameters"],
            docs_only=True,
        )
        if active_db_client is not None
        else []
    )
    model_params = next(
        (
            doc.get("parameters")
            for doc in _model_param_results
            if isinstance(doc, dict)
        ),
        default_model_params,
    )
    return (model_params,)


@app.cell
def _(default_chat_model, model_options, model_params):
    _default_model = (
        model_params.get("model_id") if model_params else default_chat_model
    )
    if isinstance(model_options, dict):
        _options_keys = list(model_options.keys())
        _selected = _options_keys[0] if _options_keys else _default_model
    else:
        _selected = (
            _default_model
            if _default_model in model_options
            else (model_options[0] if model_options else _default_model)
        )
    model_selector = mo.ui.dropdown(
        model_options or [_default_model],
        value=_selected,
        label="**Select Model/Agent Override:**",
        allow_select_none=False,
        full_width=True,
    )
    return (model_selector,)


@app.cell
def _(
    client,
    default_chat_model,
    inference_api_key,
    inference_provider,
    initialize_inference_client,
    model_params,
    model_selector,
    wx_project_id,
    wx_space_id,
    wx_url,
):
    _p = inference_provider.value
    _model_id = (
        str(model_selector.value) or model_params.get("model_id") or default_chat_model
    )
    _params = model_params.get("params")

    if client is None:
        model_inference = None
    elif _p == "watsonx-ai":
        # watsonx: ModelInference is bound to a specific model_id at init time
        model_inference = initialize_inference_client(
            provider="watsonx",
            api_key=inference_api_key,
            url=wx_url,
            project_id=wx_project_id,
            space_id=wx_space_id,
            model_id=_model_id,
            params=_params,
        )
    else:
        # rhai / wxo / ica: model_id or agent_id is passed at call time - reuse client
        model_inference = client
    return (model_inference,)


@app.cell
def _():
    ### Fallback defaults
    default_messages_template = "00000000-0000-0000-0000-000000000000"
    default_parameter_set = "mistral-medium-2505_single_generation"
    default_system_templates = "main_system_templates_marimo_v2"
    return default_parameter_set, default_system_templates, default_messages_template


@app.cell
def _():
    default_org_id = ""
    return (default_org_id,)


@app.cell
def _(default_chat_model):
    default_model_params = {
        "model_id": default_chat_model,
        "params": {
            "frequency_penalty": 0,
            "logprobs": False,
            "max_completion_tokens": 2048,
            "n": 1,
            "presence_penalty": 0,
            "response_format": {"type": "text"},
            "stop": ["</s>", "<|endoftext|>", "<|end_of_text|>"],
            "temperature": 0.7,
            "top_p": 1,
        },
    }
    return (default_model_params,)


@app.cell
def _(
    active_db_client,
    active_db_provider,
    db_model_params,
    default_parameter_set,
    inference_provider,
    retrieve_documents,
):
    def _fetch_param_targets(selectors):
        return (
            retrieve_documents(
                provider=active_db_provider,
                db_client=active_db_client,
                db_name=db_model_params,
                selectors=selectors,
                fields=["parameter_set_name", "model_provider"],
                docs_only=True,
            )
            if active_db_client is not None
            else []
        )

    _provider_filter = {
        "$and": [
            {"parameter_set_name": {"$exists": True}},
            {"model_provider": {"$eq": inference_provider.value}},
        ]
    }
    _unfiltered = {"parameter_set_name": {"$exists": True}}

    try:
        model_param_targets = _fetch_param_targets(_provider_filter)
        if not model_param_targets:
            model_param_targets = _fetch_param_targets(_unfiltered)
        if not model_param_targets:
            model_param_targets = [{"parameter_set_name": default_parameter_set}]
    except Exception:
        time.sleep(1.05)
        try:
            model_param_targets = _fetch_param_targets(_provider_filter)
            if not model_param_targets:
                model_param_targets = _fetch_param_targets(_unfiltered)
            if not model_param_targets:
                model_param_targets = [{"parameter_set_name": default_parameter_set}]
        except Exception:
            model_param_targets = [{"parameter_set_name": default_parameter_set}]

    parameter_set_names = {
        param.get("parameter_set_name") for param in model_param_targets
    }
    return (parameter_set_names,)


@app.cell
def _(default_parameter_set, parameter_set_names):
    sorted_names = sorted(parameter_set_names)
    selected_param_target = (
        default_parameter_set
        if default_parameter_set in parameter_set_names
        else (sorted_names[0] if sorted_names else None)
    )
    param_target = mo.ui.dropdown(
        sorted_names,
        value=selected_param_target,
        label="**Select Model Parameter Set:**",
        allow_select_none=not bool(sorted_names),
        full_width=True,
    )
    return (param_target,)


@app.cell
def _(
    active_db_client,
    active_db_provider,
    db_system_templates,
    default_system_templates,
    retrieve_documents,
):
    # Retrieves the system templates available
    try:
        template_types = (
            retrieve_documents(
                provider=active_db_provider,
                db_client=active_db_client,
                db_name=db_system_templates,
                selectors={"name": {"$exists": True}},
                fields=["name"],
                docs_only=True,
            )
            if active_db_client is not None
            else []
        )
        if not template_types:
            template_types = [{"name": default_system_templates}]
        template_list = [doc["name"] for doc in template_types]
    except Exception as e:  # noqa: F841
        time.sleep(1.05)
        try:
            template_types = (
                retrieve_documents(
                    provider=active_db_provider,
                    db_client=active_db_client,
                    db_name=db_system_templates,
                    selectors={"name": {"$exists": True}},
                    fields=["name"],
                    docs_only=True,
                )
                if active_db_client is not None
                else []
            )
            if not template_types:
                template_types = [{"name": default_system_templates}]
            template_list = [doc["name"] for doc in template_types]
        except Exception as retry_e:  # noqa: F841
            # Database doesn't exist or is empty, use default
            template_types = [{"name": default_system_templates}]
            template_list = [doc["name"] for doc in template_types]
    return (template_list,)


@app.cell
def _(default_system_templates, template_list):
    ### System Templates
    default_selected_template = (
        default_system_templates
        if default_system_templates in template_list
        else (template_list[0] if template_list else None)
    )
    template_selector = mo.ui.dropdown(
        template_list,
        allow_select_none=not bool(template_list),
        value=default_selected_template,
        label="**Select the System Template Variant:**",
        full_width=True,
    )
    return (template_selector,)


@app.cell
def _(template_selector):
    template_name = template_selector.value
    return (template_name,)


@app.cell
def _(
    active_db_client,
    active_db_provider,
    db_system_templates,
    retrieve_documents,
    template_name,
):
    _returned_system_templates = (
        retrieve_documents(
            provider=active_db_provider,
            db_client=active_db_client,
            db_name=db_system_templates,
            selectors={"name": {"$eq": template_name}},
            fields=["system_templates"],
            docs_only=True,
        )
        if active_db_client is not None
        else {}
    )
    system_templates = next(
        (doc.get("system_templates", {}) for doc in _returned_system_templates), {}
    )
    print(system_templates)
    return (system_templates,)


@app.cell
def _(
    active_db_client,
    active_db_provider,
    db_org_context,
    retrieve_documents,
):
    # Retrieves all organizational context samples available
    try:
        org_info = (
            retrieve_documents(
                provider=active_db_provider,
                db_client=active_db_client,
                db_name=db_org_context,
                selectors={"org_id": {"$exists": True}},
                fields=["org_id", "org_context.client_name"],
                docs_only=False,
            )
            if active_db_client is not None
            else {}
        )
        org_ids = {
            f"{org['org_context']['client_name']} ({org['org_id']})": org["org_id"]
            for org in org_info.get("docs", [])
            if org.get("org_context", {}).get("client_name")
        }
    except Exception as e:  # noqa: F841
        time.sleep(1.05)
        org_info = (
            retrieve_documents(
                provider=active_db_provider,
                db_client=active_db_client,
                db_name=db_org_context,
                selectors={"org_id": {"$exists": True}},
                fields=["org_id", "org_context.client_name"],
                docs_only=False,
            )
            if active_db_client is not None
            else {}
        )
        org_ids = {
            f"{org['org_context']['client_name']} ({org['org_id']})": org["org_id"]
            for org in org_info.get("docs", [])
            if org.get("org_context", {}).get("client_name")
        }
    return (org_ids,)


@app.cell
def _(
    active_db_client,
    active_db_provider,
    db_org_context,
    default_org_id,
    org_id_dropdown,
    retrieve_documents,
):
    organizational_context = (
        retrieve_documents(
            provider=active_db_provider,
            db_client=active_db_client,
            db_name=db_org_context,
            selectors={"org_id": {"$eq": org_id_dropdown.value or default_org_id}},
            fields=["language", "org_context"],
            docs_only=False,
        )
        if active_db_client is not None
        else {}
    )
    return (organizational_context,)


@app.cell
def _(organizational_context):
    org_specs = (
        organizational_context.get("docs")[0].get("org_context")
        if organizational_context.get("docs")
        and len(organizational_context.get("docs")) > 0
        else {}
    )
    output_language = (
        organizational_context.get("docs")[0].get("language")
        if organizational_context.get("docs")
        and len(organizational_context.get("docs")) > 0
        else "English"
    )
    return org_specs, output_language


@app.cell
def _(org_ids):
    org_id_dropdown = mo.ui.dropdown(
        org_ids,
        label="**Select the Org. Context Version:**",
        full_width=True,
    )
    return (org_id_dropdown,)


@app.cell
def _(default_org_id, org_id_dropdown):
    org_id = org_id_dropdown.value or default_org_id
    return (org_id,)


@app.cell
def _(output_language):
    output_language_editor = mo.ui.text(
        label="**Output Language** *(Loaded from template)*:",
        value=str(output_language),
        kind="text",
        max_length=100,
        full_width=True,
    )
    return (output_language_editor,)


@app.cell
def _():
    ### Number of iterations to generate
    generation_iterations_selector = mo.ui.slider(
        start=1,
        step=1,
        stop=25,
        value=3,
        label="**Select The Number of Iterations to Run:**",
        full_width=True,
        include_input=True,
        orientation="horizontal",
    )
    return (generation_iterations_selector,)


@app.cell
def _(generation_iterations_selector):
    number_of_iterations = generation_iterations_selector.value
    return (number_of_iterations,)


@app.cell
def _():
    user_spec_input = (
        mo.md(
            """
            {description}

            {goal}

            {comments}
        """
        )
        .batch(
            description=mo.ui.text_area(
                label="**Task Description**",
                max_length=500,
                value="",
                rows=4,
                full_width=True,
            ),
            goal=mo.ui.text_area(
                label="**Task Goal**",
                max_length=500,
                value="",
                rows=4,
                full_width=True,
            ),
            comments=mo.ui.text_area(
                label="**Comments**",
                max_length=500,
                value="",
                rows=4,
                full_width=True,
            ),
        )
        .form(
            show_clear_button=True,
            bordered=True,
            submit_button_label="Generate results",
            submit_button_tooltip="The form will empty out on submit, but you will see the submitted values in a new section.",
            clear_on_submit=True,
        )
    )
    return (user_spec_input,)


@app.cell
def _():
    selected_iteration_id = ""
    return (selected_iteration_id,)


@app.cell
def _():
    user_id = "e1df5a36-558d-4918-bd1f-bd2db8aeeb64" or str(uuid.uuid4())
    return (user_id,)


@app.cell
def _(
    active_db_client,
    active_db_provider,
    create_iteration_document,
    db_messages,
    number_of_iterations,
    org_id,
    output_language_editor,
    param_target,
    retrieve_documents,
    selected_iteration_id,
    template_name,
    user_id,
    user_spec_input,
):
    iteration_id = None
    iteration_doc = None

    if user_spec_input.value is not None and active_db_client is not None:
        iteration_id = selected_iteration_id or None

        if not iteration_id:
            iteration_doc = create_iteration_document(
                db_client=active_db_client,
                db_name=db_messages,
                iteration_id=selected_iteration_id or str(uuid.uuid4()),
                user_id=user_id,
                org_id=org_id,
                parameter_set_name=param_target.value,
                system_template_name=template_name,
                iteration_length=number_of_iterations,
                user_context={"user_context": user_spec_input.value},
                language=output_language_editor.value or "English",
                provider=active_db_provider,
            )
            iteration_id = iteration_doc.get("iteration_id", selected_iteration_id)

        messages_to_render = retrieve_documents(
            provider=active_db_provider,
            db_client=active_db_client,
            db_name=db_messages,
            selectors={
                "$and": [
                    {"iteration_id": {"$eq": iteration_id}},
                ]
            },
            fields=[
                "generation_content",
            ],
            docs_only=False,
        )
    else:
        messages_to_render = iteration_doc = iteration_id = None
    return (messages_to_render,)


@app.cell
def _(
    messages_to_render,
    org_specs,
    output_language_editor,
    render_jinja2_templates,
    system_templates,
    user_spec_input,
):
    language_context = (
        {"language": output_language_editor.value}
        if output_language_editor.value
        else {"language": "English"}
    )

    if user_spec_input.value:
        if isinstance(messages_to_render, dict) and messages_to_render.get("docs"):
            rendered_result = render_jinja2_templates(
                docs=messages_to_render,
                context_docs=[
                    org_specs,
                    system_templates,
                    {"user_context": user_spec_input.value},
                    language_context,
                ],
            )
            rendered_messages = (
                rendered_result.get("docs", [])
                if isinstance(rendered_result, dict)
                else rendered_result
            )
        else:
            rendered_result = render_jinja2_templates(
                docs=[{"generation_content": {"messages": []}}],
                context_docs=[
                    org_specs,
                    system_templates,
                    {"user_context": user_spec_input.value},
                    language_context,
                ],
            )
            rendered_messages = (
                rendered_result.get("docs", [])
                if isinstance(rendered_result, dict)
                else rendered_result
            )
    else:
        rendered_result = rendered_messages = []
    return (rendered_messages,)


@app.cell
def _(rendered_messages):
    messages = (
        rendered_messages[0].get("generation_content", {}).get("messages")
        if rendered_messages
        else None
    )
    return (messages,)


@app.cell
def _(
    active_db_client,
    active_db_provider,
    client,
    db_messages,
    inference_provider,
    messages,
    messages_to_render,
    model_inference,
    model_selector,
    number_of_iterations,
    parse_yaml_documents,
    run_iterative_inference,
    update_iteration_document,
):
    current_messages = messages.copy() if messages else []
    completed_generation = False
    created_iteration_id = None

    if isinstance(messages_to_render, dict):
        _iter_docs = messages_to_render.get("docs", [])
        created_iteration_id = _iter_docs[0].get("iteration_id") if _iter_docs else None

    _p = inference_provider.value
    if _p == "watsonx-ai":
        _inf_provider = "watsonx"
        _model_id = None  # baked into ModelInference at init
        _agent_id = None
    elif _p == "redhat-ai-inference":
        _inf_provider = "rhai"
        _model_id = str(model_selector.value)
        _agent_id = None
    elif _p == "watsonx-orchestrate":
        _inf_provider = "wxo"
        _model_id = None
        _agent_id = str(model_selector.value)
    elif _p == "ibm-consulting-advantage":
        _inf_provider = "ica"
        _model_id = str(model_selector.value)
        _agent_id = None
    else:
        _inf_provider = "watsonx"
        _model_id = None
        _agent_id = None

    def _on_iteration_complete(iteration_index, result, *_):
        if not (created_iteration_id and active_db_client):
            return
        assistant_message = result["choices"][0]["message"]
        raw_content = assistant_message.get("content", "")
        parsed = parse_yaml_documents(raw_content)
        if not isinstance(parsed, (dict, list)):
            parsed = []
        configs = parsed if isinstance(parsed, list) else [parsed]
        update_iteration_document(
            provider=active_db_provider,
            db_client=active_db_client,
            db_name=db_messages,
            iteration_id=created_iteration_id,
            new_messages=[assistant_message],
            new_results=[
                {
                    "iteration": iteration_index + 1,
                    "parsed_configs": configs,
                    "usage": result.get("usage", {}),
                }
            ],
            token_count=result.get("usage", {}),
        )

    all_inference_results = (
        run_iterative_inference(
            client=model_inference,
            messages=current_messages,
            number_of_iterations=number_of_iterations,
            provider=_inf_provider,
            model_id=_model_id,
            agent_id=_agent_id,
            on_iteration_complete=_on_iteration_complete,
        )
        if client is not None and messages is not None and number_of_iterations
        else []
    )

    if all_inference_results:
        # Rebuild current_messages from the full conversation after all iterations
        current_messages = messages.copy()
        for _res in all_inference_results:
            if _res and _res.get("choices"):
                current_messages.append(_res["choices"][0]["message"])

        if created_iteration_id and active_db_client:
            try:
                update_iteration_document(
                    provider=active_db_provider,
                    db_client=active_db_client,
                    db_name=db_messages,
                    iteration_id=created_iteration_id,
                    update_messages=current_messages,
                )
            except Exception as e:
                print(f"Error updating full messages list: {e}")

    completed_generation = len(all_inference_results) > 0
    return all_inference_results, completed_generation, current_messages


@app.cell
def _(all_inference_results):
    # Aggregate token counts from all iterations
    token_count = None
    if all_inference_results:
        total_prompt_tokens = 0
        total_completion_tokens = 0
        total_tokens = 0

        for token_iter_result in all_inference_results:
            if token_iter_result and token_iter_result.get("usage"):
                usage = token_iter_result["usage"]
                total_prompt_tokens += usage.get("prompt_tokens", 0)
                total_completion_tokens += usage.get("completion_tokens", 0)
                total_tokens += usage.get("total_tokens", 0)

        token_count = {  # noqa: F841
            "prompt_tokens": total_prompt_tokens,
            "completion_tokens": total_completion_tokens,
            "total_tokens": total_tokens,
        }
    return


@app.cell
def _(all_inference_results):
    # Collect all choices from all iterations
    all_inference_choices = []
    if all_inference_results:
        for choice_iter_result in all_inference_results:
            if choice_iter_result and choice_iter_result.get("choices"):
                all_inference_choices.extend(choice_iter_result.get("choices"))

    inference_result = all_inference_choices if all_inference_choices else None
    return all_inference_choices, inference_result


@app.cell
def _(inference_result, parse_yaml_documents):
    # Parse YAML from each iteration's response
    loaded_yaml_choices = []
    if inference_result:
        for choice in inference_result:
            content = choice.get("message", {}).get("content", "")
            parsed_yaml = parse_yaml_documents(content)
            loaded_yaml_choices.append(parsed_yaml)
    return


@app.cell
def _(
    active_db_client,
    active_db_provider,
    all_inference_results,
    completed_generation,
    db_messages,
    messages_to_render,
    retrieve_documents,
):
    # Retrieve the final iteration document with all results
    all_iteration_results = None
    if completed_generation and all_inference_results:
        # Derive iteration_id from messages_to_render
        _iter_docs = (
            messages_to_render.get("docs", [])
            if isinstance(messages_to_render, dict)
            else []
        )
        created_iteration_id_val = (
            _iter_docs[0].get("iteration_id") if _iter_docs else None
        )

        if created_iteration_id_val:
            retrieved_iteration = retrieve_documents(
                provider=active_db_provider,
                db_client=active_db_client,
                db_name=db_messages,
                selectors={
                    "$and": [
                        {"iteration_id": {"$eq": created_iteration_id_val}},
                    ]
                },
                fields=[
                    "generation_content.results",
                    "generation_content.messages",
                ],
                docs_only=True,
            )
            if retrieved_iteration:
                all_iteration_results = (  # noqa: F841
                    retrieved_iteration[0].get("generation_content", {}).get("results")
                )
    return


@app.cell
def _(
    db_provider,
    generation_iterations_selector,
    ica_consumptive_toggle,
    inference_provider,
    model_selector,
    org_id_dropdown,
    output_language_editor,
    param_target,
    template_selector,
):
    _inference_controls = [inference_provider, param_target]
    if ica_consumptive_toggle is not None:
        _inference_controls.append(ica_consumptive_toggle)
    _inference_controls += [model_selector, generation_iterations_selector]

    setup_selection_stack = mo.hstack(
        [
            mo.vstack(
                [db_provider, template_selector],
            ),
            mo.vstack(_inference_controls),
            mo.vstack(
                [output_language_editor, org_id_dropdown],
            ),
        ],
        justify="space-around",
        gap=6,
    )
    return (setup_selection_stack,)


@app.cell
def _(setup_selection_stack):
    setup_selection_stack
    return


@app.cell
def _(db_validation_results, set_up_baseline_documents, set_up_missing_dbs):
    mo.accordion(
        items={
            "Check Database Status": mo.vstack(
                [
                    db_validation_results,
                    set_up_missing_dbs.center(),
                    set_up_baseline_documents.center(),
                ],
                gap=2,
            )
        }
    ).center()
    return


@app.cell
def _(org_preview_accordion):
    org_preview_accordion
    return


@app.cell
def _(user_spec_input):
    user_spec_input
    return


@app.cell
def _():
    return


@app.cell
def _():
    ### Ui Elements
    return


@app.cell
def _(all_inference_choices, completed_generation):
    all_rendered_outputs = {}
    all_output_content = {}

    if completed_generation and all_inference_choices:
        with mo.status.progress_bar(
            total=len(all_inference_choices),
            title="Rendering inference responses",
            subtitle="Processing...",
            completion_title="Rendering complete",
            completion_subtitle=f"Processed {len(all_inference_choices)} response(s)",
            remove_on_exit=True,
        ) as bar:
            for idx, output_choice in enumerate(all_inference_choices):
                choice_num = idx + 1
                label = f"Inference Choice Response {choice_num}"

                message_content = output_choice.get("message", {}).get("content", "")
                choice_markdown = []
                choice_raw_content = []

                if message_content:
                    try:
                        rendered_md = mo.md(message_content)
                        labeled_markdown = mo.vstack(
                            [
                                mo.md(f"**Inference Response {choice_num}**"),
                                rendered_md,
                            ]
                        )
                        choice_markdown.append(labeled_markdown)
                        choice_raw_content.append(message_content)
                    except Exception as e:
                        failed_markdown = mo.callout(
                            mo.md(
                                f"**Inference Response {choice_num}** - Failed to render content: {str(e)}"
                            ),
                            kind="warn",
                        )
                        choice_markdown.append(failed_markdown)
                        choice_raw_content.append(message_content)
                else:
                    empty_markdown = mo.callout(
                        mo.md(
                            f"**Inference Response {choice_num}** - No content available"
                        ),
                        kind="neutral",
                    )
                    choice_markdown.append(empty_markdown)
                    choice_raw_content.append("")

                all_rendered_outputs[label] = choice_raw_content
                all_output_content[label] = choice_markdown
                bar.update(
                    title=f"Rendering ({label})",
                    subtitle="Processing content",
                )
    return (all_rendered_outputs,)


@app.cell
def _(all_rendered_outputs):
    if all_rendered_outputs:
        output_review_tabs = mo.vstack(
            [
                mo.vstack([mo.md(content) for content in output], gap=2)
                for label, output in all_rendered_outputs.items()
                if output
            ],
            gap=3,
        )
    else:
        output_review_tabs = None
    return (output_review_tabs,)


@app.cell
def _(org_specs):
    org_preview_accordion = (
        mo.accordion(
            {
                "#### **Preview Retrieved Organization Context** *(Click to Expand)*": org_specs
            }
        )
        if org_specs
        else None
    )
    return (org_preview_accordion,)


@app.cell
def _(output_review_tabs):
    rendered_widgets_accordion = mo.accordion(  # noqa: F841
        {
            "## **Rendered Outputs** *(Click to Expand)*": mo.vstack(
                [output_review_tabs], gap=3
            )
        }
    )
    return


@app.cell
def _(current_messages):
    preview_rendered_messages_json = mo.accordion(
        {"**Preview rendered messages sent to the Model**": current_messages}
    )
    return (preview_rendered_messages_json,)


@app.cell
def _(all_inference_results):
    preview_llm_output_json = mo.accordion(
        {"**Preview all responses from the Model**": all_inference_results}
    )
    return (preview_llm_output_json,)


@app.cell
def _(preview_llm_output_json, preview_rendered_messages_json):
    debugging_previews = mo.accordion(
        {
            "**Debugging Previews**": mo.hstack(
                [preview_rendered_messages_json, preview_llm_output_json],
                justify="space-around",
                widths=[0.45, 0.45],
            )
        }
    )
    debugging_previews
    return


@app.cell
def _():
    return


@app.cell
def _():
    ### Db setup validation
    return


@app.cell
def _(instantiate_missing_dbs_button_status):
    set_up_missing_dbs = mo.ui.run_button(
        label="**Instantiate Missing Databases**",
        disabled=instantiate_missing_dbs_button_status,
    )
    return (set_up_missing_dbs,)


@app.cell
def _(
    active_db_client,
    active_db_provider,
    check_database_status,
    db_messages,
    db_model_params,
    db_org_context,
    db_system_templates,
):
    if active_db_provider is not None:
        ### First call, so that we can see if the button should be disabled or not.
        status_validation = pd.DataFrame(
            check_database_status(
                [
                    db_messages,
                    db_model_params,
                    db_org_context,
                    db_system_templates,
                ],
                active_db_client,
                active_db_provider,
            )
        )
    return (status_validation,)


@app.cell
def _(
    active_db_client,
    active_db_provider,
    check_database_status,
    db_messages,
    db_model_params,
    db_org_context,
    db_system_templates,
    set_up_missing_dbs,
):
    # Check all required databases
    if active_db_provider is not None:
        db_validation_df = pd.DataFrame(
            check_database_status(
                [
                    db_messages,
                    db_model_params,
                    db_org_context,
                    db_system_templates,
                ],
                active_db_client,
                active_db_provider,
                create=set_up_missing_dbs.value,
            )
        )
    else:
        db_validation_df = (
            pd.DataFrame(
                check_database_status(
                    [
                        db_messages,
                        db_model_params,
                        db_org_context,
                        db_system_templates,
                    ],
                    active_db_client,
                    active_db_provider,
                )
            )
            if active_db_provider is not None
            else pd.DataFrame([{}])
        )
    return (db_validation_df,)


@app.cell
def _(active_db_provider, db_validation_df):
    db_validation_results = (
        mo.ui.table(
            db_validation_df,
            show_column_summaries=False,
            show_data_types=False,
            show_download=False,
            selection=None,
            label=f"Selected provider: **{active_db_provider}**",
            text_justify_columns={col: "center" for col in db_validation_df.columns},
        )
        if db_validation_df is not None
        else mo.ui.table([{}])
    )
    print(db_validation_results.data)
    return (db_validation_results,)


@app.cell
def _(status_validation):
    instantiate_missing_dbs_button_status = bool(status_validation["status"].all())
    return (instantiate_missing_dbs_button_status,)


@app.cell
def _(baseline_doc_setup_enabled):
    set_up_baseline_documents = mo.ui.run_button(
        label="**Upload specified baseline documents**",
        disabled=baseline_doc_setup_enabled,
    )
    return (set_up_baseline_documents,)


@app.cell
def _(db_validation_results):
    baseline_doc_setup_enabled = not all(
        dict(db_validation_results.data["status"]).values()
    )
    return (baseline_doc_setup_enabled,)


@app.cell
def _(
    active_db_client,
    baseline_file_templates,
    set_up_baseline_documents,
    upload_documents_from_mapping,
):
    template_upload_status = (
        upload_documents_from_mapping(
            db_client=active_db_client, file_templates=baseline_file_templates
        )
        if set_up_baseline_documents.value
        else None
    )
    template_upload_status
    return


@app.cell
def _(db_messages, db_model_params, db_org_context, db_system_templates):
    baseline_file_templates = {
        db_messages: ["examples/json_documents/generation-context"],
        db_model_params: ["examples/json_documents/model-parameters"],
        db_org_context: ["examples/json_documents/organization-context"],
        db_system_templates: ["examples/json_documents/system-templates"],
    }
    return (baseline_file_templates,)


if __name__ == "__main__":
    app.run()
