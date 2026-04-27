import marimo

__generated_with = "0.23.0"
app = marimo.App(width="full")

with app.setup:
    import marimo as mo
    import pandas as pd
    from typing import Union
    from wigglystuff import SortableList
    import time
    import uuid
    import json
    import os


@app.cell
def _():
    from ibm_watsonx_ai import Credentials, APIClient
    from ibm_watsonx_ai.foundation_models import ModelInference

    return APIClient, Credentials, ModelInference


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
        create_iteration_document,
        update_iteration_document,
        render_jinja2_templates,
        upload_single_document,
        ensure_database_exists,
        check_database_status,
        parse_yaml_documents,
        retrieve_documents,
        bulk_upload_docs,
        bulk_update_docs,
    )

    from src.utils.load_all_dotenv import (
        load_all_dotenv,
    )

    try:
        load_all_dotenv(os.path.join(parent_dir, "config"), verbose=True)
    except:
        load_all_dotenv("config", verbose=True)
    return (
        check_database_status,
        create_iteration_document,
        initialize_astradb_database,
        initialize_cloudant_database,
        initialize_mongodb_database,
        parse_yaml_documents,
        render_jinja2_templates,
        retrieve_documents,
        update_iteration_document,
    )


@app.cell
def _():
    # watsonx.ai
    wx_api_key = os.getenv("WX_API_KEY", "")
    wx_project_id = os.getenv("WX_PROJECT_ID", "")
    wx_space_id = os.getenv("WX_SPACE_ID", "")
    wx_url = os.getenv("WX_URL", "https://eu-de.ml.cloud.ibm.com")
    default_chat_model = os.getenv("CHAT_MODEL", "mistralai/mistral-medium-2505")
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
    return (
        astradb_api_endpoint,
        astradb_application_token,
        astradb_keyspace,
        cloudant_apikey,
        cloudant_url,
        default_chat_model,
        mongodb_cert_path,
        mongodb_endpoint,
        mongodb_password,
        mongodb_username,
        wx_api_key,
        wx_project_id,
        wx_space_id,
        wx_url,
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
        "survey_context".replace("_", "-")
        if db_provider.value == "cloudant"
        else "survey_context"
    )
    print(db_messages)
    db_modelparams = (
        "model_parameters".replace("_", "-")
        if db_provider.value == "cloudant"
        else "model_parameters"
    )
    print(db_modelparams)
    db_system_templates = (
        "system_templates".replace("_", "-")
        if db_provider.value == "cloudant"
        else "system_templates"
    )
    print(db_system_templates)
    return db_messages, db_modelparams, db_org_context, db_system_templates


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
    db_provider = mo.ui.dropdown(
        ["cloudant", "astradb", "mongodb"],
        value="cloudant",
        allow_select_none=False,
        label="**Select Context Database Backend:**",
        full_width=True,
    )
    return (db_provider,)


@app.cell
def _(astradb, cloudant, db_provider, mongodb):
    active_db_provider = db_provider.value
    if active_db_provider == "astradb":
        active_db_client = astradb
    elif active_db_provider == "mongodb":
        active_db_client = mongodb
    else:
        active_db_client = cloudant
    return active_db_client, active_db_provider


@app.cell
def _(APIClient, Credentials, wx_api_key, wx_project_id, wx_space_id, wx_url):
    if wx_api_key and wx_url and (wx_project_id or wx_space_id):
        wx_credentials = Credentials(url=wx_url, api_key=wx_api_key)
        client = APIClient(wx_credentials)
        if wx_project_id:
            client.set.default_project(wx_project_id)
            print(f"watsonx.ai client is set to Project: {wx_project_id}")
        elif wx_space_id:
            client.set.default_space(wx_space_id)
            print(f"watsonx.ai client is set to Deployment Space: {wx_space_id}")
    else:
        client = None
        print(
            f"wx_api_key, wx_url, and either wx_space_id or wx_project_id are required. Client is {client}"
        )
    return (client,)


@app.cell
def _(client, default_chat_model):
    model_options = (
        pd.DataFrame(
            client.foundation_models.get_chat_function_calling_model_specs().get(
                "resources"
            )
        ).model_id.to_list()
        if client
        else [default_chat_model]
    )
    return


@app.cell
def _(
    active_db_client,
    active_db_provider,
    db_modelparams,
    default_model_params,
    param_target,
    retrieve_documents,
):
    _model_param_results = (
        retrieve_documents(
            provider=active_db_provider,
            db_client=active_db_client,
            db_name=db_modelparams,
            selectors={"parameter_set_name": {"$eq": param_target.value}},
            fields=["parameters"],
            docs_only=True,
        )
        if active_db_client is not None
        else default_model_params
    )
    model_params = next(
        (doc.get("parameters") for doc in _model_param_results),
        default_model_params,
    )
    return (model_params,)


@app.cell
def _(default_chat_model, model_params):
    class ModelSelector:
        def __init__(self, value):
            self.value = value


    selected_model = (
        model_params.get("model_id") if model_params else default_chat_model
    )
    model_selector = ModelSelector(selected_model)
    return (model_selector,)


@app.cell
def _(
    ModelInference,
    client,
    default_chat_model,
    model_params,
    model_selector,
):
    model_inference = (
        ModelInference(
            api_client=client,
            model_id=(
                str(model_selector.value)
                or model_params.get("model_id")
                or default_chat_model
            ),
            params=model_params.get("params"),
        )
        if client is not None
        else None
    )
    return (model_inference,)


