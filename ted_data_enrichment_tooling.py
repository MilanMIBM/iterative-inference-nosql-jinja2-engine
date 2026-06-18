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

    from src.helpers.tenders_electronic_daily_helpers import (
        fetch_and_extract_document,
        print_extraction_summary,
        reset_extraction_log,
    )

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
        extract_notice_documents,
    )

    from wigglystuff import SortableList

    try:
        load_all_dotenv(os.path.join(parent_dir, "config"), verbose=True)
    except:  # noqa: E722
        load_all_dotenv("config", verbose=True)
    return (
        InferenceClient,
        extract_notice_documents,
        fetch_and_extract_document,
        initialize_astradb_database,
        initialize_cloudant_database,
        initialize_hcd_database,
        initialize_mongodb_database,
        nosql_doc_browser,
        parse_yaml_documents,
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
        f"{db_context_directory_drilldown}": "notice-title",
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
def _():
    # context_files
    return


@app.cell
def _(context_files, extract_notice_documents):
    notice_documents = extract_notice_documents(context_files)
    pd.DataFrame(notice_documents)
    return (notice_documents,)


@app.cell
def _():
    # Red Hat AI Inference
    apikey = os.getenv("IBM_CLOUD_API_KEY", "")
    rhai_project_id = os.getenv("RHAI_INF_PROJECT", "")
    rhai_region = os.getenv("RHAI_INF_REGION", "us-east")
    # rhai_model = os.getenv("RHAI_INF_DEFAULT_MODEL", "gpt-oss-120b")
    rhai_model = "nvidia-nemotron-3-nano-30b-a3b-fp8"
    print(rhai_project_id)
    print(rhai_model)
    return apikey, rhai_model, rhai_project_id, rhai_region


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


@app.cell(hide_code=True)
def _():
    # import mimetypes

    # import httpx
    # from kreuzberg import (
    #     ExtractionConfig,
    #     PageConfig,
    #     detect_mime_type_from_bytes,
    #     extract_bytes_sync,
    # )

    # # TED link ``format`` keys -> MIME type, for formats that ``mimetypes``
    # # does not (or unreliably) resolves on its own.
    # _FORMAT_MIME_OVERRIDES = {
    #     "pdf": "application/pdf",
    #     "html": "text/html",
    #     "htm": "text/html",
    #     "xhtml": "application/xhtml+xml",
    #     "xml": "application/xml",
    #     "txt": "text/plain",
    #     "doc": "application/msword",
    #     "docx": (
    #         "application/vnd.openxmlformats-officedocument"
    #         ".wordprocessingml.document"
    #     ),
    # }


    # def _mime_type_for_format(fmt: "str | None") -> "str | None":
    #     """Map a TED ``download_formats`` entry to a MIME type, or None."""
    #     if not fmt:
    #         return None
    #     _key = fmt.strip().lower().lstrip(".")
    #     if _key in _FORMAT_MIME_OVERRIDES:
    #         return _FORMAT_MIME_OVERRIDES[_key]
    #     return mimetypes.guess_type(f"file.{_key}")[0]


    # def fetch_and_extract_document(
    #     url: str,
    #     max_pages: int | None = None,
    #     debug: bool = True,
    #     config: "ExtractionConfig | None" = None,
    #     mime_type: "str | None" = None,
    #     download_formats: "list[str] | str | None" = None,
    # ) -> str:
    #     """
    #     Download a file from the given URL at call time, extract its text content
    #     using Kreuzberg's bytes-based loading, optionally limit to the first
    #     `max_pages` pages, then discard the downloaded bytes.

    #     MIME type is resolved in this order of precedence:

    #     1. An explicit ``mime_type`` argument, when provided.
    #     2. The HTTP ``Content-Type`` response header.
    #     3. Automatic detection from the downloaded bytes
    #        (Kreuzberg's ``detect_mime_type_from_bytes``).
    #     4. The ``download_formats`` candidates: each format (e.g. ``"pdf"``,
    #        ``"html"``) is mapped to a MIME type and tried in order; the first
    #        one that produces non-empty extracted content wins.

    #     Args:
    #         url: The URL of the file to download and extract.
    #         max_pages: Optional maximum number of pages to include (for paginated
    #             documents like PDFs). If None, all pages are included.
    #         debug: Boolean - Prints out the returned document.
    #         config: Optional Kreuzberg ``ExtractionConfig`` controlling extraction
    #             behaviour (OCR, chunking, page selection, etc.). When None,
    #             Kreuzberg's defaults are used.
    #         mime_type: Optional explicit MIME type. When provided it takes
    #             precedence over header/auto/format detection.
    #         download_formats: Optional TED ``download_formats`` entry (or list of
    #             entries) used as a fallback to pick a MIME type when automatic
    #             detection fails. The first format that yields content is used.

    #     Returns:
    #         The extracted text content as a string.
    #     """
    #     if debug:
    #         print(f"Grabbing contents for {url}")
    #     _response = httpx.get(
    #         url,
    #         follow_redirects=True,
    #         timeout=60.0,
    #         headers={"User-Agent": "TED-API-Client/1.0"},
    #     )
    #     _response.raise_for_status()
    #     _file_bytes = _response.content

    #     # Resolve the MIME type by precedence: explicit -> header -> auto-sniff.
    #     _header_mime = (
    #         _response.headers.get("content-type", "").split(";")[0].strip() or None
    #     )
    #     _mime_type = mime_type or _header_mime
    #     if not _mime_type:
    #         try:
    #             _mime_type = detect_mime_type_from_bytes(_file_bytes) or None
    #         except Exception:
    #             _mime_type = None

    #     # Build the ordered list of MIME types to attempt. The auto/header
    #     # resolved type is tried first, then each ``download_formats`` candidate
    #     # as a fallback (de-duplicated, preserving order).
    #     if isinstance(download_formats, str):
    #         _formats = [download_formats]
    #     else:
    #         _formats = list(download_formats or [])
    #     _candidates: list[str | None] = []
    #     for _mt in [_mime_type, *(_mime_type_for_format(f) for f in _formats)]:
    #         if _mt and _mt not in _candidates:
    #             _candidates.append(_mt)
    #     if not _candidates:
    #         _candidates.append(_mime_type)  # may be None; let Kreuzberg decide

    #     # When ``max_pages`` is requested we need Kreuzberg to return per-page
    #     # content (``result.pages``); the extracted text itself contains no
    #     # form-feed/page delimiters to split on. Force ``extract_pages`` on,
    #     # preserving any other page settings the caller supplied.
    #     _config = config
    #     if max_pages is not None:
    #         _existing_pages = getattr(config, "pages", None)
    #         _config = ExtractionConfig(
    #             pages=PageConfig(
    #                 extract_pages=True,
    #                 insert_page_markers=getattr(
    #                     _existing_pages, "insert_page_markers", None
    #                 ),
    #                 marker_format=getattr(_existing_pages, "marker_format", None),
    #             )
    #         )
    #         if config is not None and debug:
    #             print(
    #                 "  note: max_pages set -> using a page-extraction config; "
    #                 "other custom config fields are not applied"
    #             )

    #     try:
    #         _result = None
    #         _last_error: "Exception | None" = None
    #         for _mt in _candidates:
    #             try:
    #                 _attempt = extract_bytes_sync(
    #                     _file_bytes, mime_type=_mt, config=_config
    #                 )
    #             except Exception as _exc:  # try the next candidate format
    #                 _last_error = _exc
    #                 if debug:
    #                     print(f"  extract failed for mime_type={_mt!r}: {_exc}")
    #                 continue
    #             # Keep the first attempt as a fallback result, but prefer the
    #             # first candidate that actually yields non-empty content.
    #             if _result is None:
    #                 _result = _attempt
    #             if getattr(_attempt, "content", "").strip():
    #                 _result = _attempt
    #                 if debug and _mt != _candidates[0]:
    #                     print(f"  using fallback mime_type={_mt!r}")
    #                 break
    #         if _result is None:
    #             raise _last_error or RuntimeError(
    #                 f"Could not extract document from {url}"
    #             )
    #     finally:
    #         del _file_bytes

    #     if max_pages is not None:
    #         _pages = getattr(_result, "pages", None) or []
    #         if _pages:
    #             _output = "\f".join(
    #                 _page.get("content", "") for _page in _pages[:max_pages]
    #             )
    #         else:
    #             # No per-page data available (e.g. non-paginated format); fall
    #             # back to returning the full content unchanged.
    #             _output = _result.content
    #         if debug:
    #             print(_output)
    #         return _output

    #     if debug:
    #         print(_result.content)

    #     return _result.content
    return


@app.cell
def _():
    test_url = ["https://ted.europa.eu/en/notice/115434-2025/pdf"]
    test_formats = ["pdf"]
    return test_formats, test_url


@app.cell
def _(fetch_and_extract_document, test_formats, test_url):
    test_sample = fetch_and_extract_document(
        test_url[0],
        # max_pages=5,
        download_formats=test_formats,
        debug=False,
        return_full=True,
    )
    test_sample
    return (test_sample,)


@app.cell
def _(test_sample):
    sampled = {
        name: getattr(test_sample, name)
        for name, attr in type(test_sample).__dict__.items()
        if isinstance(attr, (property, type(type(test_sample).content)))
    }
    sampled
    return


@app.cell
def _(test_sample):
    sample = test_sample.__doc__
    mo.md(sample)
    return


@app.cell
def _():
    # lambda doc: [
    #     {"role": "system", "content": instruction},
    #     {
    #         "role": "user",
    #         "content": fetch_and_extract_document(
    #             doc.get("download_urls", [])[0],
    #             download_formats=doc.get("download_formats"),
    #         ),
    #     },
    # ]
    # Test run on a single example doc from notice_documents:
    # _example_doc = notice_documents[0]
    # print(_example_doc.get("download_urls")[0])
    # print(_example_doc)
    # _test_messages = [
    #     {"role": "system", "content": instruction},
    #     {
    #         "role": "user",
    #         "content": fetch_and_extract_document(
    #             _example_doc.get("download_urls")[0],
    #             max_pages=5,
    #             download_formats=_example_doc.get("download_formats"),
    #         ),
    #     },
    # ]
    # _test_messages
    return


@app.cell
def _(notice_documents):
    len(notice_documents)
    return


@app.cell
def _():
    run_doc_processing = mo.ui.run_button(label="**Run LLM processing**")
    run_doc_processing
    return (run_doc_processing,)


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
    return (instruction,)


@app.cell
def _():
    ted_apikey = os.getenv("TED_API_KEY")
    print(ted_apikey[:5] + "...")
    return


@app.cell
def _(
    fetch_and_extract_document,
    inf_client,
    instruction,
    notice_documents,
    rhai_model,
    run_doc_processing,
):
    processing_results = (
        inf_client.run_batch_inference(
            notice_documents,
            message_builder=lambda doc: [
                {"role": "system", "content": instruction},
                # {
                #     "role": "user",
                #     "content": "\n\n".join(
                #         fetch_and_extract_document(_url, max_pages=3)
                #         for _url in doc.get("download_urls", [])
                #     ),
                # },
                # Example using only the first url:
                {
                    "role": "user",
                    "content": fetch_and_extract_document(
                        doc.get("download_urls", [])[0],
                        max_pages=5,
                        download_formats=doc.get("download_formats"),
                        debug=True,
                        # api_key=ted_apikey,
                    ),
                },
            ],
            model_id=rhai_model,
            async_mode=True,
            max_workers=4,
            # on_item_complete=lambda index, item, result: print(
            #     [
            #         {"role": "system", "content": instruction},
            #         {
            #             "role": "user",
            #             "content": fetch_and_extract_document(
            #                 item.get("download_urls", [])[0],
            #                 download_formats=item.get("download_formats"),
            #                 debug=True,
            #             ),
            #         },
            #     ]
            # ),
        )
        if run_doc_processing.value
        else []
    )
    return (processing_results,)


@app.cell
def _(processing_results):
    processing_results
    return


@app.cell
def _(processing_results):
    contents = (
        pd.DataFrame(
            [
                result["choices"][0]["message"]["content"]
                for result in processing_results
                if result is not None
            ],
            columns=["content"],
        )
        if processing_results is not None
        else [""]
    )
    contents
    return (contents,)


@app.cell
def _(parse_yaml_documents):
    def append_rendered_yaml(
        df, content_column="content", output_column="rendered_yaml"
    ):
        _df = df.copy()
        _df[output_column] = _df[content_column].apply(
            lambda _text: (
                parse_yaml_documents(_text) if isinstance(_text, str) else None
            )
        )
        return _df

    return (append_rendered_yaml,)


@app.cell
def _(append_rendered_yaml, contents):
    parsed_contents = append_rendered_yaml(contents)
    # decomposed_parsed_contents = pd.json_normalize(
    #     parsed_contents["rendered_yaml"]
    # ) if "rendered_yaml" in parsed_contents else parsed_contents
    # if isinstance(decomposed_parsed_contents, list) and (
    #     not decomposed_parsed_contents
    #     or all(_item is None for _item in decomposed_parsed_contents)
    # ):
    #     decomposed_parsed_contents = [""]
    # elif isinstance(decomposed_parsed_contents, pd.DataFrame):
    #     if decomposed_parsed_contents.empty:
    #         decomposed_parsed_contents = [""]
    #     else:
    #         decomposed_parsed_contents = decomposed_parsed_contents.fillna("")
    #         decomposed_parsed_contents = decomposed_parsed_contents.applymap(
    #             lambda _value: [""]
    #             if isinstance(_value, list) and not _value
    #             else _value
    #         )
    return (parsed_contents,)


@app.cell
def _(parsed_contents):
    parsed_contents
    return


@app.cell
def _():
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
