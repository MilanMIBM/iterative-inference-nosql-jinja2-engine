import marimo

__generated_with = "0.23.9"
app = marimo.App(width="full")

with app.setup:
    import marimo as mo
    import pandas as pd
    import time
    import uuid
    import sys
    import os
    import io


@app.cell
def _():
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
        render_template_from_dataframe,
        purge_databases,
        bulk_upload_docs,
        clean_document,
    )

    from src.helpers.data_validation_helper_functions import (
        validate_parsed_configs,
    )

    from src.utils.load_all_dotenv import (
        load_all_dotenv,
    )


    from src.helpers.inference_helper_functions_v2 import InferenceClient

    from src.helpers.marimo_sortable_kv import sortable_kv
    from src.helpers.marimo_nosql_docviewer_with_utils import nosql_doc_browser
    from src.helpers.marimo_sortable_textarea import sortable_textarea
    from src.helpers.marimo_floating_card_view_v2 import floating_card_view

    from src.helpers.ted_ids import (
        main_nature_of_contract_search_tags,
        ted_default_fields,
        ted_language_ids,
        ted_profiler_fields,
    )

    # Tenders Electric Daily (TED) imports
    from src.helpers.tenders_electronic_daily_helpers import (
        search_ted_notices,
        filter_languages_in_column,
        filter_links,
        filter_notice_titles,
        parse_notice_titles,
        parse_tender_links,
        extract_download_links,
        drop_columns_from_input,
        safe_filter_ted_data,
        build_additional_fields,
        build_buyer_profiles,
    )

    from wigglystuff import SortableList

    try:
        load_all_dotenv(os.path.join(parent_dir, "config"), verbose=True)
    except:  # noqa: E722
        load_all_dotenv("config", verbose=True)
    return (
        SortableList,
        build_buyer_profiles,
        bulk_upload_docs,
        clean_document,
        floating_card_view,
        initialize_astradb_database,
        initialize_cloudant_database,
        initialize_hcd_database,
        initialize_mongodb_database,
        main_nature_of_contract_search_tags,
        nosql_doc_browser,
        render_template_from_dataframe,
        ted_language_ids,
        ted_profiler_fields,
    )


@app.cell
def _():
    org_name_list_file = mo.ui.file(
        label="Add your list of organizations (.csv)",
        kind="area",
        filetypes=[".csv"],
    )
    return (org_name_list_file,)


@app.cell
def _(org_name_list_file):
    org_name_list_dataframe = (
        pd.read_csv(io.BytesIO(org_name_list_file.value[0].contents))
        if org_name_list_file.value and org_name_list_file.value[0].contents
        else []
    )
    return (org_name_list_dataframe,)


