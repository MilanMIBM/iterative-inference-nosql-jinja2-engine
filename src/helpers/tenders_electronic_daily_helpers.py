from typing import Optional, Dict, List, Any
import pandas as pd
import requests
import json


def build_additional_fields(
    id_groups: List[List[str]],
    default_fields: Optional[List[str]] = None,
) -> List[str]:
    """
    Flatten a list of lists of field ids into a single, de-duplicated list
    suitable for use as ``additional_fields``.

    Args:
        id_groups (List[List[str]]): Groups of field ids to combine.
        default_fields (List[str], optional): Fields already present in the
            default set. Any id matching one of these is dropped to prevent
            duplicates.

    Returns:
        List[str]: De-duplicated ids, excluding any that appear in
        ``default_fields``, preserving first-seen order.
    """
    excluded = set(default_fields or [])
    seen = set()
    additional_fields = []
    for group in id_groups:
        for field_id in group:
            if field_id in excluded or field_id in seen:
                continue
            seen.add(field_id)
            additional_fields.append(field_id)
    return additional_fields


def search_ted_notices(
    organization_name: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 10,
    page: int = 1,
    additional_fields: Optional[List[str]] = None,
    return_only_notices=True,
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
        return_only_notices (boolean): Returns only the notice items as part of a dataframe

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
        "onlyLatestVersions": True,
    }

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "TED-API-Client/1.0",  # Required per TED API docs
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        if return_only_notices:
            response_df = pd.DataFrame(response.json())
            notices = response_df.notices if "notices" in response_df else []
            # An empty result set still yields a well-formed (empty) DataFrame so
            # downstream filtering/`.columns` access stays valid.
            return pd.json_normalize(notices, max_level=0)
        else:
            return response.json()

    except requests.exceptions.RequestException as e:
        error = {
            "error": f"API request failed: {str(e)}",
            "status_code": (
                getattr(e.response, "status_code", None)
                if hasattr(e, "response")
                else None
            ),
            "response_text": (
                getattr(e.response, "text", None) if hasattr(e, "response") else None
            ),
        }
        # Keep the return type consistent with the success path: callers that
        # requested notices always get a DataFrame (here, an empty one carrying
        # the error in its `.attrs`) so they never have to special-case a dict.
        if return_only_notices:
            empty = pd.DataFrame()
            empty.attrs["error"] = error
            return empty
        return error


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

    def filter_flat_structure(data_str: str, extract_text_only: bool = False) -> str:
        """Filter flat language dictionary structure"""
        try:
            if pd.isna(data_str):
                return data_str

            # Parse JSON string
            data_dict = json.loads(data_str) if isinstance(data_str, str) else data_str
            if not isinstance(data_dict, dict):
                return data_str

            # Filter to keep only specified languages (case insensitive)
            languages_lower = [lang.lower() for lang in languages_to_keep]
            filtered_dict = {
                k: v for k, v in data_dict.items() if k.lower() in languages_lower
            }

            # NEW: Extract text only if requested
            if extract_text_only and filtered_dict:
                # Return just the first available title text
                return list(filtered_dict.values())[0]

            return (
                json.dumps(filtered_dict, ensure_ascii=False) if filtered_dict else "{}"
            )

        except (json.JSONDecodeError, TypeError, AttributeError):
            return data_str

    def filter_nested_structure(data_str: str) -> str:
        """Filter nested structure like links with format->language hierarchy"""
        try:
            if pd.isna(data_str):
                return data_str

            # Parse JSON string
            data_dict = json.loads(data_str) if isinstance(data_str, str) else data_str
            if not isinstance(data_dict, dict):
                return data_str

            filtered_dict = {}
            languages_lower = [lang.lower() for lang in languages_to_keep]

            # Essential codes to always preserve (case insensitive)
            essential_codes = ["mul", "all", "default"] if preserve_essential else []

            for format_key, format_data in data_dict.items():
                if isinstance(format_data, dict):
                    # Filter languages within this format
                    filtered_languages = {}

                    for k, v in format_data.items():
                        # Keep if it's in our language list OR it's an essential code
                        if k.lower() in languages_lower or k.lower() in essential_codes:
                            filtered_languages[k] = v

                    if filtered_languages:
                        filtered_dict[format_key] = filtered_languages
                else:
                    # If it's not nested, keep as is
                    filtered_dict[format_key] = format_data

            return (
                json.dumps(filtered_dict, ensure_ascii=False) if filtered_dict else "{}"
            )

        except (json.JSONDecodeError, TypeError, AttributeError):
            return data_str

    def filter_links_structure(data_str: str) -> str:
        """Special handling for links to preserve all URLs while filtering languages"""
        try:
            if pd.isna(data_str):
                return data_str

            # Parse JSON string
            data_dict = json.loads(data_str) if isinstance(data_str, str) else data_str
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
                        if k.lower() in languages_lower or k.lower() in essential_codes:
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

    # Guard against non-DataFrame input (e.g. an empty result set returned as a
    # dict/None) -- return it unchanged rather than raising.
    if not isinstance(df, pd.DataFrame):
        return df

    # Make a copy of the dataframe
    df_filtered = df.copy()

    # Nothing to filter if the column isn't present (e.g. no notice-title in
    # the result set) -- return the dataframe unchanged rather than raising.
    if column_name not in df_filtered.columns:
        return df_filtered

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


