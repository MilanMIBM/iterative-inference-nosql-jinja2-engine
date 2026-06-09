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

    try:
        load_all_dotenv(os.path.join(parent_dir, "config"), verbose=True)
    except:  # noqa: E722
        load_all_dotenv("config", verbose=True)
    return (
        build_additional_fields,
        filter_links,
        filter_notice_titles,
        render_template_from_dataframe,
        search_ted_notices,
        ted_buyer_details,
        ted_default_fields,
        ted_general_metadata_details,
        ted_language_ids,
        ted_tender_winner_details,
    )


@app.cell
def _():
    return


@app.cell
def _():
    return


@app.cell
def _(
    build_additional_fields,
    ted_buyer_details,
    ted_default_fields,
    ted_general_metadata_details,
    ted_tender_winner_details,
):
    additional_fields = build_additional_fields(
        id_groups=[
            ted_buyer_details,
            ted_tender_winner_details,
            ted_general_metadata_details,
            # ted_notice_details,
            # tender_financials_detailed,
            # ted_tender_conclusion_results,
            # ted_tender_conclusion_winner_details,
            # ted_notice_procedure_details,
        ],
        default_fields=ted_default_fields,
    )
    print(additional_fields)
    return (additional_fields,)


@app.cell
def _():
    target_examples = [
        "Stortinget",
        "Forsvaret",
        "Statens vegvesen",
        "ARBEIDS- OG VELFERDSETATEN",  # NAV
        "HLAVNÍ MĚSTO PRAHA",
    ]
    default_target = target_examples[3]
    return (default_target,)


@app.cell
def _(default_target):
    ted_search_target_org = mo.ui.text(
        label="**Organization Name**",
        value=default_target,
        full_width=True,
        max_length=256,
    )
    return (ted_search_target_org,)


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
        stop=100,
    )
    return (ted_search_max_items,)


@app.cell
def _():
    run_search_button = mo.ui.run_button(label="Search Tenders")
    return (run_search_button,)


@app.cell
def _(
    additional_fields,
    run_search_button,
    search_ted_notices,
    ted_search_from_date,
    ted_search_max_items,
    ted_search_target_org,
):
    search_results = (
        search_ted_notices(
            organization_name=str(ted_search_target_org.value),
            start_date=str(ted_search_from_date.value),
            limit=int(ted_search_max_items.value),
            additional_fields=additional_fields,
        )
        if run_search_button.value
        else None
    )
    return (search_results,)


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
def _(
    run_search_button,
    ted_languages,
    ted_search_from_date,
    ted_search_max_items,
    ted_search_target_org,
):
    org_details_stack = mo.vstack(
        [
            ted_search_target_org,
            ted_search_from_date,
            ted_search_max_items,
            ted_languages,
            run_search_button.center(),
        ],
        gap=1,
    )
    org_details_stack.center()
    return


@app.cell
def _(filter_links, filter_notice_titles, search_results, ted_languages):
    if search_results is not None:
        search_results_filtered = filter_notice_titles(
            search_results,
            ted_languages.value,
            extract_text_only=True,
        )
        search_results_filtered = filter_links(
            search_results_filtered,
            ted_languages.value,
            extract_text_only=True,
        )
        wrap_columns = list(search_results_filtered)
    else:
        search_results_filtered = wrap_columns = None
    return search_results_filtered, wrap_columns


@app.cell
def _(search_results, search_results_filtered):
    search_results_accordion = mo.accordion(
        items={
            "### Search Results": search_results,
            "### Filtered Results by Language": search_results_filtered,
        },
        multiple=True,
    )
    search_results_accordion
    return


@app.cell
def _():
    return


@app.cell
def _(search_results, search_results_filtered, wrap_columns):
    column_wrap = False

    if column_wrap:
        tender_table = (
            mo.ui.table(
                search_results_filtered,
                page_size=20,
                wrapped_columns=wrap_columns,
                freeze_columns_left=(
                    ["notice-title", "links"]
                    if "notice-title" in search_results_filtered
                    and "links" in search_results_filtered
                    else None
                ),
            )
            if search_results is not None
            else None
        )
    else:
        tender_table = (
            mo.ui.table(
                search_results_filtered,
                page_size=20,
                freeze_columns_left=(
                    ["notice-title", "links"]
                    if "notice-title" in search_results_filtered
                    and "links" in search_results_filtered
                    else None
                ),
            )
            if search_results is not None
            else None
        )

    tender_table
    return


@app.cell
def _(ted_search_from_date):
    print(ted_search_from_date.value)
    return


@app.cell
def _():
    # Test - Create profile
    return


@app.cell
def _():
    get_profile = mo.ui.run_button(label="**Retrieve profile data**")
    get_profile
    return (get_profile,)


