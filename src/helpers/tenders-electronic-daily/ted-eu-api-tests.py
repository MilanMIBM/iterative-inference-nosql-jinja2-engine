import marimo

__generated_with = "0.23.9"
app = marimo.App(width="full")


@app.cell
def _():
    import marimo as mo
    from dotenv import load_dotenv
    import requests
    import certifi
    import os
    import re

    load_dotenv()
    return mo, re, requests


@app.cell
def _():
    import json
    from datetime import datetime
    from typing import Optional, Dict, List, Any

    return Any, Dict, List, Optional, json


@app.function
def get_iam_token(api_key):
    import requests
    import certifi

    return requests.post(
        "https://iam.cloud.ibm.com/identity/token",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
            "apikey": api_key,
        },
        verify=certifi.where(),
    ).json()["access_token"]


@app.cell
def _(Any, Dict, List, Optional, requests):
    def search_ted_notices(
        organization_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 10,
        page: int = 1,
        additional_fields: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Search TED notices for a specific organization by name.

        Args:
            organization_name (str): The official name of the organization
            start_date (str, optional): Start date in YYYY-MM-DD format
            end_date (str, optional): End date in YYYY-MM-DD format
            limit (int): Number of results per page (max 250)
            page (int): Page number to retrieve
            additional_fields (List[str], optional): Additional fields to include in response

        Returns:
            Dict containing the API response with notices

                Example:
            # Search for Stortinget notices
            result = search_ted_notices(
                organization_name="Stortinget",
                start_date="2024-01-01",
                end_date="2025-06-01",
            )

            # Search for Oslo Municipality notices
            result = search_ted_notices(
                organization_name="Oslo kommune"
            )
        """

        # TED Search API endpoint
        url = "https://api.ted.europa.eu/v3/notices/search"

        # Build query using TED's expected syntax
        query_parts = []

        # Use organisation-name-buyer field with text search operator (~)
        # The ~ operator searches for text containing the term
        query_parts.append(f'organisation-name-buyer~"{organization_name}"')

        # Add date filtering
        if start_date or end_date:
            if start_date and end_date:
                # Convert YYYY-MM-DD to YYYYMMDD
                start_fmt = start_date.replace("-", "")
                end_fmt = end_date.replace("-", "")
                query_parts.append(f"publication-date>={start_fmt}")
                query_parts.append(f"publication-date<={end_fmt}")
            elif start_date:
                start_fmt = start_date.replace("-", "")
                query_parts.append(f"publication-date>={start_fmt}")
            elif end_date:
                end_fmt = end_date.replace("-", "")
                query_parts.append(f"publication-date<={end_fmt}")

        # Join with AND
        expert_query = " AND ".join(query_parts)

        # Use field names that are confirmed to exist in TED
        default_fields = [
            "notice-identifier",
            "publication-date",
            "notice-title",
            "organisation-name-buyer",  # This is the field we're searching on
            "buyer-identifier",  # Keep this to get org numbers if available
            "procedure-identifier",
            "notice-type",
            "organisation-country-buyer",
        ]

        if additional_fields:
            fields = list(set(default_fields + additional_fields))
        else:
            fields = default_fields

        # Request payload
        payload = {
            "query": expert_query,
            "fields": fields,
            "page": page,
            "limit": min(limit, 250),
            "scope": "ACTIVE",
            "checkQuerySyntax": False,
            "paginationMode": "PAGE_NUMBER",
            "onlyLatestVersions": False,
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "TED-API-Client/1.0",  # Required per TED API docs
        }

        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            return {
                "error": f"API request failed: {str(e)}",
                "status_code": getattr(e.response, "status_code", None)
                if hasattr(e, "response")
                else None,
                "response_text": getattr(e.response, "text", None)
                if hasattr(e, "response")
                else None,
            }

    return (search_ted_notices,)


@app.cell
def _():
    import pandas as pd

    return (pd,)


@app.cell
def _(List, json, pd):
    def filter_languages_in_column(
        df: pd.DataFrame,
        column_name: str,
        languages_to_keep: List[str],
        structure_type: str = "flat",
        preserve_essential: bool = True,
        extract_text_only: bool = False,
    ) -> pd.DataFrame:
        """
        Filter a DataFrame column to keep only specified languages while preserving essential data.

        Parameters:
        -----------
        df : pd.DataFrame
            The input DataFrame
        column_name : str
            Name of the column to filter
        languages_to_keep : List[str]
            List of language codes to keep (e.g., ['eng', 'nor', 'swe'])
        structure_type : str
            Type of structure in the column:
            - 'flat': Direct language dict like {"eng": "title", "fra": "titre"}
            - 'nested': Nested structure like {"pdf": {"ENG": "url", "FRA": "url"}}
            - 'links': Special handling for links to preserve essential links
        preserve_essential : bool
            If True, preserves essential non-language specific entries (like "MUL" for multilingual)

        Returns:
        --------
        pd.DataFrame
            DataFrame with filtered language data
        """

        def filter_flat_structure(
            data_str: str, extract_text_only: bool = False
        ) -> str:
            """Filter flat language dictionary structure"""
            try:
                if pd.isna(data_str):
                    return data_str

                # Parse JSON string
                data_dict = (
                    json.loads(data_str) if isinstance(data_str, str) else data_str
                )
                if not isinstance(data_dict, dict):
                    return data_str

                # Filter to keep only specified languages (case insensitive)
                languages_lower = [lang.lower() for lang in languages_to_keep]
                filtered_dict = {
                    k: v
                    for k, v in data_dict.items()
                    if k.lower() in languages_lower
                }

                # NEW: Extract text only if requested
                if extract_text_only and filtered_dict:
                    # Return just the first available title text
                    return list(filtered_dict.values())[0]

                return (
                    json.dumps(filtered_dict, ensure_ascii=False)
                    if filtered_dict
                    else "{}"
                )

            except (json.JSONDecodeError, TypeError, AttributeError):
                return data_str

        def filter_nested_structure(data_str: str) -> str:
            """Filter nested structure like links with format->language hierarchy"""
            try:
                if pd.isna(data_str):
                    return data_str

                # Parse JSON string
                data_dict = (
                    json.loads(data_str) if isinstance(data_str, str) else data_str
                )
                if not isinstance(data_dict, dict):
                    return data_str

                filtered_dict = {}
                languages_lower = [lang.lower() for lang in languages_to_keep]

                # Essential codes to always preserve (case insensitive)
                essential_codes = (
                    ["mul", "all", "default"] if preserve_essential else []
                )

                for format_key, format_data in data_dict.items():
                    if isinstance(format_data, dict):
                        # Filter languages within this format
                        filtered_languages = {}

                        for k, v in format_data.items():
                            # Keep if it's in our language list OR it's an essential code
                            if (
                                k.lower() in languages_lower
                                or k.lower() in essential_codes
                            ):
                                filtered_languages[k] = v

                        if filtered_languages:
                            filtered_dict[format_key] = filtered_languages
                    else:
                        # If it's not nested, keep as is
                        filtered_dict[format_key] = format_data

                return (
                    json.dumps(filtered_dict, ensure_ascii=False)
                    if filtered_dict
                    else "{}"
                )

            except (json.JSONDecodeError, TypeError, AttributeError):
                return data_str

        def filter_links_structure(data_str: str) -> str:
            """Special handling for links to preserve all URLs while filtering languages"""
            try:
                if pd.isna(data_str):
                    return data_str

                # Parse JSON string
                data_dict = (
                    json.loads(data_str) if isinstance(data_str, str) else data_str
                )
                if not isinstance(data_dict, dict):
                    return data_str

                filtered_dict = {}
                languages_lower = [lang.lower() for lang in languages_to_keep]

                # Always preserve these essential entries for links
                essential_codes = ["mul", "all", "default"]

                for format_key, format_data in data_dict.items():
                    if isinstance(format_data, dict):
                        filtered_languages = {}

                        for k, v in format_data.items():
                            # For links, be more permissive - keep essential codes and requested languages
                            if (
                                k.lower() in languages_lower
                                or k.lower() in essential_codes
                                or k.upper()
                                in [lang.upper() for lang in languages_to_keep]
                            ):
                                filtered_languages[k] = v

                        # For links, if we have any languages, keep the format
                        if filtered_languages:
                            filtered_dict[format_key] = filtered_languages
                        # Also preserve formats that might not have language variants
                        elif not format_data:  # Empty dict
                            filtered_dict[format_key] = format_data
                    else:
                        # Always preserve non-dict entries in links
                        filtered_dict[format_key] = format_data

                return json.dumps(filtered_dict, ensure_ascii=False)

            except (json.JSONDecodeError, TypeError, AttributeError):
                return data_str

        # Make a copy of the dataframe
        df_filtered = df.copy()

        # Apply the appropriate filtering function
        if structure_type == "flat":
            df_filtered[column_name] = df_filtered[column_name].apply(
                lambda x: filter_flat_structure(x, extract_text_only)
            )
        elif structure_type == "nested":
            df_filtered[column_name] = df_filtered[column_name].apply(
                filter_nested_structure
            )
        elif structure_type == "links":
            df_filtered[column_name] = df_filtered[column_name].apply(
                filter_links_structure
            )
        else:
            raise ValueError("structure_type must be 'flat', 'nested', or 'links'")

        return df_filtered


    def safe_filter_ted_data(
        df: pd.DataFrame, languages_to_keep: List[str]
    ) -> pd.DataFrame:
        """
        Safely filter TED procurement data to keep only specified languages.

        This function specifically handles the TED data structure and preserves
        all links while filtering language-specific content.

        Parameters:
        -----------
        df : pd.DataFrame
            DataFrame containing TED data
        languages_to_keep : List[str]
            List of language codes to keep (e.g., ['eng', 'nor', 'swe'])

        Returns:
        --------
        pd.DataFrame
            Filtered DataFrame with preserved links
        """

        # Define which columns need filtering and their types
        language_columns = {
            "notice-title": "flat",
            "organisation-name-buyer": "flat",
            "links": "links",  # Special handling for links
        }

        df_result = df.copy()

        # Filter each language column appropriately
        for col_name, structure_type in language_columns.items():
            if col_name in df_result.columns:
                print(f"Filtering {col_name} with structure type: {structure_type}")
                df_result = filter_languages_in_column(
                    df_result,
                    col_name,
                    languages_to_keep,
                    structure_type=structure_type,
                    preserve_essential=True,
                )

        return df_result

    return (filter_languages_in_column,)


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
    print(default_target)
    return (default_target,)


@app.cell
def _(default_target, mo):
    target_org = mo.ui.text(label="Organization Name", value=default_target)
    from_date = mo.ui.date(label="Tenders from (date):", value="2024-01-01")
    max_items = mo.ui.number(label="Max Results:", value=100, start=1, stop=300)
    mo.hstack([target_org, from_date, max_items], justify="space-around")
    return from_date, max_items, target_org


@app.cell
def _(from_date, target_org):
    print(target_org.value, from_date.value)
    return


@app.cell
def _(mo):
    run_search_button = mo.ui.run_button(label="Search Tenders")
    run_search_button
    return (run_search_button,)


@app.cell
def _(from_date, max_items, run_search_button, search_ted_notices, target_org):
    search_example = (
        search_ted_notices(
            organization_name=target_org.value,
            start_date=str(from_date.value),
            limit=max_items.value,
        )
        if run_search_button.value
        else None
    )
    return (search_example,)


@app.cell
def _(mo, pd, search_example):
    if search_example is not None:
        df_raw = pd.DataFrame(search_example["notices"])
        df = mo.ui.dataframe(df_raw)
    else:
        df_raw = df = None
    df
    return (df_raw,)


@app.cell
def _():
    return


@app.cell
def _():
    return


@app.cell
def _():
    return


@app.cell
def _():
    return


@app.cell
def _(List, Optional, filter_languages_in_column, pd):
    def filter_notice_titles(
        df: pd.DataFrame,
        languages: List[str],
        extract_text_only: Optional[bool] = False,
    ) -> pd.DataFrame:
        """Convenience function specifically for notice-title column"""
        return filter_languages_in_column(
            df,
            "notice-title",
            languages,
            "flat",
            extract_text_only=extract_text_only,
        )


    def filter_links(
        df: pd.DataFrame,
        languages: List[str],
        extract_text_only: Optional[bool] = False,
    ) -> pd.DataFrame:
        """Convenience function specifically for links column"""
        return filter_languages_in_column(
            df, "links", languages, "nested", extract_text_only=extract_text_only
        )

    return filter_links, filter_notice_titles


@app.cell
def _():
    languages = ["eng", "ENG"]
    return (languages,)


@app.cell
def _(df_raw, filter_links, filter_notice_titles, languages, search_example):
    if search_example is not None:
        df_filtered = filter_notice_titles(
            df_raw, languages, extract_text_only=True
        )
        df_filtered = filter_links(df_filtered, languages, extract_text_only=True)
        wrap_columns = list(df_filtered)
        print(wrap_columns)
    else:
        df_filtered = wrap_columns = None
    return df_filtered, wrap_columns


@app.cell
def _(df_filtered, mo, search_example, wrap_columns):
    column_wrap = False

    if column_wrap:
        tender_table = (
            mo.ui.table(
                df_filtered,
                page_size=8,
                wrapped_columns=wrap_columns,
                freeze_columns_left=["notice-title", "links"],
            )
            if search_example is not None
            else None
        )
    else:
        tender_table = (
            mo.ui.table(
                df_filtered,
                page_size=8,
                freeze_columns_left=["notice-title", "links"],
            )
            if search_example is not None
            else None
        )

    tender_table
    return (tender_table,)


@app.cell(hide_code=True)
def _(json):
    def parse_tender_links(links_data):
        """Parse tender links data into a list of JSON dictionaries.

        Args:
            links_data: List of JSON strings to parse

        Returns:
            List of dictionaries parsed from JSON strings
        """
        parsed_links = []
        for i, link_str in enumerate(links_data):
            try:
                parsed_links.append(json.loads(link_str))
            except json.JSONDecodeError as e:
                print(f"Error parsing link at index {i}: {e}")
                continue
        return parsed_links


    def parse_notice_titles(notice_titles_data):
        """Parse notice titles data into a list of title strings.

        Args:
            notice_titles_data: List of strings or objects containing notice titles

        Returns:
            List of title strings
        """
        titles = []
        for i, title_item in enumerate(notice_titles_data):
            try:
                # First check if it's already a string
                if isinstance(title_item, str):
                    if title_item.strip():  # Only add non-empty strings
                        titles.append(title_item)
                # Then try parsing as JSON if it's not a string
                else:
                    title_dict = json.loads(str(title_item))
                    if isinstance(title_dict, dict):
                        for key, value in title_dict.items():
                            if isinstance(value, str):
                                titles.append(value)
                            elif isinstance(value, dict):
                                titles.extend(value.values())
                    elif isinstance(title_dict, str):
                        titles.append(title_dict)
            except (json.JSONDecodeError, TypeError):
                # If JSON parsing fails, try to use the raw value as string
                if title_item and str(title_item).strip():
                    titles.append(str(title_item))
                continue
        return titles


    def extract_download_links(parsed_links, link_filter=None, tender_names=None):
        """Extract download links from parsed tender links data.

        Args:
            parsed_links: List of dictionaries from parse_tender_links()
            link_filter: Optional filter ('xml', 'pdf', 'pdfs', 'html', 'htmlDirect')
            tender_names: Optional list of tender names to create name->links mapping

        Returns:
            List of URLs if tender_names=None, or dict {tender_name: [links]} if provided
        """
        if tender_names:
            # Return dict mapping tender names to their links
            result_dict = {}
            for i, link_dict in enumerate(parsed_links):
                if not isinstance(link_dict, dict):
                    continue

                # Get tender name, fallback to index if not enough names
                name = tender_names[i] if i < len(tender_names) else f"Tender_{i}"
                links = []

                if link_filter:
                    if link_filter in link_dict:
                        section = link_dict[link_filter]
                        if isinstance(section, dict):
                            links.extend(section.values())
                        elif isinstance(section, str):
                            links.append(section)
                else:
                    for key, value in link_dict.items():
                        if isinstance(value, dict):
                            links.extend(value.values())
                        elif isinstance(value, str):
                            links.append(value)

                result_dict[name] = links
            return result_dict

        else:
            # Original behavior - return flat list
            all_links = []
            for link_dict in parsed_links:
                if not isinstance(link_dict, dict):
                    continue

                if link_filter:
                    if link_filter in link_dict:
                        section = link_dict[link_filter]
                        if isinstance(section, dict):
                            all_links.extend(section.values())
                        elif isinstance(section, str):
                            all_links.append(section)
                else:
                    for key, value in link_dict.items():
                        if isinstance(value, dict):
                            all_links.extend(value.values())
                        elif isinstance(value, str):
                            all_links.append(value)

            return all_links

    return extract_download_links, parse_notice_titles, parse_tender_links


@app.cell
def _(tender_table):
    selected_tenders = tender_table.value if tender_table is not None else None
    return (selected_tenders,)


@app.cell
def _(parse_notice_titles, parse_tender_links, selected_tenders):
    tender_names = (
        parse_notice_titles(selected_tenders["notice-title"])
        if selected_tenders is not None
        else []
    )
    tender_file_links = (
        parse_tender_links(selected_tenders["links"])
        if selected_tenders is not None
        else []
    )
    return tender_file_links, tender_names


@app.cell
def _(mo, source_urls, tender_file_links, tender_names):
    mo.hstack(
        [tender_names, tender_file_links, source_urls],
        justify="space-around",
        widths=[0.3, 0.3, 0.3],
    )
    return


@app.cell
def _(extract_download_links, tender_file_links):
    # tender_download_links = extract_download_links(tender_file_links, 'pdf', tender_names)
    tender_download_links = extract_download_links(
        tender_file_links, "pdf"
    )  ### pdf filtered
    # tender_download_links
    return (tender_download_links,)


@app.cell
def _():
    # headers = {
    #     "Content-Type": "application/json",
    #     "Authorization": "Bearer " + token,
    # }
    # function_endpoint = "https://us-south.ml.cloud.ibm.com/ml/v4/deployments/deployed_stream_files_hmac_cos/predictions?version=2021-05-01"
    return


@app.cell
def _(mo, target_org):
    target = str(target_org.value.lower())
    path_target = target.replace(" ", "-")
    bucket_name = mo.ui.text(
        label="Bucket Name", value="eu-tender-based-profile-generation"
    )
    path_prefix = mo.ui.text(label="Path Prefix", value=path_target)
    mo.hstack([bucket_name, path_prefix], justify="space-around")
    return bucket_name, path_prefix


@app.cell
def _(tender_download_links):
    if tender_download_links:
        source_urls = tender_download_links
    else:
        source_urls = [
            "https://example.com/file1.pdf",
            "https://example.com/file2.csv",
        ]
    return (source_urls,)


@app.cell
def _(bucket_name, path_prefix, source_urls):
    input_data = {
        "input_data": [
            {
                "fields": ["cos_config", "source_urls", "prefix"],
                "values": [
                    [
                        {
                            "bucket_name": str(bucket_name.value),
                        },  ### Target Bucket
                        source_urls,  ### Source Urls
                        str(path_prefix.value),  ### Prefix
                    ]
                ],
            }
        ]
    }

    # ex = [
    #         {
    #             "cos_config": {
    #                 "bucket_name": str(bucket_name.value),
    #             },
    #             "source_urls": source_urls,
    #             "prefix": str(path_prefix.value),
    #         }
    # ]
    return


@app.cell
def _(mo):
    run_button = mo.ui.run_button(label="Run Deployed Function")
    run_button
    return


@app.cell
def _():
    # api_key = os.getenv("WX_APIKEY")
    # token = get_iam_token(api_key)
    return


@app.cell
def _():
    # func_run = (
    #     requests.post(url=function_endpoint, json=input_data, headers=headers)
    #     if run_button.value
    #     else None
    # )

    # func_run
    return


@app.cell
def _():
    # result_stack = (
    #     mo.hstack(
    #         [func_run.text, func_run.json()],
    #         justify="space-around",
    #         widths=[0.4, 0.4],
    #     )
    #     if func_run is not None
    #     else None
    # )
    # result_stack
    return


@app.cell
def _(mo):
    mo.md(f"""
    ### Tempfile Variant
    """)
    return


@app.cell
def _():
    # cos_config = {
    #     "access_key": os.getenv("COS_ACCESS_KEY"),
    #     "secret_key": os.getenv("COS_SECRET_KEY"),
    #     "cos_endpoint": os.getenv("COS_URL_ENDPOINT"),
    #     "bucket_name": bucket_name.value,
    # }
    # print(cos_config)
    return


@app.cell
def _():
    # import ibm_boto3
    # from ibm_botocore.client import Config

    # cos_client = ibm_boto3.client(
    #     "s3",
    #     aws_access_key_id=cos_config["access_key"],
    #     aws_secret_access_key=cos_config["secret_key"],
    #     config=Config(max_pool_connections=100),
    #     endpoint_url=cos_config["cos_endpoint"],
    # )
    # bucket_table = mo.ui.table(
    #     cos_client.list_buckets()["Buckets"],
    #     selection="single",
    #     initial_selection=[0],
    # )
    # bucket_table
    return


@app.cell
def _():
    # bucket_table.value
    return


@app.cell
def _():
    # bucket = (
    #     bucket_table.value[0]["Name"] if "Name" in bucket_table.value[0] else ""
    # )
    # bucket
    return


@app.cell
def _():
    # # bucket_objects = cos_client.list_objects_v2(Bucket=bucket)
    # bucket_objects = cos_client.list_objects_v2(
    #     Bucket=bucket, Prefix=path_prefix.value
    # )
    # drop_columns = ["ETag", "StorageClass"]
    # object_list = bucket_objects["Contents"] if "Contents" in bucket_objects else []
    # prepped_objects = drop_columns_from_input(object_list, drop_columns)
    # bucket_object_table = mo.ui.table(prepped_objects, selection="multi")
    return


@app.function
def drop_columns_from_input(data, columns_to_drop):
    """
    Drop specified columns from various data structures.

    Args:
        data: Input data (DataFrame, list of dicts, or dict)
        columns_to_drop: List of column names to drop

    Returns:
        Data in the same format as input but with specified columns removed
    """
    import pandas as pd

    # Handle pandas DataFrame
    if isinstance(data, pd.DataFrame):
        return data.drop(columns=columns_to_drop, errors="ignore")

    # Handle list of dictionaries (JSON array)
    elif isinstance(data, list) and all(
        isinstance(item, dict) for item in data
    ):
        return [
            {k: v for k, v in item.items() if k not in columns_to_drop}
            for item in data
        ]

    # Handle single dictionary
    elif isinstance(data, dict):
        return {k: v for k, v in data.items() if k not in columns_to_drop}

    # Handle marimo table data (access the underlying data)
    elif hasattr(data, "value") and isinstance(data.value, list):
        return [
            {k: v for k, v in item.items() if k not in columns_to_drop}
            for item in data.value
        ]

    # Handle other iterable types (tuple, etc.)
    elif hasattr(data, "__iter__") and not isinstance(data, (str, bytes)):
        try:
            return [
                {k: v for k, v in item.items() if k not in columns_to_drop}
                for item in data
            ]
        except (AttributeError, TypeError):
            pass

    # Return original data if type not supported
    return data


@app.cell
def _():
    return


@app.cell
def _():
    return


@app.cell
def _():
    return


@app.cell
def _():
    return


@app.cell
def _():
    # mo.hstack(
    #     [bucket_object_table, create_pdf_grid()],
    #     justify="space-around",
    #     widths=[0.5, 0.5],
    # )
    return


@app.cell
def _():
    # upload_to_cos = download_and_upload_to_cos(source_urls, prefix="streamed_tempfiles/")
    # upload_to_cos
    return


@app.cell
def _():
    # stream_to_cos = stream_upload_urls_to_cos(source_urls, prefix="streamed/")
    # stream_to_cos
    return


@app.cell
def _():
    return


@app.cell
def _():
    return


@app.cell
def _(cos_client, cos_config, extract_filename_from_headers):
    def stream_upload_urls_to_cos(source_urls, prefix=""):
        """
        Upload files from URLs to IBM Cloud Object Storage.

        Args:
            source_urls (list): List of URLs to download and upload
            prefix (str): Optional prefix for the target key
        """
        import requests
        import ibm_boto3.s3.transfer
        import io

        http_method = "GET"
        for source_url in source_urls:
            try:
                # Setup download stream
                session = requests.Session()
                response = session.request(http_method, source_url, stream=True)
                response.raise_for_status()
                # Extract actual filename from response
                filename = extract_filename_from_headers(response)
                # Combine prefix with filename for the full COS key
                target_key = f"{prefix}{filename}" if prefix else filename

                # Create a BytesIO buffer and write decompressed content
                file_buffer = io.BytesIO()
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        file_buffer.write(chunk)
                file_buffer.seek(0)  # Reset to beginning for upload

                # Upload file to COS
                conf = ibm_boto3.s3.transfer.TransferConfig(
                    multipart_threshold=1024**2,
                    max_concurrency=100,  # 1MB
                )
                cos_client.upload_fileobj(
                    file_buffer, cos_config["bucket_name"], target_key, Config=conf
                )
            except Exception as e:
                # Handle individual URL failures without breaking the loop
                print(f"Failed to upload {source_url}: {str(e)}")
                continue


    # def upload_urls_to_cos(source_urls, prefix=""): ### This one corrupts the downloads when streaming
    #     """
    #     Upload files from URLs to IBM Cloud Object Storage.

    #     Args:
    #         source_urls (list): List of URLs to download and upload
    #         prefix (str): Optional prefix for the target key
    #     """
    #     import requests
    #     import ibm_boto3.s3.transfer
    #     http_method="GET"
    #     for source_url in source_urls:
    #         try:
    #             # Setup download stream
    #             session = requests.Session()
    #             response = session.request(http_method, source_url, stream=True)
    #             response.raise_for_status()
    #             # Extract actual filename from response
    #             filename = extract_filename_from_headers(response)
    #             # Combine prefix with filename for the full COS key
    #             target_key = f"{prefix}{filename}" if prefix else filename
    #             # Upload file to COS
    #             conf = ibm_boto3.s3.transfer.TransferConfig(
    #                 multipart_threshold=1024**2, max_concurrency=100  # 1MB
    #             )
    #             cos_client.upload_fileobj(
    #                 response.raw, cos_config["bucket_name"], target_key, Config=conf
    #             )
    #         except Exception as e:
    #             # Handle individual URL failures without breaking the loop
    #             print(f"Failed to upload {source_url}: {str(e)}")
    #             continue


    def download_and_upload_to_cos(source_urls, prefix=""):
        """
        Download files from URLs to temporary files and upload them to COS.

        Args:
            source_urls (list): List of URLs to download
            prefix (str): Optional prefix for the target key

        Returns:
            list: List of target_keys for successfully uploaded files
        """
        import requests
        import tempfile
        import os
        import ibm_boto3.s3.transfer

        http_method = "GET"
        uploaded_files = []

        for source_url in source_urls:
            temp_file_path = None
            file_obj = None
            try:
                # Setup download stream
                session = requests.Session()
                response = session.request(http_method, source_url, stream=True)
                response.raise_for_status()

                # Extract actual filename from response
                filename = extract_filename_from_headers(response)
                # Combine prefix with filename for the full COS key
                target_key = f"{prefix}{filename}" if prefix else filename

                # Create temporary file
                temp_file = tempfile.NamedTemporaryFile(delete=False)
                temp_file_path = temp_file.name

                # Download to temp file
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        temp_file.write(chunk)

                temp_file.close()

                # Reopen for reading
                file_obj = open(temp_file_path, "rb")

                # Upload file to COS
                conf = ibm_boto3.s3.transfer.TransferConfig(
                    multipart_threshold=1024**2,
                    max_concurrency=100,  # 1MB
                )
                cos_client.upload_fileobj(
                    file_obj, cos_config["bucket_name"], target_key, Config=conf
                )

                uploaded_files.append(target_key)

            except Exception as e:
                # Handle individual URL failures without breaking the loop
                print(f"Failed to process {source_url}: {str(e)}")
                continue
            finally:
                # Clean up resources
                if file_obj:
                    file_obj.close()
                if temp_file_path and os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)

        return uploaded_files


    def download_urls_to_tempfiles(source_urls, prefix=""):
        """
        Download files from URLs to temporary files.

        Args:
            source_urls (list): List of URLs to download
            prefix (str): Optional prefix for the target key

        Returns:
            list: List of tuples (file_object, target_key, temp_file_path) for each successful download
        """
        import requests
        import tempfile
        import os

        http_method = "GET"
        downloaded_files = []

        for source_url in source_urls:
            try:
                # Setup download stream
                session = requests.Session()
                response = session.request(http_method, source_url, stream=True)
                response.raise_for_status()

                # Extract actual filename from response
                filename = extract_filename_from_headers(response)
                # Combine prefix with filename for the full COS key
                target_key = f"{prefix}{filename}" if prefix else filename

                # Create temporary file
                temp_file = tempfile.NamedTemporaryFile(delete=False)

                # Download to temp file
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        temp_file.write(chunk)

                temp_file.close()

                # Reopen for reading
                file_obj = open(temp_file.name, "rb")

                downloaded_files.append((file_obj, target_key, temp_file.name))

            except Exception as e:
                # Handle individual URL failures without breaking the loop
                print(f"Failed to download {source_url}: {str(e)}")
                continue

        return downloaded_files

    return


