import marimo

__generated_with = "0.23.8"
app = marimo.App(width="full")

with app.setup:
    import marimo as mo
    from wigglystuff import SortableList
    import uuid
    import os


@app.cell
def _():
    import sys

    parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

    from src.helpers.nosql_database_helper_functions import (
        initialize_cloudant_database,
        initialize_astradb_database,
        initialize_hcd_database,
        initialize_mongodb_database,
        upload_single_document,
    )

    from src.helpers.marimo_widget_helper_functions import (
        records_to_dict,
    )
    from src.helpers.marimo_sortablekv import sortable_kv
    from src.utils.load_all_dotenv import (
        load_all_dotenv,
    )

    try:
        load_all_dotenv(os.path.join(parent_dir, "config"), verbose=True)
    except:  # noqa: E722
        load_all_dotenv("config", verbose=True)
    return (
        initialize_astradb_database,
        initialize_cloudant_database,
        initialize_hcd_database,
        initialize_mongodb_database,
        records_to_dict,
        sortable_kv,
        upload_single_document,
    )


@app.cell
def _():
    astradb_api_endpoint = os.getenv("ASTRA_DB_API_ENDPOINT", "")
    astradb_application_token = os.getenv("ASTRA_DB_APPLICATION_TOKEN", "")
    astradb_keyspace = os.getenv("ASTRA_DB_KEYSPACE", "default_keyspace")
    cloudant_url = os.getenv("CLOUDANT_URL", "")
    cloudant_apikey = os.getenv("CLOUDANT_APIKEY", "")
    mongodb_endpoint = os.getenv("MONGODB_ENDPOINT", "")
    mongodb_username = os.getenv("MONGODB_USERNAME", "")
    mongodb_password = os.getenv("MONGODB_PASSWORD", "")
    mongodb_cert_path = os.getenv("MONGODB_CERT_PATH", "")
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
    mo.md(rf"""
    # **Organization Context** *- Drafting Dashboard - v.2.0*
    ### Notebook that allows users to create and upload organizational context documents to IBM Cloudant or AstraDB (WIP) for use in generative AI usecases as common context across an organization. The file will be uploaded to the database and be available for use.
    {db_provider.center()}
    """)
    return


@app.cell
def _():
    mo.md("""
    > [BUG TO FIX] **Note to self, fix the issue of empty strings/keys from the key value pair setups when sending the documents in. Make it clear out any before submission.**
    """)
    return


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
def _(db_provider):
    db_org_context = (
        "organization_context".replace("_", "-")
        if db_provider.value == "cloudant"
        else "organization_context"
    )
    return (db_org_context,)


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
def _():
    term_template = [
        {
            "original": "<Term to Replace>",
            "replacement": "<Bias to Replacement Term>",
        },
        {
            "original": "<Term to Replace>",
            "replacement": "<Bias to Replacement Term>",
        },
        {
            "original": "<Term to Replace>",
            "replacement": "<Bias to Replacement Term>",
        },
    ]
    print(term_template)
    taxonomy_template = [
        {"term": "<Term>", "definition": "<Definition>"},
        {"term": "<Term>", "definition": "<Definition>"},
        {"term": "<Term>", "definition": "<Definition>"},
    ]
    print(taxonomy_template)

    offerings_kv_template = [
        {"key": "<Offering Name>", "value": "<Offering Description>"},
        {"key": "<Offering Name>", "value": "<Offering Description>"},
        {"key": "<Offering Name>", "value": "<Offering Description>"},
    ]
    print(offerings_kv_template)
    return offerings_kv_template, taxonomy_template, term_template


@app.cell
def _(sortable_kv, term_template):
    term_editor = sortable_kv(
        label="Terminology Remapping",
        value=term_template,
        key_placeholder=list(term_template[0].values())[0],
        value_placeholder=list(term_template[0].values())[1],
        addable=True,
        removable=True,
        editable=True,
        movable=True,
    )
    return (term_editor,)


@app.cell
def _(records_to_dict, term_editor):
    terminology_map = (
        [records_to_dict(term_editor.value.get("value"))]
        if term_editor.value.get("value") is not None
        else []
    )
    return (terminology_map,)


@app.cell
def _(sortable_kv, taxonomy_template):
    taxonomy_editor = sortable_kv(
        label="Taxonomy",
        value=taxonomy_template,
        key_placeholder=list(taxonomy_template[0].values())[0],
        value_placeholder=list(taxonomy_template[0].values())[1],
        addable=True,
        removable=True,
        editable=True,
        movable=True,
    )
    return (taxonomy_editor,)


@app.cell
def _(records_to_dict, taxonomy_editor):
    taxonomy = (
        [records_to_dict(taxonomy_editor.value.get("value"))]
        if taxonomy_editor.value.get("value") is not None
        else []
    )
    return (taxonomy,)


@app.cell
def _(offerings_kv_template, sortable_kv):
    offerings_kv = sortable_kv(
        label="Offerings",
        value=offerings_kv_template,
        key_placeholder=list(offerings_kv_template[0].values())[0],
        value_placeholder=list(offerings_kv_template[0].values())[1],
        addable=True,
        removable=True,
        editable=True,
        movable=True,
    )
    return (offerings_kv,)


@app.cell
def _(offerings_kv, records_to_dict):
    offerings = (
        [records_to_dict(offerings_kv.value.get("value"))]
        if offerings_kv.value.get("value") is not None
        else []
    )
    return (offerings,)


@app.cell
def _():
    organization_name = mo.ui.text(
        label="**Organization Name:**",
        placeholder="Name of the organization",
        full_width=True,
        max_length=300,
    )
    return (organization_name,)


@app.cell
def _():
    language = mo.ui.text(
        label="**Default Language for Outputs *(defaults to English)*:**",
        value="English",
        full_width=True,
        max_length=300,
    )
    return (language,)


