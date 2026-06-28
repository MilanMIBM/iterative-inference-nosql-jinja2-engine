import marimo

__generated_with = "0.23.11"
app = marimo.App(width="full")

with app.setup:
    from typing import Callable, Optional, Dict, List, Any, Union
    import marimo as mo
    import pandas as pd
    import pycountry
    import requests
    import certifi
    import time
    import uuid
    import sys
    import os
    import io
    import re


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
        append_rendered_yaml,
        retrieve_documents,
        upload_documents_from_mapping,
        render_template_from_dataframe,
        purge_databases,
        bulk_upload_docs,
        clean_document,
        collect_urls,
    )

    from src.helpers.data_validation_helper_functions import (
        validate_parsed_configs,
    )

    from src.utils.load_all_dotenv import (
        load_all_dotenv,
    )

    from src.helpers.inference_helper_functions_v2 import InferenceClient

    from src.helpers.tenders_electronic_daily_helpers import (
        fetch_and_extract_document,
        print_extraction_summary,
        reset_extraction_log,
    )

    from src.helpers.marimo_sortable_kv import sortable_kv
    from src.helpers.marimo_nosql_docviewer_with_utils import nosql_doc_browser
    from src.helpers.marimo_sortable_textarea import sortable_textarea
    from src.helpers.marimo_floating_card_view_v2 import floating_card_view
    from src.helpers.marimo_widget_helper_functions import iso_lang

    from src.helpers.ted_ids import (
        main_nature_of_contract_search_tags,
        ted_default_fields,
        ted_language_ids,
        ted_profiler_fields,
    )

    from src.helpers.tenders_electronic_daily_sparkql_helpers import (
        fetch_and_extract_document_sparkql,
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
        extract_notice_documents,
        fetch_and_extract_notice,
        render_notices_sequential,
        extract_downloaded_files,
        extract_downloaded_files_batch,
    )

    from wigglystuff import SortableList

    try:
        load_all_dotenv(os.path.join(parent_dir, "config"), verbose=True)
    except:  # noqa: E722
        load_all_dotenv("config", verbose=True)
    return (
        InferenceClient,
        collect_urls,
        extract_downloaded_files_batch,
        extract_notice_documents,
        initialize_astradb_database,
        initialize_cloudant_database,
        initialize_hcd_database,
        initialize_mongodb_database,
        iso_lang,
        nosql_doc_browser,
        render_notices_sequential,
    )


@app.cell
def _():
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
        if astradb_api_endpoint
        and astradb_application_token
        and astradb_keyspace
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
            mongodb_endpoint,
            mongodb_username,
            mongodb_password,
            mongodb_cert_path,
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
    return (context_directory_name,)


@app.cell
def _(context_directory_name, db_provider):
    db_context_directory = (
        context_directory_name.replace("_", "-")
        if db_provider.value == "cloudant"
        else context_directory_name
    )
    print(db_context_directory)
    return (db_context_directory,)


@app.cell
def _(db_context_directory):
    db_context_directory_drilldown = f"{db_context_directory}_details"
    print(db_context_directory_drilldown)
    return (db_context_directory_drilldown,)


@app.cell
def _():
    fetch_documents = mo.ui.run_button(label="**Fetch context documents**")
    return


@app.cell
def _(db_context_directory, db_context_directory_drilldown):
    collection_name_keys = {
        f"{db_context_directory}": "org_name",
        f"{db_context_directory_drilldown}": "notice_title",
        "generation_context": "iteration_id",
        "model_parameters": "parameter_set_name",
        "organization_context": "org_context.client_name",
        "system_templates": "name",
    }
    print(collection_name_keys)
    return (collection_name_keys,)


@app.cell
def _(db_provider):
    db_provider
    return


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
    context_files = doc_browser.value if doc_browser.value else []
    return (context_files,)


@app.cell
def _(context_files, extract_notice_documents):
    notice_documents = extract_notice_documents(context_files)
    notice_documents_df = pd.DataFrame(notice_documents)
    notice_documents_df
    return (notice_documents_df,)


@app.cell
def _(collect_urls, notice_documents_df):
    collected_urls = (
        collect_urls(
            notice_documents_df,
            url_column="download_urls",
            extension_replacement="/xml",
        )
        if not notice_documents_df.empty
        else []
    )
    return (collected_urls,)