@app.cell
def _(re, unquote):
    def extract_filename_from_headers(response):
        """
        Extract the actual filename from response headers.
        Checks Content-Disposition and falls back to other methods if needed.
        Uses mimetypes library for extension mapping.
        """
        import mimetypes

        # Ensure mimetypes database is initialized with common types
        mimetypes.init()

        # Add any missing but common MIME types that might not be in the default database
        if not mimetypes.guess_extension("application/x-jsonlines"):
            mimetypes.add_type("application/x-jsonlines", ".jsonl")
        if not mimetypes.guess_extension("application/parquet"):
            mimetypes.add_type("application/parquet", ".parquet")
        if not mimetypes.guess_extension("application/x-ipynb+json"):
            mimetypes.add_type("application/x-ipynb+json", ".ipynb")
        if not mimetypes.guess_extension("application/yaml"):
            mimetypes.add_type("application/yaml", ".yaml")
        if not mimetypes.guess_extension("text/yaml"):
            mimetypes.add_type("text/yaml", ".yaml")
        if not mimetypes.guess_extension("application/toml"):
            mimetypes.add_type("application/toml", ".toml")

        # Try Content-Disposition header first
        content_disposition = response.headers.get("Content-Disposition")
        if content_disposition:
            # Look for filename= or filename*= parameters
            matches = re.findall(
                r"filename\*?=(?:([^\']*\'\')?([^;\n]*))", content_disposition
            )
            if matches:
                # Take the last match and handle encoded filenames
                encoding, filename = matches[-1]
                if encoding:
                    filename = unquote(filename)
                return filename.strip("\"'")

        # Get the URL path as fallback filename
        url_path = response.url.split("/")[-1].split("?")[0]

        # Try Content-Type for file extension
        content_type = response.headers.get("Content-Type", "").split(";")[0]
        if content_type and "." not in url_path:
            # Get extension from mimetype
            extension = mimetypes.guess_extension(content_type)
            if extension:
                return f"{url_path}{extension}"

        # Fallback to URL filename
        return url_path

    return (extract_filename_from_headers,)


