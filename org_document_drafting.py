import marimo

__generated_with = "0.23.4"
app = marimo.App(width="full")

with app.setup:
    import marimo as mo
    from typing import Union
    from wigglystuff import SortableList
    import uuid
    import json
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
        initialize_mongodb_database,
        upload_single_document,
    )

    from src.helpers.marimo_widget_helper_functions import (
        columns_from_template,
        marimo_create_data_editor_df,
    )

    from src.utils.load_all_dotenv import (
        load_all_dotenv,
    )

    try:
        load_all_dotenv(os.path.join(parent_dir, "config"), verbose=True)
    except:
        load_all_dotenv("config", verbose=True)
    return (
        columns_from_template,
        initialize_astradb_database,
        initialize_cloudant_database,
        initialize_mongodb_database,
        marimo_create_data_editor_df,
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
    return (
        astradb_api_endpoint,
        astradb_application_token,
        astradb_keyspace,
        cloudant_apikey,
        cloudant_url,
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
    db_provider = mo.ui.dropdown(
        ["cloudant", "astradb", "mongodb"],
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
def _(columns_from_template):
    term_template = columns_from_template(
        "examples/db_structure_templates/organization_context.json",
        target_key="terminology_mapping",
    )
    print(term_template)

    taxonomy_template = columns_from_template(
        "examples/db_structure_templates/organization_context.json",
        target_key="taxonomy",
    )
    print(taxonomy_template)

    # offerings_template = columns_from_template(
    #     "examples/db_structure_templates/organization_context.json",
    #     target_key="offerings",
    #     variant_index=1,
    # )
    offerings_template = {
        "<offering_name1>": "str",
        "<offering_name2>": "str",
        "<offering_name3>": "str",
        "<offering_name4>": "str",
        "<offering_name5>": "str",
    }
    print(offerings_template)
    return offerings_template, taxonomy_template, term_template


@app.cell
def _(marimo_create_data_editor_df, term_template):
    term_editor_dataframe = marimo_create_data_editor_df(
        num_rows=1, columns=term_template
    )
    term_editor = mo.ui.data_editor(
        data=term_editor_dataframe,
        editable_columns="all",
    )
    return (term_editor,)


@app.cell
def _(term_editor):
    terminology_map = (
        term_editor.value.replace("", None).dropna().to_dict(orient="records")
        if term_editor.value is not None
        else []
    )
    return (terminology_map,)


@app.cell
def _(marimo_create_data_editor_df, taxonomy_template):
    taxonomy_editor_dataframe = marimo_create_data_editor_df(
        num_rows=1, columns=taxonomy_template
    )
    taxonomy_editor = mo.ui.data_editor(
        data=taxonomy_editor_dataframe,
        editable_columns="all",
    )
    return (taxonomy_editor,)


@app.cell
def _(taxonomy_editor):
    taxonomy = (
        taxonomy_editor.value.replace("", None).dropna().to_dict(orient="records")
        if taxonomy_editor.value is not None
        else []
    )
    return (taxonomy,)


@app.cell
def _(marimo_create_data_editor_df, offerings_template):
    offerings_editor_dataframe = marimo_create_data_editor_df(
        num_rows=1, columns=offerings_template
    )
    offerings_editor = mo.ui.data_editor(
        label="**Offerings**",
        data=offerings_editor_dataframe,
        editable_columns="all",
    )
    return (offerings_editor,)


@app.cell
def _(offerings_editor):
    offerings = (
        offerings_editor.value.replace("", None).dropna().to_dict(orient="records")
        if offerings_editor.value is not None
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
        value=[],
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
        widths=[0.3, 0.2],
        justify="space-around",
        align="start",
    )
    return


@app.cell
def _(organization_description):
    organization_description.style({"width": "55%"}).center()
    return


@app.cell
def _(offerings_editor):
    offerings_stack = mo.vstack(
        [
            mo.md("##**Offerings Editor**"),
            mo.md(
                "#### *(Add or remove columns as necessary, to add or remove offerings and their descriptions)*"
            ),
            offerings_editor,
        ]
    )
    offerings_stack.style({"width": "80%"}).center()
    return


@app.cell
def _(term_editor):
    term_stack = mo.vstack([mo.md("###**Term Editor**").center(), term_editor])
    term_stack.style({"width": "60%"}).center()
    return


@app.cell
def _(taxonomy_editor):
    taxonomy_stack = mo.vstack(
        [mo.md("###**Taxonomy Editor**").center(), taxonomy_editor]
    )
    taxonomy_stack.style({"width": "60%"}).center()
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
                doc=context_document,
                provider=active_db_provider,
            )
            provider_label = {
                "astradb": "AstraDB",
                "mongodb": "MongoDB",
            }.get(active_db_provider, "Cloudant")
            status_printout = (
                f"Uploaded document under **{org_id}** org_id to "
                f"**{db_org_context}** ({provider_label})"
            )
    else:
        org_id = status_printout = None
    return (status_printout,)


if __name__ == "__main__":
    app.run()