@app.cell
def _():
    # def collect_urls(df, url_column="download_urls", extension_replacement="/xml"):
    #     import ast

    #     _all_urls = []
    #     for _entry in df[url_column]:
    #         if isinstance(_entry, str):
    #             try:
    #                 _parsed = ast.literal_eval(_entry)
    #             except (ValueError, SyntaxError):
    #                 _parsed = [_entry]
    #         else:
    #             _parsed = _entry
    #         for _url in _parsed or []:
    #             _all_urls.append(_url.replace("/pdf", extension_replacement))
    #     return _all_urls


    # html_urls = collect_urls(notice_documents_df)
    # html_urls
    return


@app.cell
def _():
    return


@app.cell
def _():
    apikey = os.getenv("IBM_CLOUD_API_KEY", "")
    rhai_project_id = os.getenv("RHAI_INF_PROJECT", "")
    rhai_region = os.getenv("RHAI_INF_REGION", "us-east")
    rhai_model = os.getenv("RHAI_INF_DEFAULT_MODEL", "gpt-oss-120b")
    # rhai_model = "nvidia-nemotron-3-nano-30b-a3b-fp8"
    print(rhai_project_id)
    print(rhai_model)
    return apikey, rhai_model, rhai_project_id, rhai_region


@app.cell
def _(inf_client, rhai_model):
    model_selection_list = inf_client.get_models()
    select_model = mo.ui.dropdown(
        model_selection_list,
        label="**Select Model to Inference:**",
        value=rhai_model,
    )
    select_model
    return


@app.cell
def _():
    return


@app.cell
def _():
    ted_apikey = os.getenv("TED_API_KEY")
    print(ted_apikey[:5] + "...")
    return (ted_apikey,)


@app.cell
def _(InferenceClient, apikey, rhai_project_id, rhai_region):
    inf_client = InferenceClient(
        provider="rhai",
        project=rhai_project_id,
        region=rhai_region,
        api_key=apikey,
    )
    inf_client
    return (inf_client,)


@app.cell
def _():
    instruction = """Extract the names of any technologies (for example: Apache Spark, Apache Kafka, Db2, etc.) or architectural patterns (like zero-trust architectures, event-driven architecture, etc.) mentioned in the texts.\n\nReturn format:
    ---
    technology_stack:
      - item
      - ...

    architectural_patterns:
      - item
      - ...
    ---"""
    return


@app.cell
def _():
    # run_doc_processing = mo.ui.run_button(label="**Run LLM processing**")
    # run_doc_processing
    return


@app.cell
def _():
    run_doc_download = mo.ui.run_button(label="**Run notice download**")
    run_doc_download
    return (run_doc_download,)


@app.cell
def _(iso_lang):
    file_format = "PDF"
    lang = "ENG"
    lang_iso = iso_lang(lang)
    return file_format, lang_iso


@app.cell
def _():
    return


@app.cell
def _(
    collected_urls,
    file_format,
    lang_iso,
    render_notices_sequential,
    run_doc_download,
    ted_apikey,
):
    downloaded_notices = (
        render_notices_sequential(
            urls=collected_urls,
            api_key=ted_apikey,
            language=lang_iso,
            output_format=file_format,
        )
        if run_doc_download.value
        else []
    )
    return (downloaded_notices,)


@app.cell
def _():
    # downloaded_notices
    return


@app.cell
def _():
    # extracted_notices = (
    #     extract_downloaded_files(
    #         downloaded_notices,
    #         file_format=file_format.lower(),
    #         return_full_extraction_objects=False,
    #         max_pages=2,
    #     )
    #     if run_doc_download.value and downloaded_notices is not []
    #     else []
    # )
    return


@app.cell
def _(
    downloaded_notices,
    extract_downloaded_files_batch,
    file_format,
    run_doc_download,
):
    extracted_notices_batch = (
        extract_downloaded_files_batch(
            downloaded_notices,
            file_format=file_format.lower(),
            return_full_extraction_objects=False,
            # config=pdf_extraction_config,
            # max_pages=2,
        )
        if run_doc_download.value and downloaded_notices is not []
        else []
    )
    return (extracted_notices_batch,)


@app.cell
def _(extracted_notices_batch):
    extracted_notices_batch
    return


@app.cell
def _(extracted_notices_batch):
    clean_extracted_notices_batch = clean_strings(extracted_notices_batch)
    return (clean_extracted_notices_batch,)


@app.cell
def _(clean_extracted_notices_batch):
    clean_extracted_notices_batch
    return


@app.cell
def _():
    # extracted_notices_batch[0]
    return