@app.cell
def _():
    # import tempfile
    # import pathlib
    # import base64
    # import io


    # # Function to create a PDF viewer for selected objects with improved error handling
    # def create_pdf_preview():
    #     # Check if any objects are selected
    #     selected_objects = bucket_object_table.value

    #     if not selected_objects or len(selected_objects) == 0:
    #         return mo.md("Please select a PDF object to preview")

    #     # Get the first selected object
    #     selected_object = selected_objects[0]
    #     object_key = selected_object["Key"]

    #     # Only proceed if this is a PDF file
    #     if not object_key.lower().endswith(".pdf"):
    #         return mo.md(
    #             f"Selected file ({object_key}) is not a PDF. Please select a PDF file."
    #         )

    #     try:
    #         # Verify bucket is defined
    #         if not bucket:
    #             return mo.md(
    #                 "Error: No bucket selected. Please select a bucket first."
    #             )

    #         # First check if the object exists
    #         try:
    #             cos_client.head_object(Bucket=bucket, Key=object_key)
    #         except Exception as e:
    #             return mo.md(
    #                 f"Error: Object does not exist or is not accessible.\nBucket: {bucket}\nKey: {object_key}\nError: {str(e)}"
    #             )

    #         # Get the object from COS
    #         response = cos_client.get_object(Bucket=bucket, Key=object_key)

    #         # Read the content
    #         pdf_content = response["Body"].read()

    #         if not pdf_content:
    #             return mo.md(f"Error: PDF content is empty for {object_key}")

    #         # Create a temporary file using pathlib
    #         temp_dir = pathlib.Path(tempfile.gettempdir())
    #         temp_file_path = temp_dir / f"preview_{pathlib.Path(object_key).name}"

    #         # Write content to file
    #         temp_file_path.write_bytes(pdf_content)

    #         # Check if file was written correctly
    #         if not temp_file_path.exists() or temp_file_path.stat().st_size == 0:
    #             return mo.md(f"Error: Failed to write PDF to temporary file")

    #         # Create a PDF viewer
    #         pdf_viewer = mo.pdf(str(temp_file_path), width="100%", height="600px")

    #         return pdf_content, pdf_viewer
    #         # return mo.vstack(
    #         #     [
    #         #         mo.md(f"### Preview of: {object_key}"),
    #         #         mo.md(f"File size: {len(pdf_content)} bytes"),
    #         #         pdf_viewer,
    #         #     ]
    #         # )

    #     except Exception as e:
    #         return mo.md(f"Error retrieving PDF: {str(e)}")


    # # Display the PDF preview
    # create_pdf_preview()
    return


