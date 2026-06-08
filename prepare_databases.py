import marimo

__generated_with = "0.23.8"
app = marimo.App(width="full")

with app.setup:
    import marimo as mo
    import pandas as pd
    import sys
    import os


@app.cell
def _():
    _dir = os.getcwd()
    while _dir != os.path.dirname(_dir):
        if os.path.isfile(os.path.join(_dir, "pyproject.toml")):
            break
        _dir = os.path.dirname(_dir)
    parent_dir = _dir

    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

    from src.helpers.nosql_database_helper_functions import (
        initialize_cloudant_database,
        initialize_astradb_database,
        initialize_mongodb_database,
        initialize_hcd_database,
        upload_documents_from_mapping,
        check_database_status,
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
        initialize_astradb_database,
        initialize_cloudant_database,
        initialize_hcd_database,
        initialize_mongodb_database,
        upload_documents_from_mapping,
    )


@app.cell
def _():
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
    return (
        astradb_api_endpoint,
        astradb_application_token,
        astradb_keyspace,
        cloudant_apikey,
        cloudant_url,
        hcd_api_endpoint,
        hcd_api_password,
        hcd_api_username,
        hcd_keyspace,
        mongodb_cert_path,
        mongodb_endpoint,
        mongodb_password,
        mongodb_username,
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
    db_provider = mo.ui.dropdown(
        ["cloudant", "astradb", "hcd", "mongodb"],
        value="cloudant",
        allow_select_none=False,
        label="**Select Context Database Backend:**",
        full_width=False,
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
def _(instantiate_missing_dbs_button_enabled):
    set_up_missing_dbs = mo.ui.run_button(
        label="**Instantiate Missing Databases**",
        disabled=instantiate_missing_dbs_button_enabled,
    )
    return (set_up_missing_dbs,)


@app.cell
def _(baseline_doc_setup_enabled):
    set_up_baseline_documents = mo.ui.run_button(
        label="**Upload specified baseline documents**",
        disabled=baseline_doc_setup_enabled,
    )
    return (set_up_baseline_documents,)


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
def _(status_validation):
    instantiate_missing_dbs_button_status_dict = dict(status_validation["status"])
    instantiate_missing_dbs_button_enabled = all(
        instantiate_missing_dbs_button_status_dict.values()
    )
    return (instantiate_missing_dbs_button_enabled,)


@app.cell
def _(db_validation_results):
    baseline_doc_setup_enabled = not all(
        dict(db_validation_results.data["status"]).values()
    )
    return (baseline_doc_setup_enabled,)


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
    return (db_validation_results,)


@app.cell
def _(db_validation_results):
    print(db_validation_results.value)
    return


@app.cell
def _(db_provider):
    db_provider.center()
    return


@app.cell
def _(db_validation_results, set_up_missing_dbs):
    mo.accordion(
        items={
            "Check Database Status": mo.vstack(
                [
                    db_validation_results.style(
                        {
                            "width": "95%",
                        }
                    ).center(),
                    set_up_missing_dbs.center(),
                ],
                gap=2,
            )
        }
    ).style({"width": "100%"}).center()
    return


@app.cell
def _(set_up_baseline_documents):
    set_up_baseline_documents.center()
    return


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
    print(template_upload_status)
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