@app.cell
def _():
    ### Fallback defaults
    default_messages_template = "00000000-0000-0000-0000-000000000000"
    default_parameter_set = "mistral-medium-2505_single_generation"
    default_system_templates = "main_system_templates_marimo_v2"
    return default_parameter_set, default_system_templates


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
    db_modelparams,
    default_parameter_set,
    retrieve_documents,
):
    # Retrieves model parameter sets available
    try:
        model_param_targets = (
            retrieve_documents(
                provider=active_db_provider,
                db_client=active_db_client,
                db_name=db_modelparams,
                selectors={"parameter_set_name": {"$exists": True}},
                fields=["parameter_set_name"],
                docs_only=True,
            )
            if active_db_client is not None
            else []
        )
        if not model_param_targets:
            model_param_targets = [{"parameter_set_name": default_parameter_set}]
        parameter_set_names = {
            param.get("parameter_set_name") for param in model_param_targets
        }
    except Exception as e:
        time.sleep(1.05)
        try:
            model_param_targets = (
                retrieve_documents(
                    provider=active_db_provider,
                    db_client=active_db_client,
                    db_name=db_modelparams,
                    selectors={"parameter_set_name": {"$exists": True}},
                    fields=["parameter_set_name"],
                    docs_only=True,
                )
                if active_db_client is not None
                else []
            )
            if not model_param_targets:
                model_param_targets = [
                    {"parameter_set_name": default_parameter_set}
                ]
            parameter_set_names = {
                param.get("parameter_set_name") for param in model_param_targets
            }
        except Exception as retry_e:
            # Database doesn't exist or is empty, use default
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
    except Exception as e:
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
        except Exception as retry_e:
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
    except Exception as e:
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
    messages
    return (messages,)


@app.cell
def _(
    active_db_client,
    active_db_provider,
    client,
    db_messages,
    messages,
    messages_to_render,
    model_inference,
    number_of_iterations,
    parse_yaml_documents,
    update_iteration_document,
):
    # Multi-generation loop for iterative inference (no validation endpoint)
    all_inference_results = []
    current_messages = messages.copy() if messages else []
    completed_generation = False
    created_iteration_id = None

    # Derive iteration_id from the messages_to_render cell output
    if isinstance(messages_to_render, dict):
        _iter_docs = messages_to_render.get("docs", [])
        created_iteration_id = (
            _iter_docs[0].get("iteration_id") if _iter_docs else None
        )

    if client is not None and messages is not None and number_of_iterations:
        for iteration in range(number_of_iterations):
            # Generate response
            iteration_inference_result = model_inference.chat(
                messages=current_messages
            )
            all_inference_results.append(iteration_inference_result)

            # Extract the assistant's response
            if iteration_inference_result and iteration_inference_result.get(
                "choices"
            ):
                assistant_message = iteration_inference_result["choices"][0][
                    "message"
                ]
                current_messages.append(assistant_message)

                # Parse YAML from the raw response content
                raw_content = assistant_message.get("content", "")
                parsed = parse_yaml_documents(raw_content)
                if not isinstance(parsed, (dict, list)):
                    parsed = []
                configs = parsed if isinstance(parsed, list) else [parsed]

                # Append "Generate Next Output" for the next iteration
                if iteration < number_of_iterations - 1:
                    current_messages.append(
                        {"role": "user", "content": "Generate Next Output."}
                    )

                # Update iteration document with this iteration's results
                if created_iteration_id and active_db_client:
                    try:
                        update_iteration_document(
                            provider=active_db_provider,
                            db_client=active_db_client,
                            db_name=db_messages,
                            iteration_id=created_iteration_id,
                            new_messages=[assistant_message],
                            new_results=[
                                {
                                    "iteration": iteration + 1,
                                    "parsed_configs": configs,
                                    "usage": iteration_inference_result.get(
                                        "usage", {}
                                    ),
                                }
                            ],
                            token_count=iteration_inference_result.get("usage", {}),
                        )
                    except Exception as e:
                        print(f"Error updating iteration document: {e}")

        # Final update: overwrite messages with the complete conversation
        if created_iteration_id and active_db_client and current_messages:
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

        token_count = {
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
                all_iteration_results = (
                    retrieved_iteration[0]
                    .get("generation_content", {})
                    .get("results")
                )
    return


@app.cell
def _(
    db_provider,
    generation_iterations_selector,
    org_id_dropdown,
    output_language_editor,
    param_target,
    template_selector,
):
    setup_selection_stack = mo.hstack(
        [
            mo.vstack(
                [db_provider, template_selector],
            ),
            mo.vstack(
                [param_target, output_language_editor],
            ),
            mo.vstack(
                [org_id_dropdown, generation_iterations_selector],
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
def _(db_validation_results, set_up_missing_dbs):
    mo.accordion(
        items={
            "Check Database Status": mo.vstack(
                [
                    db_validation_results.style(
                        {
                            "width": "90%",
                        }
                    ).center(),
                    set_up_missing_dbs.center(),
                ],
                gap=2,
            )
        }
    ).style({"width": "35%"}).center()
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

                message_content = output_choice.get("message", {}).get(
                    "content", ""
                )
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
    rendered_widgets_accordion = mo.accordion(
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
    db_modelparams,
    db_org_context,
    db_system_templates,
):
    if active_db_provider is not None:
        ### First call, so that we can see if the button should be disabled or not.
        status_validation = pd.DataFrame(
            check_database_status(
                [
                    db_messages,
                    db_modelparams,
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
    db_modelparams,
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
                    db_modelparams,
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
                        db_modelparams,
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
            text_justify_columns={
                col: "center" for col in db_validation_df.columns
            },
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


if __name__ == "__main__":
    app.run()