@app.cell
def _(bucket, bucket_object_table, cos_client, mo):
    ### Works perfectly to preview bucket pdfs in marim
    def create_pdf_preview():
        import io

        # Check selection
        selected_objects = bucket_object_table.value
        if not selected_objects:
            return mo.md("Please select a PDF object to preview")

        object_key = selected_objects[0]["Key"]
        if not object_key.lower().endswith(".pdf"):
            return mo.md("Please select a PDF file")

        try:
            # Get PDF content
            response = cos_client.get_object(Bucket=bucket, Key=object_key)
            pdf_content = response["Body"].read()

            # Create PDF viewer using BytesIO
            pdf_buffer = io.BytesIO(pdf_content)
            return mo.pdf(pdf_buffer, width="100%", height="600px")

        except Exception as e:
            return mo.md(f"Error loading PDF: {str(e)}")


    def create_pdf_grid():
        import io

        # Check selection
        selected_objects = bucket_object_table.value
        if not selected_objects:
            return mo.md("Please select PDF objects to preview")

        # Filter for PDFs only
        pdf_objects = [
            obj for obj in selected_objects if obj["Key"].lower().endswith(".pdf")
        ]
        if not pdf_objects:
            return mo.md("No PDF files selected")

        pdf_viewers = []

        for obj in pdf_objects:
            try:
                # Get PDF content
                response = cos_client.get_object(Bucket=bucket, Key=obj["Key"])
                pdf_content = response["Body"].read()

                # Create PDF viewer
                pdf_buffer = io.BytesIO(pdf_content)
                pdf_viewer = mo.vstack(
                    [
                        mo.md(f"**{obj['Key']}**"),
                        mo.pdf(pdf_buffer, width="100%", height="400px"),
                    ]
                )
                pdf_viewers.append(pdf_viewer)

            except Exception as e:
                # Add error placeholder for failed PDFs
                pdf_viewers.append(mo.md(f"**{obj['Key']}**\nError: {str(e)}"))

        # Create grid with 3 items per row
        rows = []
        for i in range(0, len(pdf_viewers), 3):
            row_items = pdf_viewers[i : i + 3]
            rows.append(mo.hstack(row_items, widths="equal", gap=1.0))

        return mo.vstack(rows, gap=1.0)


    # create_pdf_grid()
    # create_pdf_preview()
    return


@app.cell
def _():
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
