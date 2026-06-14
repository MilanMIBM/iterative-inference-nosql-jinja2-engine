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
    )

    from src.helpers.data_validation_helper_functions import (
        validate_parsed_configs,
    )

    from src.utils.load_all_dotenv import (
        load_all_dotenv,
    )

    from src.helpers.inference_helper_functions import (
        initialize_inference_client,
        get_models,
        get_ica_models,
        get_wxo_agents,
        run_iterative_inference,
    )

    from src.helpers.marimo_sortablekv import sortable_kv
    from src.helpers.ted_ids import (
        ted_default_fields,
        ted_language_ids,
        ted_buyer_details,
        ted_tender_winner_details,
        ted_general_metadata_details,
        ted_notice_details,
        tender_financials_detailed,
        ted_tender_conclusion_results,
        ted_tender_conclusion_winner_details,
        ted_notice_procedure_details,
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
    )

    from src.helpers.code_engine_app_helpers import (
        SIZE_PRESETS,
        AppScaleConfig,
        deploy_public_image_app,
        parse_image_reference,
    )

    try:
        load_all_dotenv(os.path.join(parent_dir, "config"), verbose=True)
    except:  # noqa: E722
        load_all_dotenv("config", verbose=True)
    return


@app.cell
def _():
    # result = deploy_public_image_app(
    #     region="eu-de",
    #     project_id="30c6a0be-9fda-4f55-8a1b-31a53594f40b",
    #     image="https://hub.docker.com/r/memgraph/lab",
    #     size="large",
    #     # ui_instructions_only=True,
    #     inspect_image=True,
    #     overwrite_current_instance=True,
    # )
    return


@app.cell
def _(result):
    result.__dict__
    return


@app.cell
def _():
    # mo.md(result.instructions_markdown)
    return


@app.cell
def _():
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