def format_links_as_markdown(links_data) -> str:
    """Convert a TED links structure into discrete markdown links.

    The TED ``links`` column is stored as a JSON string such as::

        {"xml": {"MUL": "https://ted.europa.eu/en/notice/44552-2026/xml"},
         "pdf": {"ENG": "https://ted.europa.eu/en/notice/44552-2026/pdf"}, ...}

    When that raw JSON string is dropped into a table cell, front-ends that
    auto-detect URLs greedily include any character adjacent to the URL in the
    href -- the trailing JSON punctuation (``"},``) became ``.../pdf%22%7D%2C``,
    and a wrapping markdown link ``](url)`` became ``.../pdf)``. The only format
    the auto-linkifier handles correctly is a bare URL bounded by whitespace, so
    each URL is emitted on its own line with a plain-text label and no adjacent
    punctuation.

    Args:
        links_data: A links dict or JSON string of the structure described above.

    Returns:
        A newline-separated string of ``label: url`` entries (each URL bounded by
        whitespace), or the original value unchanged if it cannot be parsed.
    """
    try:
        if pd.isna(links_data):
            return links_data
    except (TypeError, ValueError):
        pass

    try:
        data_dict = (
            json.loads(links_data) if isinstance(links_data, str) else links_data
        )
    except (json.JSONDecodeError, TypeError):
        return links_data

    if not isinstance(data_dict, dict):
        return links_data

    parts = []
    for format_key, format_data in data_dict.items():
        if isinstance(format_data, dict):
            for lang, url in format_data.items():
                if isinstance(url, str) and url:
                    parts.append(f"{format_key} ({lang}): {url}")
        elif isinstance(format_data, str) and format_data:
            parts.append(f"{format_key}: {format_data}")

    return "\n".join(parts) if parts else (links_data if data_dict else "")


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
    """Convenience function specifically for links column.

    Always filters the nested format->language link structure down to the
    requested languages. When ``extract_text_only`` is True the filtered links
    are additionally rendered as discrete markdown links so URL auto-detection
    in table cells does not over-capture the surrounding JSON punctuation (which
    produced broken links such as ``.../pdf%22%7D%2C``).
    """
    df_filtered = filter_languages_in_column(
        df, "links", languages, "nested", extract_text_only=False
    )

    if (
        extract_text_only
        and isinstance(df_filtered, pd.DataFrame)
        and "links" in df_filtered.columns
    ):
        df_filtered = df_filtered.copy()
        df_filtered["links"] = df_filtered["links"].apply(format_links_as_markdown)

    return df_filtered


def add_link_type_column(
    df: pd.DataFrame,
    link_type: str,
    languages: Optional[List[str]] = None,
    source_column: str = "links",
) -> pd.DataFrame:
    """Append a ``<link_type>-link`` column holding only that link type's URLs.

    Pulls the URLs for a single TED link type (e.g. ``pdf``, ``xml``, ``html``,
    ``pdfs``, ``htmlDirect``) out of the nested ``links`` structure and writes
    them into a new column named ``<link_type>-link`` at the end of each row.

    The cell value is a single bare URL string when the type resolves to one
    URL, or a Python list of URLs when several remain (e.g. multiple languages).
    Bare URLs avoid the adjacent-character over-capture that breaks table cell
    linkifying (see [format_links_as_markdown]).

    Args:
        df: DataFrame containing a links column.
        link_type: The link type to extract (e.g. ``"pdf"``).
        languages: Optional list of language codes to keep (case insensitive).
            Essential codes (``MUL``/``ALL``/``DEFAULT``) are always kept. When
            None, all languages for the type are kept.
        source_column: Name of the column holding the links structure.

    Returns:
        A copy of ``df`` with the new ``<link_type>-link`` column appended. Each
        cell is a URL string, a list of URL strings, or ``None`` for rows lacking
        that link type or a parseable links value.
    """
    df_result = df.copy()
    new_column = f"{link_type}-link"

    if source_column not in df_result.columns:
        df_result[new_column] = None
        return df_result

    languages_lower = (
        [lang.lower() for lang in languages] if languages is not None else None
    )
    essential_codes = ["mul", "all", "default"]

    def extract(links_value):
        try:
            if pd.isna(links_value):
                return None
        except (TypeError, ValueError):
            pass

        try:
            data_dict = (
                json.loads(links_value)
                if isinstance(links_value, str)
                else links_value
            )
        except (json.JSONDecodeError, TypeError):
            return None

        if not isinstance(data_dict, dict) or link_type not in data_dict:
            return None

        section = data_dict[link_type]
        urls = []
        if isinstance(section, dict):
            for lang, url in section.items():
                if not isinstance(url, str) or not url:
                    continue
                if (
                    languages_lower is None
                    or lang.lower() in languages_lower
                    or lang.lower() in essential_codes
                ):
                    urls.append(url)
        elif isinstance(section, str) and section:
            urls.append(section)

        if not urls:
            return None
        return urls[0] if len(urls) == 1 else urls

    df_result[new_column] = df_result[source_column].apply(extract)
    return df_result


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
    elif isinstance(data, list) and all(isinstance(item, dict) for item in data):
        return [
            {k: v for k, v in item.items() if k not in columns_to_drop} for item in data
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