@app.cell
def _(org_name_list_dataframe):
    sample_org_names = mo.ui.range_slider(
        label="*Select how many names you want loaded from your file*",
        start=0,
        step=1,
        stop=len(org_name_list_dataframe),
        value=(0, len(org_name_list_dataframe) // 4),
        show_value=True,
        full_width=True,
    )
    return (sample_org_names,)


@app.cell
def _(org_name_list_dataframe, org_name_list_file, sample_org_names):
    if org_name_list_file.value and org_name_list_dataframe is not None:
        org_names = org_name_list_dataframe.iloc[:, 0].tolist()
        adjusted_range_org_names = org_names[
            sample_org_names.value[0] : sample_org_names.value[1]
        ]
    else:
        org_names = adjusted_range_org_names = []
    return (adjusted_range_org_names,)


@app.cell
def _(SortableList, adjusted_range_org_names):
    org_name_list = mo.ui.anywidget(
        SortableList(
            value=adjusted_range_org_names,
            addable=True,
            removable=True,
            editable=True,
        )
    )
    return (org_name_list,)


@app.cell
def _(org_name_list):
    org_accordion = mo.accordion(items={"Organization Names List": org_name_list})
    return (org_accordion,)


@app.cell
def _():
    ted_search_from_date = mo.ui.date(
        label="**Tenders from** (to today):",
        value="2025-01-01",
    )
    return (ted_search_from_date,)


@app.cell
def _():
    ted_search_max_items = mo.ui.number(
        label="**Max Results:**",
        value=20,
        start=1,
        stop=200,
    )
    return (ted_search_max_items,)


@app.cell
def _(main_nature_of_contract_search_tags):
    ted_contract_natures = mo.ui.multiselect(
        label="**Filter by contract nature** *(Optional)*:",
        options=main_nature_of_contract_search_tags,
        max_selections=None,
        full_width=True,
    )
    return (ted_contract_natures,)


@app.cell
def _(ted_language_ids):
    ted_languages = mo.ui.multiselect(
        label="**Select the languages to filter by:**",
        options=ted_language_ids,
        value=["English"],
        max_selections=None,
    )
    return (ted_languages,)


@app.cell
def _():
    get_profile = mo.ui.run_button(label="**Retrieve profile data**")
    return (get_profile,)


@app.cell
def _(
    get_profile,
    sample_org_names,
    ted_contract_natures,
    ted_languages,
    ted_search_from_date,
    ted_search_max_items,
):
    org_details_stack = mo.vstack(
        [
            sample_org_names,
            ted_search_from_date,
            ted_search_max_items,
            ted_contract_natures,
            ted_languages,
            get_profile,
        ],
        gap=1,
    )
    return (org_details_stack,)


@app.cell
def _(context_directory_name_input, db_provider):
    database_provider_stack = mo.vstack(
        [db_provider, context_directory_name_input], gap=1
    )
    database_provider_stack.center()
    return


@app.cell
def _(org_accordion, org_details_stack, org_name_list_file):
    search_stack = mo.hstack(
        [
            org_accordion,
            mo.vstack([org_name_list_file, org_details_stack], align="start"),
        ],
        justify="space-around",
        gap=3,
        widths=[0.5, 0.3],
    )
    search_stack
    return


@app.cell
def _(org_name_list):
    print(org_name_list.value.get("value"))
    return


@app.cell
def _():
    template_with_coupled_fields = os.getenv(
        "JSON_DOCUMENT_TEMPLATE",
        "examples/jinja2_templates/tender_org_profiler_with_coupled_fields_v3.yaml.j2",
    )
    return (template_with_coupled_fields,)


@app.cell
def _(org_name_list):
    organization_names = (
        org_name_list.value.get("value") if org_name_list.value else []
    )
    return (organization_names,)


@app.cell
def _(ted_contract_natures):
    contract_nature_filter = (
        f"contract-nature IN ({' '.join(ted_contract_natures.value)})"
        if ted_contract_natures.value
        else None
    )
    return (contract_nature_filter,)


@app.cell
def _(
    build_buyer_profiles,
    contract_nature_filter,
    get_profile,
    organization_names,
    render_template_from_dataframe,
    ted_languages,
    ted_profiler_fields,
    ted_search_from_date,
    ted_search_max_items,
    template_with_coupled_fields,
):
    if get_profile.value:
        buyer_profiles = build_buyer_profiles(
            organization_names,
            render_template_from_dataframe=render_template_from_dataframe,
            template=template_with_coupled_fields,
            start_date=str(ted_search_from_date.value),
            limit=int(ted_search_max_items.value),
            buyer_profile_fields=ted_profiler_fields,
            language=ted_languages.value,
            preferred_file_format="pdf",
            extra_query_filters=[contract_nature_filter],
            # add_uuid=True,
        )
    else:
        buyer_profiles = []
    return (buyer_profiles,)


@app.cell
def _(buyer_profiles):
    buyer_profile_dataframe = pd.DataFrame(buyer_profiles)
    return (buyer_profile_dataframe,)


@app.cell
def _(buyer_profile_dataframe):
    buyer_profile_dataframe
    return


@app.cell
def _(buyer_profile_dataframe, floating_card_view):
    profile_cards = floating_card_view(
        buyer_profile_dataframe["buyer_profile_doc"]
        if "buyer_profile_doc" in buyer_profile_dataframe.columns
        else [],
        card_height=600,
        card_width="60%",
        aspect_ratio=0.7,
        selectable=False,
    )
    profile_cards
    return


@app.cell
def _(upload_documents):
    upload_documents.center()
    return


@app.cell
def _():
    ### Database Providers
    return


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
        if hcd_api_endpoint
        and hcd_api_username
        and hcd_api_password
        and hcd_keyspace
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
        value="astradb",
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
def _(active_db_provider):
    context_directory_name_input = mo.ui.text(
        label="**Destination Database/Collection Name**",
        placeholder="Write a lowercase name with either - or _ instead of spaces",
        value=(
            "organizational-profiles"
            if active_db_provider == "cloudant"
            else "organizational_profiles"
        ),
        max_length=256,
        full_width=True,
    )
    return (context_directory_name_input,)


@app.cell
def _(context_directory_name_input):
    context_directory_name = (
        context_directory_name_input.value.replace(" ", "_").lower()
        if context_directory_name_input.value
        else "organizational_profiles"
    )
    print(context_directory_name)
    return (context_directory_name,)


@app.cell
def _(context_directory_name, db_provider):
    db_context_directory = (
        context_directory_name.replace("_", "-")
        if db_provider.value == "cloudant"
        else context_directory_name
    )
    return (db_context_directory,)


@app.cell
def _():
    upload_documents = mo.ui.run_button(label="**Upload context documents**")
    return (upload_documents,)


@app.cell
def _(
    active_db_client,
    active_db_provider,
    bulk_upload_docs,
    buyer_profiles,
    clean_document,
    db_context_directory,
    upload_documents,
):
    if upload_documents.value:
        uploaded_docs = bulk_upload_docs(
            db_client=active_db_client,
            db_name=db_context_directory,
            docs=clean_document(buyer_profiles),
            batch_size=10,
            provider=active_db_provider,
        )
    else:
        uploaded_docs = None
    return (uploaded_docs,)


@app.cell
def _(uploaded_docs):
    uploaded_docs
    return


@app.cell
def _(db_context_directory):
    collection_name_keys = {
        f"{db_context_directory}": "org_name",
        "generation_context": "iteration_id",
        "model_parameters": "parameter_set_name",
        "organization_context": "org_context.client_name",
        "system_templates": "name",
    }
    print(collection_name_keys)
    return (collection_name_keys,)


@app.cell
def _(active_db_client, collection_name_keys, db_provider, nosql_doc_browser):
    doc_browser = nosql_doc_browser(
        db_client=active_db_client,
        provider=db_provider.value,
        name_key=collection_name_keys,
        name_mode="append",
        label="Browse JSON documents",
        multiselect=True,
        limit=200,
    )
    doc_browser
    return (doc_browser,)


@app.cell
def _(doc_browser):
    (doc_browser.value if doc_browser.value else None)
    return


if __name__ == "__main__":
    app.run()