@app.cell
def _():
    # mo.Html(extracted_notices_batch[0])
    return


@app.cell
def _():
    # mo.Html(clean_extracted_notices_batch[0])
    return


@app.cell
def _():
    extraction_regex = r"^([\s\S]*?\S)\s*\d+/\d{4}[\s\S]*?00\d+"
    return (extraction_regex,)


@app.cell
def _():
    return


@app.cell
def _(extracted_notices_batch, notice_documents_df):
    expanded_notice_documents_df = (
        add_notice_titles_and_contents(
            df=notice_documents_df,
            notices=extracted_notices_batch,
            id_col="publication_number",
            title_col="extracted_notice_title",
            contents_col="extracted_notice_contents",
            full_id=True,
        )
        if extracted_notices_batch
        and notice_documents_df is not None
        and not notice_documents_df.empty
        and "publication_number" in notice_documents_df.columns
        else notice_documents_df
    )
    expanded_notice_documents_df
    return


@app.cell
def _():
    return


@app.cell
def _(extracted_notices_batch, extraction_regex):
    notice_titles_list = run_pattern(
        extracted_notices_batch, extraction_regex, group=1
    )
    return


@app.function
def clean_strings(strings):
    """Return a list of cleaned strings: soft hyphens removed, nbsp/newlines normalized to spaces, whitespace collapsed."""
    import unicodedata

    cleaned = []
    for s in strings:
        s = s.replace("\xad", "")  # drop soft hyphens
        s = unicodedata.normalize(
            "NFKC", s
        )  # nbsp -> space, normalize other forms
        s = " ".join(
            s.split()
        )  # collapse all whitespace (incl. \r\n) to single spaces
        cleaned.append(s)
    return cleaned


@app.function
def add_notice_titles_and_contents(
    df,
    notices,
    id_col="publication_number",
    title_col="extracted_notice_title",
    contents_col="extracted_notice_contents",
    full_id=True,
    regex=None,
    title_group=1,
    id_from_match=None,
    df_key=None,
    lengths=(6, 5, 4),
):
    """Return a copy of df with title_col/contents_col mapped from notices by id.
    full_id=True  -> default: match the whole publication number (both halves).
    full_id=False -> match the first half only (before the dash).
    Overridable knobs (each falls back to the full_id default when None):
      regex          : a fixed search pattern. When None (default), the function
                       instead runs a length cascade over `lengths` and keeps the
                       first match whose assembled id is a real publication id.
      title_group    : which group holds the title.
      id_from_match  : fn(match) -> str key built from the notice text.
      df_key         : fn(series) -> series, the matching key built from id_col.
      lengths        : first-half digit lengths to try, in order (6 -> 5 -> 4).
    """
    if id_from_match is None:
        id_from_match = (
            (lambda m: m.group(2) + m.group(3))
            if full_id
            else (lambda m: m.group(2))
        )
    if df_key is None:
        df_key = (
            (lambda s: s.str.replace("-", "", regex=False))
            if full_id
            else (lambda s: s.str.split("-").str[0])
        )
    result = df.copy()
    keys = df_key(result[id_col])
    valid_ids = set(keys)
    id_to_title = {}
    id_to_contents = {}
    for n in notices:
        if (
            regex is not None
        ):  # user-supplied fixed pattern: single pass, no cascade
            if m := re.search(regex, n):
                id_to_title[id_from_match(m)] = m.group(title_group)
                id_to_contents[id_from_match(m)] = n
            continue
        for length in (
            lengths
        ):  # try first-half lengths in order, keep first valid id
            pat = (
                rf"^([\s\S]*?\S)\s*\d+/\d{{4}}[\s\S]*?00(\d{{{length}}})\xad(\d+)"
                if full_id
                else rf"^([\s\S]*?\S)\s*\d+/\d{{4}}[\s\S]*?00(\d{{{length}}})"
            )
            if m := re.search(pat, n):
                key = id_from_match(m)
                if key in valid_ids:
                    id_to_title[key] = m.group(title_group)
                    id_to_contents[key] = n
                    break
    result[title_col] = keys.map(id_to_title)
    result[contents_col] = keys.map(id_to_contents)
    return result