@app.cell
def _():
    buyer_profile_fields = [
        "organisation-name-buyer",
        "organisation-identifier-buyer",
        "organisation-country-buyer",
        "organisation-city-buyer",
        "organisation-street-buyer",
        "organisation-internet-address-buyer",
        "organisation-email-buyer",
        "organisation-tel-buyer",
        "notice-identifier",
        "publication-number",
        "description-proc",
    ]

    buyer_financial_profile_fields = [
        "BT-24-Procedure",
        "description-proc",
        "notice-title",
        "estimated-value-proc",
        "additional-information",
        "additional-info-proc",
        "result-value-notice",
        "total-value",
        "total-value-cur",
        "TV",
        "TVL",
    ]
    return buyer_financial_profile_fields, buyer_profile_fields


@app.cell
def _(
    buyer_financial_profile_fields,
    buyer_profile_fields,
    filter_notice_titles,
    get_profile,
    search_ted_notices,
    ted_languages,
    ted_search_from_date,
    ted_search_max_items,
    ted_search_target_org,
):
    if get_profile.value:
        buyer_profile = search_ted_notices(
            organization_name=str(ted_search_target_org.value),
            start_date=str(ted_search_from_date.value),
            limit=int(ted_search_max_items.value),
            use_custom_default_fields=True,
            custom_default_fields=buyer_profile_fields,
            additional_fields=[],
        )

        buyer_financial_profile = search_ted_notices(
            organization_name=str(ted_search_target_org.value),
            start_date=str(ted_search_from_date.value),
            limit=int(ted_search_max_items.value),
            use_custom_default_fields=True,
            custom_default_fields=buyer_financial_profile_fields,
            additional_fields=[],
        )
        buyer_financial_profile = filter_notice_titles(
            buyer_financial_profile,
            ted_languages.value,
            extract_text_only=True,
        )
        # buyer_profile_filtered = filter_notice_titles(
        #     buyer_profile,
        #     ted_languages.value,
        #     extract_text_only=True,
        # )
        # buyer_profile_filtered = filter_links(
        #     buyer_profile_filtered,
        #     ted_languages.value,
        #     extract_text_only=True,
        # )
        # buyer_profile_wrap_columns = list(buyer_profile_filtered)
    else:
        buyer_profile = buyer_financial_profile = None
    return buyer_financial_profile, buyer_profile


@app.cell
def _(buyer_financial_profile):
    mo.ui.table(
        buyer_financial_profile,
        wrapped_columns=["notice-title"],
        page_size=5,
        freeze_columns_left=["notice-title", "total-value"],
    ) if buyer_financial_profile is not None else None
    return


@app.cell
def _(buyer_profile):
    buyer_profile
    return


@app.cell
def _():
    # buyer_profile_table = (
    #     mo.ui.table(
    #         buyer_profile_filtered,
    #         page_size=2,
    #         wrapped_columns=buyer_profile_wrap_columns
    #         if buyer_profile_wrap_columns is not None
    #         else [],
    #         freeze_columns_left=(
    #             ["notice-identifier", "notice-title", "links"]
    #             if buyer_profile_filtered is not None
    #             and "notice-title" in buyer_profile_filtered
    #             and "links" in buyer_profile_filtered
    #             else ["notice-identifier"]
    #             if buyer_profile_filtered is not None
    #             and "notice-identifier" in buyer_profile_filtered
    #             else ["notice-title"]
    #             if buyer_profile_filtered is not None
    #             and "notice-title" in buyer_profile_filtered
    #             else ["links"]
    #             if buyer_profile_filtered is not None
    #             and "links" in buyer_profile_filtered
    #             else None
    #         ),
    #     )
    #     if get_profile.value and buyer_profile_filtered is not None
    #     else None
    # )
    # buyer_profile_table
    return


@app.cell
def _(
    buyer_profile,
    get_profile,
    render_template_from_dataframe,
    ted_search_from_date,
    ted_search_target_org,
):
    # coupled_buyer_profile_fields = {
    #     "contact_details": {
    #         "email": "organisation-email-buyer",
    #         "phone": "organisation-tel-buyer",
    #         "notice-id": "notice-identifier",
    #     }
    # }
    additional_context = {
        "org_profile_name": str(ted_search_target_org.value),
        "language": "eng",
        "preferred_file_format": "pdf",
        "profiling_period_from": str(ted_search_from_date.value),
        "profiling_period_to": str(time.strftime("%Y-%m-%d")),
    }
    print(additional_context)
    # template = "examples/jinja2_templates/tender_org_profiler.yaml.j2"
    template_with_coupled_fields = (
        "examples/jinja2_templates/tender_org_profiler_with_coupled_fields.yaml.j2"
    )

    buyer_profile_doc = (
        render_template_from_dataframe(
            template=template_with_coupled_fields,
            df=buyer_profile,
            extra_context=additional_context,
        )
        if get_profile.value
        else {}
    )
    buyer_profile_doc
    return


@app.cell
def _():
    mo.md(r"""
    /// warning | Note to self - What to add/change
    ### Add a total value addition to notices in their own section with their own descriptions ***(move "description-proc" there)***, also add a sum value of all total values ***("total-value")*** of tenders at the top of all the org context, as well as total awareded value, and currencies ***("total-value-cur")***
    """)
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