@app.cell
def _():
    organization_description = mo.ui.text_area(
        label="**Organization Description:**",
        placeholder="Describe your organization in as detailed a manner as you can on an overarching level. This will influence all outputs for all users in your organization",
        full_width=True,
        max_length=2000,
        rows=8,
    )
    return (organization_description,)


@app.cell
def _():
    location_operations = SortableList(
        label="Add your locations (Country or specific addresses recommended)",
        addable=True,
        editable=True,
        removable=True,
        value=[""],
    )
    return (location_operations,)


@app.cell
def _():
    upload_org_context = mo.ui.run_button(
        label="**Upload your Organization Context**",
    )
    return (upload_org_context,)


@app.cell
def _():
    ### --- Widget Displays
    return


@app.cell
def _(language, organization_name):
    mo.hstack(
        [organization_name, language],
        widths=[0.3, 0.3],
        justify="space-around",
        align="start",
    )
    return


@app.cell
def _(organization_description):
    organization_description.style({"width": "100%"})
    return


@app.cell
def _():
    return


@app.cell
def _(offerings_kv):
    offerings_stack = mo.vstack(
        [
            mo.md("##**Offerings Editor**"),
            mo.md(
                "#### *(Add or remove columns as necessary, to add or remove offerings and their descriptions)*"
            ),
            offerings_kv,
        ]
    )
    offerings_stack
    return


@app.cell
def _(term_editor):
    term_stack = mo.vstack([mo.md("###**Term Editor**").center(), term_editor])
    term_stack
    return


@app.cell
def _(taxonomy_editor):
    taxonomy_stack = mo.vstack(
        [mo.md("###**Taxonomy Editor**").center(), taxonomy_editor]
    )
    taxonomy_stack
    return


@app.cell
def _(location_operations):
    location_operations
    return


@app.cell
def _(context_document_preview):
    mo.accordion(items={"Preview JSON document": context_document_preview})
    return


@app.cell
def _(status_printout, upload_org_context):
    mo.hstack(
        [
            (mo.md(status_printout) if status_printout is not None else None),
            upload_org_context,
        ],
        justify="space-around",
    )
    return


@app.cell
def _(
    language,
    location_operations,
    offerings,
    organization_description,
    organization_name,
    taxonomy,
    terminology_map,
):
    context_document_preview = {
        "language": language.value or "English",
        "org_context": {
            "client_name": organization_name.value,
            "org_description": organization_description.value,
            "offerings": offerings,
            "terminology_mapping": terminology_map,
            "taxonomy": taxonomy,
            "location_operations": location_operations.value,
        },
    }
    return (context_document_preview,)


@app.function
def clean_document(obj):
    if isinstance(obj, dict):
        cleaned = {}
        for k, v in obj.items():
            if k is None:
                continue
            key = str(k).strip()
            if key == "":
                continue
            cleaned_value = clean_document(v)
            if cleaned_value in (None, "", [], {}):
                continue
            cleaned[key] = cleaned_value
        return cleaned
    elif isinstance(obj, list):
        cleaned_list = []
        for item in obj:
            cleaned_item = clean_document(item)
            if cleaned_item in (None, "", [], {}):
                continue
            cleaned_list.append(cleaned_item)
        return cleaned_list
    elif isinstance(obj, str):
        return obj.strip()
    else:
        return obj


@app.cell
def _(
    active_db_client,
    active_db_provider,
    db_org_context,
    language,
    location_operations,
    offerings,
    organization_description,
    organization_name,
    taxonomy,
    terminology_map,
    upload_org_context,
    upload_single_document,
):
    if upload_org_context.value:
        org_id = str(uuid.uuid4()).upper()
        context_document = {
            "_id": org_id,
            "org_id": org_id,
            "language": language.value or "English",
            "org_context": {
                "client_name": organization_name.value,
                "org_description": organization_description.value,
                "offerings": offerings,
                "terminology_mapping": terminology_map,
                "taxonomy": taxonomy,
                "location_operations": location_operations.value,
            },
        }
        if active_db_client is None:
            status_printout = (
                "Database client is not initialized. Please check your credentials."
            )
        else:
            upload_single_document(
                db_client=active_db_client,
                db_name=db_org_context,
                doc=clean_document(context_document),
                provider=active_db_provider,
            )
            provider_label = {
                "astradb": "AstraDB",
                "mongodb": "MongoDB",
                "hcd": "Datastax HCD",
            }.get(active_db_provider, "Cloudant")
            status_printout = (
                f"Uploaded document under **{org_id}** org_id to "
                f"**{db_org_context}** ({provider_label})"
            )
    else:
        org_id = status_printout = None
    return context_document, status_printout


@app.cell
def _(context_document, upload_org_context):
    if upload_org_context.value:
        pre_cleaning_doc = mo.vstack(
            ["**Pre-cleanup document**", context_document], gap=1
        )
        post_cleaning_doc = mo.vstack(
            ["**Post-cleanup document**", clean_document(context_document)], gap=1
        )
        uploaded_doc_preview_stack = mo.hstack(
            [pre_cleaning_doc, post_cleaning_doc], justify="space-around"
        )
        uploaded_doc_preview_accordion = mo.accordion(
            {
                "Uploaded JSON document *(pre and post cleanup)*": uploaded_doc_preview_stack
            }
        )
    else:
        uploaded_doc_preview_accordion = mo.accordion(
            {
                "Uploaded JSON document *(pre and post cleanup)*": "No Document Uploaded Yet..."
            }
        )
    return (uploaded_doc_preview_accordion,)


@app.cell
def _(uploaded_doc_preview_accordion):
    uploaded_doc_preview_accordion
    return


if __name__ == "__main__":
    app.run()