@app.function
def add_notice_titles(
    df,
    notices,
    id_col="publication_number",
    out_col="extracted_notice_title",
    full_id=True,
    regex=None,
    title_group=1,
    id_from_match=None,
    df_key=None,
    lengths=(6, 5, 4),
):
    """Return a copy of df with out_col mapped from notices by id.

    full_id=True  -> default: match the whole publication number (both halves).
    full_id=False -> match the first half only (before the dash).

    Overridable knobs (each falls back to the full_id default when None):
      regex          : a fixed search pattern. When None (default), the function
                       instead runs a length cascade over `lengths` and keeps the
                       first match whose assembled id is a real publication id.
      title_group    : which group holds the title.
      id_from_match  : fn(match) -> str key built from the notice text.
      df_key         : fn(series) -> series, the matching key built from id_col.
      lengths        : first-half digit lengths to try, in order (6 -> 5 -> 4).
    """
    if id_from_match is None:
        id_from_match = (
            (lambda m: m.group(2) + m.group(3))
            if full_id
            else (lambda m: m.group(2))
        )
    if df_key is None:
        df_key = (
            (lambda s: s.str.replace("-", "", regex=False))
            if full_id
            else (lambda s: s.str.split("-").str[0])
        )

    result = df.copy()
    keys = df_key(result[id_col])
    valid_ids = set(keys)

    id_to_title = {}
    for n in notices:
        if (
            regex is not None
        ):  # user-supplied fixed pattern: single pass, no cascade
            if m := re.search(regex, n):
                id_to_title[id_from_match(m)] = m.group(title_group)
            continue
        for length in (
            lengths
        ):  # try first-half lengths in order, keep first valid id
            pat = (
                rf"^([\s\S]*?\S)\s*\d+/\d{{4}}[\s\S]*?00(\d{{{length}}})\xad(\d+)"
                if full_id
                else rf"^([\s\S]*?\S)\s*\d+/\d{{4}}[\s\S]*?00(\d{{{length}}})"
            )
            if m := re.search(pat, n):
                key = id_from_match(m)
                if key in valid_ids:
                    id_to_title[key] = m.group(title_group)
                    break

    result[out_col] = keys.map(id_to_title)
    return result


@app.cell
def _():
    # def add_notice_titles(
    #     df,
    #     notices,
    #     id_col="publication_number",
    #     out_col="extracted_notice_title",
    #     full_id=True,
    #     regex=None,
    #     title_group=1,
    #     id_from_match=None,
    #     df_key=None,
    # ):
    #     """Return a copy of df with out_col mapped from notices by id.

    #     full_id=True  -> default: match the whole publication number (both halves).
    #     full_id=False -> match the first half only (before the dash).

    #     Overridable knobs (each falls back to the full_id default when None):
    #       regex          : the search pattern.
    #       title_group    : which group holds the title.
    #       id_from_match  : fn(match) -> str key built from the notice text.
    #       df_key         : fn(series) -> series, the matching key built from id_col.
    #     """
    #     if regex is None:
    #         regex = (
    #             r"^([\s\S]*?\S)\s*\d+/\d{4}[\s\S]*?00(\d+)\xad(\d+)"
    #             if full_id
    #             else r"^([\s\S]*?\S)\s*\d+/\d{4}[\s\S]*?00(\d+)"
    #         )
    #     if id_from_match is None:
    #         id_from_match = (
    #             (lambda m: m.group(2) + m.group(3))
    #             if full_id
    #             else (lambda m: m.group(2))
    #         )
    #     if df_key is None:
    #         df_key = (
    #             (lambda s: s.str.replace("-", "", regex=False))
    #             if full_id
    #             else (lambda s: s.str.split("-").str[0])
    #         )

    #     result = df.copy()
    #     id_to_title = {
    #         id_from_match(m): m.group(title_group)
    #         for n in notices
    #         if (m := re.search(regex, n))
    #     }
    #     result[out_col] = df_key(result[id_col]).map(id_to_title)
    #     return result
    return


@app.function
def run_pattern(strings, pattern, group=0):
    """Run pattern on each string, returning the chosen group (None where no match)."""
    compiled = re.compile(pattern)
    return [
        m.group(group) if (m := compiled.search(s)) else None
        for s in strings
    ]


@app.cell
def _():
    def _match_notice(n, valid_ids, lengths=(6, 5, 4)):
        """Try first-half digit lengths in order; return (title, key) for the first
        length whose assembled id is a known publication id, else None."""
        head = r"^([\s\S]*?\S)\s*\d+/\d{4}[\s\S]*?"
        for length in lengths:
            pattern = head + rf"00(\d{{{length}}})\xad(\d+)"
            if m := re.search(pattern, n):
                key = m.group(2) + m.group(3)
                if key in valid_ids:
                    return m.group(1), key
        return None

    return


@app.cell
def _():
    # from kreuzberg import ExtractionConfig, PdfConfig, HierarchyConfig

    # pdf_extraction_config = ExtractionConfig(
    #     pdf_options=PdfConfig(
    #         extract_metadata=True,
    #         hierarchy=HierarchyConfig(
    #             enabled=True,
    #             k_clusters=6,
    #             include_bbox=True,
    #             ocr_coverage_threshold=0.8,
    #         ),
    #     ),
    #     include_document_structure=True,
    # )
    # pdf_extraction_config.include_document_structure
    return


@app.cell
def _():
    # extract_downloaded_files(
    #                     render_notices_sequential(
    #                         urls=notice_documents[0].get("download_urls", [])[
    #                             :1
    #                         ],  # Grabs the first url only.
    #                         api_key=ted_apikey,
    #                         language=lang_iso,
    #                         output_format=file_format,
    #                     ),
    #                     file_format=file_format.lower(),
    #                 )
    return


@app.cell
def _():
    # processing_results = (
    #     inf_client.run_batch_inference(
    #         notice_documents,
    #         message_builder=lambda doc: [
    #             {"role": "system", "content": str(instruction)},
    #             {
    #                 "role": "user",
    #                 "content": str(
    #                     extract_downloaded_files(
    #                         render_notices_sequential(
    #                             urls=doc.get("download_urls", [])[
    #                                 :1
    #                             ],  # Grabs the first url only.
    #                             api_key=ted_apikey,
    #                             language=lang_iso,
    #                             output_format=file_format,
    #                         ),
    #                         file_format=file_format.lower(),
    #                     )[0]
    #                 ),
    #             },
    #         ],
    #         model_id=str(select_model.value),
    #         include_item=False,
    #         progress_bar=True,
    #     )
    #     if run_doc_processing.value
    #     else []
    # )
    return


@app.cell
def _():
    # pd.DataFrame(processing_results)
    return


@app.cell
def _():
    # processing_results = (
    #     inf_client.run_batch_inference(
    #         notice_documents,
    #         message_builder=lambda doc: [
    #             {"role": "system", "content": instruction},
    #             # {
    #             #     "role": "user",
    #             #     "content": "\n\n".join(
    #             #         fetch_and_extract_document(_url, max_pages=3)
    #             #         for _url in doc.get("download_urls", [])
    #             #     ),
    #             # },
    #             # Example using only the first url:
    #             {
    #                 "role": "user",
    #                 "content": fetch_and_extract_document(
    #                     doc.get("download_urls", [])[0],
    #                     max_pages=5,
    #                     download_formats=doc.get("download_formats"),
    #                     debug=True,
    #                     # api_key=ted_apikey,
    #                 ),
    #             },
    #         ],
    #         model_id=rhai_model,
    #         async_mode=True,
    #         max_workers=4,
    #         # on_item_complete=lambda index, item, result: print(
    #         #     [
    #         #         {"role": "system", "content": instruction},
    #         #         {
    #         #             "role": "user",
    #         #             "content": fetch_and_extract_document(
    #         #                 item.get("download_urls", [])[0],
    #         #                 download_formats=item.get("download_formats"),
    #         #                 debug=True,
    #         #             ),
    #         #         },
    #         #     ]
    #         # ),
    #     )
    #     if run_doc_processing.value
    #     else []
    # )
    return


@app.cell
def _():
    # contents = (
    #     pd.DataFrame(
    #         [
    #             result["choices"][0]["message"]["content"]
    #             for result in processing_results
    #             if result is not None
    #         ],
    #         columns=["content"],
    #     )
    #     if processing_results is not []
    #     else [""]
    # )
    # parsed_contents = append_rendered_yaml(contents)
    # parsed_contents
    return


@app.cell
def _():
    return


@app.cell
def _():
    # retrieve_contents = mo.ui.run_button(label="**Fetch file contents**")
    # retrieve_contents
    return


@app.cell
def _():
    # if retrieve_contents.value and notice_documents:
    #     download_format = notice_documents[0].get("download_formats")[0].upper()
    #     print(download_format)
    #     retrieve_notice_docs = fetch_and_extract_document_sparkql(
    #         list(notice_documents_df.publication_number),
    #         render=download_format,
    #         api_key=ted_apikey,
    #         show_progress=True,
    #     )
    # else:
    #     retrieve_notice_docs = []

    # retrieve_notice_docs
    return


@app.cell
def _():
    # if retrieve_contents.value and notice_documents:
    #     retrieve_notice_docs = fetch_and_extract_notice(notice_documents)
    #     retrieve_notice_docs_limited = fetch_and_extract_notice(
    #         notice_documents, max_pages=2
    #     )
    # else:
    #     retrieve_notice_docs = retrieve_notice_docs_limited = []

    # retrieve_notice_docs
    return


@app.cell
def _():
    # mo.hstack(
    #     [retrieve_notice_docs, retrieve_notice_docs_limited],
    #     justify="space-around",
    #     widths=[0.3, 0.3],
    # )
    return


@app.cell
def _():
    # def retrieve_notice_contents(
    #     notice_docs,
    #     page_size: int = 100,
    #     preferred_langs: tuple = ("ENG",),
    #     timeout: float = 10.0,
    #     user_agent: Optional[str] = None,
    #     api_key: Optional[str] = None,
    #     poll_interval: float = 2.0,
    #     max_wait: float = 10.0,
    # ) -> list:
    #     import httpx
    #     import time
    #     import certifi

    #     TED_SEARCH_URL = "https://api.ted.europa.eu/v3/notices/search"

    #     request_headers: dict[str, str] = {}
    #     if user_agent:
    #         request_headers["User-Agent"] = user_agent
    #     if api_key:
    #         request_headers["Authorization"] = f"Bearer {api_key}"

    #     def _pick_notice_url(links):
    #         """Pick (url, fmt): htmlDirect > html > pdf, preferring given languages."""
    #         for fmt in ("htmlDirect", "html", "pdf"):
    #             fmt_map = links.get(fmt) or {}
    #             if not fmt_map:
    #                 continue
    #             for lang in preferred_langs:
    #                 if lang in fmt_map:
    #                     return fmt_map[lang], fmt
    #             return next(iter(fmt_map.values()), None), fmt
    #         return None, None

    #     def _download(url: str) -> bytes:
    #         deadline = time.monotonic() + max_wait
    #         while True:
    #             response = httpx.get(
    #                 url,
    #                 follow_redirects=False,
    #                 timeout=timeout,
    #                 headers=request_headers,
    #                 verify=certifi.where(),
    #             )
    #             response.raise_for_status()
    #             if response.status_code != 202 and response.content:
    #                 return response.content
    #             if time.monotonic() >= deadline:
    #                 raise RuntimeError(
    #                     f"Document not ready (HTTP {response.status_code}, "
    #                     f"{len(response.content)} bytes) for {url}"
    #                 )
    #             retry_after = response.headers.get("Retry-After")
    #             wait = (
    #                 float(retry_after)
    #                 if retry_after and retry_after.isdigit()
    #                 else poll_interval
    #             )
    #             time.sleep(min(wait, deadline - time.monotonic()))

    #     # --- resolve real artifact links via the Search API (public, no key needed) ---
    #     pub_numbers = [
    #         d["publication_number"]
    #         for d in notice_docs
    #         if d.get("publication_number")
    #     ]
    #     links_by_pubnum = {}
    #     for i in range(0, len(pub_numbers), page_size):
    #         batch = pub_numbers[i : i + page_size]
    #         body = {
    #             "query": "publication-number IN (" + " ".join(batch) + ")",
    #             "fields": ["publication-number", "links"],
    #             "limit": page_size,
    #             "page": 1,
    #             "paginationMode": "PAGE_NUMBER",
    #         }
    #         resp = httpx.post(TED_SEARCH_URL, json=body, timeout=timeout)
    #         resp.raise_for_status()
    #         for notice in resp.json().get("notices", []):
    #             links_by_pubnum[notice.get("publication-number")] = notice.get(
    #                 "links", {}
    #             )

    #     # --- download each notice's contents ---
    #     for d in notice_docs:
    #         links = links_by_pubnum.get(d.get("publication_number"), {})
    #         url, fmt = _pick_notice_url(links)
    #         d["notice_source_url"] = url
    #         d["notice_format"] = fmt
    #         if url:
    #             content = _download(url)
    #             if fmt in ("htmlDirect", "html"):
    #                 d["notice_content"] = content.decode("utf-8", errors="replace")
    #             else:
    #                 d["notice_content"] = content  # raw bytes (e.g. pdf)
    #         else:
    #             d["notice_content"] = None
    #     return notice_docs
    return


if __name__ == "__main__":
    app.run()
