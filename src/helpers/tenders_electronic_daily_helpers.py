from typing import Callable, Optional, Dict, List, Any
import pandas as pd
import requests
import threading
import json
import time
import uuid
import os


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


# Fields that must always be present in the requested field set: the field we
# search on plus the identifiers needed to key/join results downstream.
REQUIRED_FIELDS = [
    "organisation-name-buyer",  # This is the field we're searching on
    "buyer-identifier",
    "notice-identifier",
]


def search_ted_notices(
    organization_name: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 10,
    page: int = 1,
    additional_fields: Optional[List[str]] = None,
    return_only_notices=True,
    use_custom_default_fields: bool = False,
    custom_default_fields: Optional[List[str]] = None,
    extra_query_filters: Optional[List[str]] = None,
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
        use_custom_default_fields (bool): When True, replace the built-in default
            field set with ``custom_default_fields``. The fields in
            ``REQUIRED_FIELDS`` (organisation-name-buyer, buyer-identifier,
            notice-identifier) are always included regardless.
        custom_default_fields (List[str], optional): The replacement default field
            set to use when ``use_custom_default_fields`` is True.
        extra_query_filters (List[str], optional): Additional TED expert-query
            clauses to AND into the search filter. Each entry must already be
            valid TED query syntax, e.g.
            ``"contract-nature IN (services supplies combined)"`` or
            ``'place-of-performance IN (NOR)'``.

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

    # Append any caller-supplied filter clauses (already valid TED query syntax),
    # e.g. "contract-nature IN (services supplies combined)".
    if extra_query_filters:
        query_parts.extend(f for f in extra_query_filters if f)

    # Join with AND
    expert_query = " AND ".join(query_parts)

    # Use field names that are confirmed to exist in TED
    if use_custom_default_fields:
        default_fields = list(custom_default_fields or [])
    else:
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

    # The required fields must always be present, even with a custom default set.
    default_fields = REQUIRED_FIELDS + [
        f for f in default_fields if f not in REQUIRED_FIELDS
    ]

    if additional_fields:
        # Preserve order while de-duplicating, rather than set() which scrambles it.
        seen = set()
        fields = []
        for field in default_fields + additional_fields:
            if field not in seen:
                seen.add(field)
                fields.append(field)
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
                json.loads(links_value) if isinstance(links_value, str) else links_value
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


# Default fields used to build a buyer profile, mirroring the set used in the
# tender_context_intelililililigence marimo notebook.
DEFAULT_BUYER_PROFILE_FIELDS = [
    "organisation-name-buyer",
    "organisation-identifier-buyer",
    "organisation-country-buyer",
    "organisation-city-buyer",
    "organisation-street-buyer",
    "organisation-internet-address-buyer",
    "organisation-email-buyer",
    "organisation-tel-buyer",
    "notice-identifier",
    "notice-title",
    "publication-number",
    "description-proc",
    "total-value",
    "total-value-cur",
    "result-value-notice",
    "result-value-cur-notice",
    "additional-information",
    "additional-info-proc",
]

# Default Jinja2 template used to render a buyer profile document, matching the
# template_with_coupled_fields used in the tender_context_intelililililigence
# marimo notebook.
DEFAULT_BUYER_PROFILE_TEMPLATE = os.getenv(
    "JSON_DOCUMENT_TEMPLATE",
    "examples/jinja2_templates/tender_org_profiler_with_coupled_fields_v2.yaml.j2",
)


def build_buyer_profile_context(
    org_name: str,
    *,
    start_date: Optional[str] = None,
    language: str = "eng",
    preferred_file_format: str = "pdf",
    profiling_period_to: Optional[str] = None,
    extra_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build the per-org template context, mirroring the notebook's defaults.

    Produces the same ``additional_context`` shape as the
    ``tender_context_intelililililigence`` notebook
    (``org_profile_name``/``language``/``preferred_file_format``/
    ``profiling_period_from``/``profiling_period_to``). Anything passed via
    ``extra_context`` overrides these defaults, so callers can add keys or
    replace the defaults entirely.

    Args:
        org_name: The organization name (bound to ``org_profile_name``).
        start_date: Search start date (bound to ``profiling_period_from``).
        language: Default ``language`` value.
        preferred_file_format: Default ``preferred_file_format`` value.
        profiling_period_to: Period end; defaults to today (``YYYY-MM-DD``).
        extra_context: Caller-supplied values that take precedence over the
            defaults above.

    Returns:
        The merged context dict.
    """
    context = {
        "org_profile_name": str(org_name),
        "language": language,
        "preferred_file_format": preferred_file_format,
        "profiling_period_from": str(start_date),
        "profiling_period_to": profiling_period_to or time.strftime("%Y-%m-%d"),
    }
    context.update(extra_context or {})
    return context


def build_buyer_profiles(
    organization_names: List[str],
    *,
    render_template_from_dataframe: Callable[..., Dict[str, Any]],
    template: str = DEFAULT_BUYER_PROFILE_TEMPLATE,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 20,
    buyer_profile_fields: Optional[List[str]] = None,
    extra_query_filters: Optional[List[str]] = None,
    language: Any = "eng",
    preferred_file_format: str = "pdf",
    extra_context: Optional[Dict[str, Any]] = None,
    context_builder: Optional[
        Callable[..., Dict[str, Any]]
    ] = build_buyer_profile_context,
    coupled_fields: Optional[Dict[str, Dict[str, str]]] = None,
    is_path: bool = True,
    search_fn: Callable[..., Any] = search_ted_notices,
    show_progress: bool = True,
    add_uuid: bool = False,
    uuid_field: str = "uuid",
) -> List[Dict[str, Any]]:
    """Build a buyer profile document for each organization name.

    For every name in ``organization_names`` this searches TED notices (using the
    same fixed parameters for all orgs) and renders ``template`` against the
    resulting dataframe, exactly as the ``tender_context_intelililililigence``
    notebook does for a single org. Each result is collected as a
    ``{"org_name": <name>, "language": <lang>, "buyer_profile_doc": <doc>}`` record.

    If ``language`` is a list/tuple of more than one value, a separate profile is
    produced for each org *and* each language (the org is searched once and the
    template re-rendered per language), yielding one record per org x language.

    Every input is passable but has a default applied inside: ``buyer_profile_fields``
    falls back to ``DEFAULT_BUYER_PROFILE_FIELDS``, and the per-org template
    context is produced by ``context_builder`` (defaults to
    :func:`build_buyer_profile_context`) with ``extra_context`` merged in on top.

    Args:
        organization_names: Organization names to profile.
        render_template_from_dataframe: The renderer (injected to avoid a circular
            import); typically
            ``src.helpers.nosql_database_helper_functions.render_template_from_dataframe``.
        template: Path to a ``.j2`` template (or its source text if ``is_path``
            is False). Defaults to ``DEFAULT_BUYER_PROFILE_TEMPLATE`` (the
            coupled-fields v2 template).
        start_date: Search start date (YYYY-MM-DD), shared across all orgs.
        end_date: Search end date (YYYY-MM-DD), shared across all orgs.
        limit: Max notices to retrieve per org.
        buyer_profile_fields: Fields to request; defaults to
            ``DEFAULT_BUYER_PROFILE_FIELDS``.
        extra_query_filters: Additional TED expert-query clauses AND-ed into the
            search filter for every org, e.g.
            ``["contract-nature IN (services supplies combined)"]``. Each entry
            must be valid TED query syntax. Passed through to ``search_fn``.
        language: ``language`` value injected into the template context. May be a
            single string or a list/tuple of language codes; multiple languages
            fan out to one profile per org per language.
        preferred_file_format: ``preferred_file_format`` value for the context.
        extra_context: Additional fixed context merged into each render; these
            keys take precedence over the context builder's defaults.
        context_builder: Callable that builds the per-org context. Receives
            ``org_name`` and the keyword args ``start_date``, ``language``,
            ``preferred_file_format``, ``extra_context``. Defaults to
            :func:`build_buyer_profile_context`.
        coupled_fields: Optional row-aligned field mapping passed through to the
            renderer.
        is_path: Whether ``template`` is a path (True) or source text (False).
        search_fn: The notice search function (defaults to ``search_ted_notices``).
        show_progress: When True (default), display a ``mo.status.progress_bar``
            that advances once per organization name, showing the current org in
            its subtitle. Silently disabled if marimo is unavailable (e.g. when
            called outside a marimo context).
        add_uuid: When True, add a ``uuid_field`` key to each record holding a
            freshly generated ``str(uuid.uuid4()).upper()`` (a distinct UUID per
            document/record). Defaults to False.
        uuid_field: Name of the record key to store the generated UUID under when
            ``add_uuid`` is True. Defaults to ``"uuid"``.

    Returns:
        A list of ``{"org_name": str, "language": str, "buyer_profile_doc":
        Dict[str, Any]}`` records, one per organization name (and per language
        when several are given). Input order is preserved, org-major then
        language. When ``add_uuid`` is True, each record also carries a
        ``uuid_field`` key with an uppercased UUID4 string.
    """
    fields = buyer_profile_fields or DEFAULT_BUYER_PROFILE_FIELDS

    # Normalize language into a list so single-value and multi-value callers
    # share one code path (one profile rendered per language).
    if isinstance(language, (list, tuple)):
        languages = list(language)
    else:
        languages = [language]

    # Resolve the progress bar lazily: marimo isn't a hard dependency of this
    # module, so fall back to no progress UI when it's unavailable.
    progress = None
    if show_progress:
        try:
            import marimo as mo

            progress = mo.status.progress_bar(
                total=len(organization_names),
                title="Building buyer profiles",
                completion_title="Buyer profiles complete",
                remove_on_exit=True,
            )
        except Exception:  # noqa: BLE001 - any import/context failure -> no bar
            progress = None

    results: List[Dict[str, Any]] = []

    def _process(org_name: str, bar=None) -> None:
        if bar is not None:
            # increment=0 so this only sets the subtitle; the step is advanced
            # once per org after processing.
            bar.update(increment=0, subtitle=f"Profiling {org_name}")

        # Search once per org; the language only affects the rendered context.
        buyer_profile = search_fn(
            organization_name=str(org_name),
            start_date=start_date,
            end_date=end_date,
            limit=int(limit),
            use_custom_default_fields=True,
            custom_default_fields=fields,
            additional_fields=[],
            extra_query_filters=extra_query_filters,
        )

        for lang in languages:
            additional_context = context_builder(
                org_name,
                start_date=start_date,
                language=lang,
                preferred_file_format=preferred_file_format,
                extra_context=extra_context,
            )

            buyer_profile_doc = render_template_from_dataframe(
                template=template,
                df=buyer_profile,
                is_path=is_path,
                extra_context=additional_context,
                coupled_fields=coupled_fields,
            )

            record = {
                "org_name": str(org_name),
                "language": lang,
                "buyer_profile_doc": buyer_profile_doc,
            }
            if add_uuid:
                record[uuid_field] = str(uuid.uuid4()).upper()
            results.append(record)

    if progress is not None:
        with progress as bar:
            for org_name in organization_names:
                _process(org_name, bar=bar)
                bar.update()  # advance one step per org
    else:
        for org_name in organization_names:
            _process(org_name)

    return results


# def extract_notice_documents(profile_documents):
#     all_notices = []
#     for profile in profile_documents:
#         context = profile.get("buyer_profile_doc", {}).get("context", {})
#         org_name = context.get("org_name", "")
#         profile_name = profile.get("buyer_profile_doc", {}).get("org_profile_name", "")

#         links_by_id = {}
#         formats_by_id = {}
#         for link in context.get("org_notice_links", []):
#             nid = link.get("notice_id")
#             if nid:
#                 links_by_id.setdefault(nid, []).append(link.get("url"))
#                 formats_by_id.setdefault(nid, []).append(link.get("format"))

#         values_by_id = {}
#         for val in context.get("notice_values", []):
#             nid = val.get("notice_id")
#             if nid:
#                 values_by_id[nid] = val

#         all_ids = set(links_by_id.keys()) | set(values_by_id.keys())
#         for nid in all_ids:
#             val = values_by_id.get(nid, {})
#             urls = links_by_id.get(nid, [])
#             formats = formats_by_id.get(nid, [])
#             doc = {
#                 "org_name": org_name,
#                 "org_profile_name": profile_name,
#                 "notice_id": nid,
#                 "notice_title": val.get("notice_title", ""),
#                 "download_urls": urls,
#                 "download_formats": formats,
#             }
#             if "description_proc" in val:
#                 doc["description_proc"] = val.get("description_proc")
#             all_notices.append(doc)
#     return all_notices


def extract_notice_documents(profile_documents):
    all_notices = []
    for profile in profile_documents:
        context = profile.get("buyer_profile_doc", {}).get("context", {})
        org_name = context.get("org_name", "")
        profile_name = profile.get("buyer_profile_doc", {}).get("org_profile_name", "")

        links_by_id = {}
        formats_by_id = {}
        pubnum_by_id = {}
        for link in context.get("org_notice_links", []):
            nid = link.get("notice_id")
            if nid:
                links_by_id.setdefault(nid, []).append(link.get("url"))
                formats_by_id.setdefault(nid, []).append(link.get("format"))
                pubnum_by_id.setdefault(nid, link.get("publication_number"))

        values_by_id = {}
        for val in context.get("notice_values", []):
            nid = val.get("notice_id")
            if nid:
                values_by_id[nid] = val

        all_ids = set(links_by_id.keys()) | set(values_by_id.keys())
        for nid in all_ids:
            val = values_by_id.get(nid, {})
            urls = links_by_id.get(nid, [])
            formats = formats_by_id.get(nid, [])
            doc = {
                "org_name": org_name,
                "org_profile_name": profile_name,
                "notice_id": nid,
                "publication_number": pubnum_by_id.get(nid, ""),
                "notice_title": val.get("notice_title", ""),
                "download_urls": urls,
                "download_formats": formats,
            }
            if "description_proc" in val:
                doc["description_proc"] = val.get("description_proc")
            all_notices.append(doc)
    return all_notices


# TED link ``format`` keys -> MIME type, for formats that the stdlib
# ``mimetypes`` module does not (or unreliably) resolves on its own.
TED_FORMAT_MIME_OVERRIDES: Dict[str, str] = {
    "pdf": "application/pdf",
    "html": "text/html",
    "htm": "text/html",
    "xhtml": "application/xhtml+xml",
    "xml": "application/xml",
    "txt": "text/plain",
    "doc": "application/msword",
    "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
}


def mime_type_for_format(fmt: Optional[str]) -> Optional[str]:
    """
    Map a TED ``download_formats`` entry to a MIME type.

    Args:
        fmt (str, optional): A TED format key such as ``"pdf"`` or ``"html"``.

    Returns:
        Optional[str]: The resolved MIME type, or ``None`` when ``fmt`` is
        empty or cannot be resolved.
    """
    import mimetypes

    if not fmt:
        return None
    key = fmt.strip().lower().lstrip(".")
    if key in TED_FORMAT_MIME_OVERRIDES:
        return TED_FORMAT_MIME_OVERRIDES[key]
    return mimetypes.guess_type(f"file.{key}")[0]


# Cross-call registry of extraction outcomes. ``fetch_and_extract_document``
# appends to this on every call; ``print_extraction_summary`` reports it.
EXTRACTION_LOG: Dict[str, List] = {"succeeded": [], "failed": []}


def reset_extraction_log() -> None:
    """Clear the recorded extraction outcomes (call before a new batch)."""
    EXTRACTION_LOG["succeeded"].clear()
    EXTRACTION_LOG["failed"].clear()


def print_extraction_summary() -> Dict[str, List]:
    """
    Print and return a summary of all succeeded/failed extractions accumulated
    since the last :func:`reset_extraction_log` (or process start).

    Returns:
        Dict[str, List]: ``{"succeeded": [(url, tries), ...],
        "failed": [(url, tries, error), ...]}``.
    """
    succeeded = EXTRACTION_LOG["succeeded"]
    failed = EXTRACTION_LOG["failed"]
    total = len(succeeded) + len(failed)
    print(
        f"\n=== Extraction summary: {len(succeeded)}/{total} succeeded, "
        f"{len(failed)} failed ==="
    )
    if succeeded:
        print(f"Succeeded ({len(succeeded)}):")
        for url, tries in succeeded:
            print(f"  - {url} (after {tries} tries)")
    if failed:
        print(f"Failed ({len(failed)}):")
        for url, tries, err in failed:
            print(f"  - {url} (after {tries} tries): {err}")
    return {"succeeded": list(succeeded), "failed": list(failed)}


# Per-thread HTTP sessions: each async worker thread gets its own
# ``requests.Session`` (isolated connection pool + cookie jar) so concurrent
# downloads don't contend on shared client state.
_thread_local = threading.local()


def _get_session() -> requests.Session:
    """Return this thread's ``requests.Session``, creating it on first use."""
    session = getattr(_thread_local, "session", None)
    if session is None:
        session = requests.Session()
        _thread_local.session = session
    return session


def fetch_and_extract_document(
    url: str,
    max_pages: Optional[int] = None,
    debug: bool = False,
    config: Optional[Any] = None,
    mime_type: Optional[str] = None,
    download_formats: Optional[Any] = None,
    timeout: float = 60.0,
    return_full: bool = False,
    user_agent: Optional[str] = None,
    retries: int = 6,
    retry_wait: float = 1.0,
    retry_backoff: float = 2.0,
    retry_max_wait: float = 30.0,
    api_key: Optional[str] = None,
) -> str:
    """
    Download a file from ``url`` and extract its text content using Kreuzberg's
    bytes-based loading, optionally limiting the result to the first
    ``max_pages`` pages, then discard the downloaded bytes.

    MIME type is resolved in this order of precedence:

    1. An explicit ``mime_type`` argument, when provided.
    2. The HTTP ``Content-Type`` response header.
    3. Automatic detection from the downloaded bytes
       (Kreuzberg's ``detect_mime_type_from_bytes``).
    4. The ``download_formats`` candidates: each format (e.g. ``"pdf"``,
       ``"html"``) is mapped to a MIME type and tried in order; the first one
       that produces non-empty extracted content wins.

    ``kreuzberg`` is imported lazily so the rest of this module can be used
    without it installed.

    Args:
        url (str): The URL of the file to download and extract.
        max_pages (int, optional): Maximum number of pages to include (for
            paginated documents like PDFs). If ``None``, all pages are included.
        debug (bool): When True, prints progress and the returned document.
        config: Optional Kreuzberg ``ExtractionConfig`` controlling extraction
            behaviour (OCR, chunking, page selection, etc.). When ``None``,
            Kreuzberg's defaults are used. Note: when ``max_pages`` is set, a
            page-extraction config is used and other custom config fields are
            not applied.
        mime_type (str, optional): Explicit MIME type. Takes precedence over
            header/auto/format detection.
        download_formats: A TED ``download_formats`` entry (or list of entries)
            used as a fallback to pick a MIME type when automatic detection
            fails. The first format that yields content is used.
        timeout (float): HTTP request timeout in seconds.
        return_full (boolean): Return full kreuzberg object and not just `result.contents`.
        user_agent (str, optional): Value sent as the ``User-Agent`` request
            header. When ``None`` (the default), no ``User-Agent`` header is
            sent.
        retries (int): Number of download+extract attempts before giving up.
            TED's ``/pdf`` route intermittently returns a non-PDF/empty body
            (which Kreuzberg then rejects, or which parses to empty content);
            retrying re-downloads the file. Must be at least 1. Defaults to 6.
        retry_wait (float): Base seconds to wait before the first retry.
            Defaults to 1.0.
        retry_backoff (float): Multiplier applied to the wait after each failed
            attempt (exponential backoff). Defaults to 2.0, so waits grow
            1s, 2s, 4s, 8s, ... to wait out throttling. Use 1.0 for a fixed
            wait.
        retry_max_wait (float): Upper bound on any single wait, in seconds.
            Defaults to 30.0.
        api_key (str, optional): TED API key (from the TED Developer Portal),
            sent as an ``Authorization: Bearer`` header on the download.
            Authenticated requests bypass the anonymous edge rate-gate that
            otherwise returns ``202 Accepted`` with an empty body. Defaults to
            the ``TED_API_KEY`` environment variable.

    Returns:
        str: The extracted text content.
    """
    import httpx
    from kreuzberg import (
        ExtractionConfig,
        PageConfig,
        detect_mime_type_from_bytes,
        extract_bytes_sync,
    )

    # TED API key: explicit arg wins, else fall back to the env var. Sent as a
    # Bearer token; authenticated requests are exempt from the anonymous edge
    # rate-gate that otherwise returns ``202 Accepted`` with an empty body.
    # api_key = api_key if api_key is not None else os.getenv("TED_API_KEY", "")
    api_key = api_key

    request_headers: dict[str, str] = {}
    if user_agent:
        request_headers["User-Agent"] = user_agent
    if api_key:
        request_headers["Authorization"] = f"Bearer {api_key}"

    # When ``max_pages`` is requested we need Kreuzberg to return per-page
    # content (``result.pages``); the extracted text itself contains no
    # form-feed/page delimiters to split on. Force ``extract_pages`` on,
    # preserving any other page settings the caller supplied.
    active_config = config
    if max_pages is not None:
        existing_pages = getattr(config, "pages", None)
        active_config = ExtractionConfig(
            pages=PageConfig(
                extract_pages=True,
                insert_page_markers=getattr(
                    existing_pages, "insert_page_markers", None
                ),
                marker_format=getattr(existing_pages, "marker_format", None),
            )
        )
        if config is not None and debug:
            print(
                "  note: max_pages set -> using a page-extraction config; "
                "other custom config fields are not applied"
            )

    def _download_and_extract() -> Any:
        """One download + extract attempt. Raises on any failure."""
        response = httpx.get(
            url,
            follow_redirects=True,
            timeout=timeout,
            headers=request_headers,
        )
        response.raise_for_status()
        # TED's ``/pdf`` route renders on demand: a ``202 Accepted`` (often with
        # an empty body) means "not ready yet, poll again". Treat it as a
        # retriable failure so the backoff loop re-requests until it is ready.
        if response.status_code == 202 or not response.content:
            raise RuntimeError(
                f"Document not ready (HTTP {response.status_code}, "
                f"{len(response.content)} bytes) for {url}"
            )
        file_bytes = response.content

        # Resolve the MIME type by precedence: explicit -> header -> auto-sniff.
        header_mime = (
            response.headers.get("content-type", "").split(";")[0].strip() or None
        )
        resolved_mime = mime_type or header_mime
        if debug:
            print(f"  header mime: {header_mime}")
        if not resolved_mime:
            try:
                resolved_mime = detect_mime_type_from_bytes(file_bytes) or None
            except Exception:
                resolved_mime = None

        if debug:
            print(f"  resolved mime: {resolved_mime}")

        # Build the ordered list of MIME types to attempt. The auto/header
        # resolved type is tried first, then each ``download_formats``
        # candidate as a fallback (de-duplicated, preserving order).
        if isinstance(download_formats, str):
            formats = [download_formats]
        else:
            formats = list(download_formats or [])
        candidates: List[Optional[str]] = []
        for mt in [resolved_mime, *(mime_type_for_format(f) for f in formats)]:
            if mt and mt not in candidates:
                candidates.append(mt)
        if not candidates:
            candidates.append(resolved_mime)  # may be None; Kreuzberg decides

        try:
            result = None
            last_error: Optional[Exception] = None
            for mt in candidates:
                try:
                    attempt = extract_bytes_sync(
                        file_bytes, mime_type=mt, config=active_config
                    )
                except Exception as exc:  # try the next candidate format
                    last_error = exc
                    if debug:
                        print(f"  extract failed for mime_type={mt!r}: {exc}")
                    continue
                # Keep the first attempt as a fallback result, but prefer the
                # first candidate that actually yields non-empty content.
                if result is None:
                    result = attempt
                if getattr(attempt, "content", "").strip():
                    result = attempt
                    if debug and mt != candidates[0]:
                        print(f"  using fallback mime_type={mt!r}")
                    break
            if result is None:
                raise last_error or RuntimeError(
                    f"Could not extract document from {url}"
                )
            # An extraction that returns empty content is treated as a failure
            # so the retry loop re-downloads (TED's throttle responses parse
            # "successfully" but yield no text).
            if not (getattr(result, "content", "") or "").strip():
                raise last_error or RuntimeError(
                    f"Extracted empty content from {url} "
                    f"(candidates tried: {candidates})"
                )
            return result
        finally:
            del file_bytes

    # Retry the whole download+extract: the bad-body failure only surfaces once
    # Kreuzberg rejects the content, so a fresh download is what actually helps.
    result = None
    last_error = None
    tries = 0
    for attempt_num in range(1, max(1, retries) + 1):
        tries = attempt_num
        if debug:
            print(f"Grabbing contents for {url}")
        try:
            result = _download_and_extract()
            break
        except Exception as exc:
            last_error = exc
            if attempt_num < max(1, retries):
                # Exponential backoff (capped) so we wait out TED throttling
                # before giving up rather than hammering it every second.
                wait = min(
                    retry_wait * (retry_backoff ** (attempt_num - 1)),
                    retry_max_wait,
                )
                if debug:
                    print(
                        f"  attempt {attempt_num}/{retries} failed "
                        f"({exc}); retrying in {wait:.1f}s"
                    )
                time.sleep(wait)
    if result is None:
        EXTRACTION_LOG["failed"].append((url, tries, str(last_error)))
        raise last_error or RuntimeError(f"Could not extract document from {url}")
    EXTRACTION_LOG["succeeded"].append((url, tries))
    print(f"Succeeded extracting {url} after {tries} tries")

    if max_pages is not None:
        pages = getattr(result, "pages", None) or []
        if pages:
            output = "\f".join(page.get("content", "") for page in pages[:max_pages])
        else:
            # No per-page data available (e.g. non-paginated format); fall back
            # to returning the full content unchanged.
            output = result.content
        if debug:
            print(output)
        return output

    if debug:
        print(result.content)

    if return_full:
        return result
    else:
        return result.content


def fetch_and_extract_notice(
    notices: Any,
    direct: bool = False,
    fmt: str = "pdf",
    preferred_langs: tuple = ("ENG",),
    page_size: int = 100,
    max_pages: Optional[int] = None,
    config: Optional[Any] = None,
    timeout: float = 60.0,
    return_full: bool = False,
    user_agent: Optional[str] = None,
    api_key: Optional[str] = None,
    retries: int = 6,
    retry_wait: float = 1.0,
    retry_backoff: float = 2.0,
    retry_max_wait: float = 30.0,
    debug: bool = False,
) -> Any:
    """
    Download TED notices straight from the API v3 document endpoint and extract
    their text - returning the extracted content (or the full Kreuzberg result),
    not mutated document dicts.

    This is the notice-oriented counterpart to ``fetch_and_extract_document``:
    the caller passes a TED publication number instead of a pre-resolved URL.

    Two resolution modes:

    * ``direct=True`` (default): the download URL is built deterministically as
      ``https://api.ted.europa.eu/v3/notices/{publication_number}/{fmt}`` - no
      Search API round-trip. Pass an ``api_key`` (Bearer token); authenticated
      requests bypass the anonymous edge rate-gate that otherwise returns
      ``202 Accepted`` with an empty body.
    * ``direct=False``: links are resolved through the public Search API in
      batches, preferring ``htmlDirect`` > ``html`` > ``pdf`` and the given
      ``preferred_langs`` (no key needed).

    Either way, each resolved URL is handed to ``fetch_and_extract_document``,
    which owns the polling/backoff and Kreuzberg extraction.

    Accepts either a single notice or a list of notices, where each notice is
    either a publication-number string or a dict containing a
    ``publication_number`` key. A scalar input yields a scalar result; a list
    input yields a list of results, positionally aligned with the input (an
    entry whose link cannot be resolved becomes ``None``).

    Args:
        notices: A publication-number string, a dict with a
            ``publication_number`` key, or a list of either.
        direct (bool): When True, build the API v3 document URL directly from
            each publication number instead of querying the Search API.
        fmt (str): Document format to request when ``direct=True`` (e.g.
            ``"pdf"``, ``"xml"``, ``"html"``). Defaults to ``"pdf"``.
        preferred_langs (tuple): Language codes to prefer when a format has
            multiple language variants (Search API mode only). Defaults to
            ``("ENG",)``.
        page_size (int): Batch size for the Search API link-resolution lookup
            (Search API mode only).
        max_pages (int, optional): Maximum number of pages to include for
            paginated documents. ``None`` includes all pages.
        config: Optional Kreuzberg ``ExtractionConfig`` (see
            ``fetch_and_extract_document``).
        timeout (float): HTTP request timeout in seconds.
        return_full (bool): Return the full Kreuzberg result instead of
            ``result.content``.
        user_agent (str, optional): ``User-Agent`` header for the download.
        api_key (str, optional): TED API key, sent as a Bearer token on the
            download to bypass the anonymous edge rate-gate. Recommended (and
            effectively required for reliability) when ``direct=True``.
        retries, retry_wait, retry_backoff, retry_max_wait: Download retry
            policy, forwarded to ``fetch_and_extract_document``.
        debug (bool): When True, prints progress.

    Returns:
        The extracted text (str) or full Kreuzberg result for a scalar input;
        a list of those (with ``None`` for unresolved entries) for a list input.
    """
    import httpx

    TED_SEARCH_URL = "https://api.ted.europa.eu/v3/notices/search"
    TED_NOTICE_URL = "https://api.ted.europa.eu/v3/notices/{num}/{fmt}"

    def _pub_number(notice: Any) -> Optional[str]:
        if isinstance(notice, dict):
            return notice.get("publication_number")
        return notice

    def _pick_notice_url(links: dict) -> tuple:
        """Pick (url, fmt): htmlDirect > html > pdf, preferring given langs."""
        for f in ("htmlDirect", "html", "pdf"):
            fmt_map = links.get(f) or {}
            if not fmt_map:
                continue
            for lang in preferred_langs:
                if lang in fmt_map:
                    return fmt_map[lang], f
            return next(iter(fmt_map.values()), None), f
        return None, None

    # Normalize to a list, remembering whether the caller passed a scalar so we
    # can return in kind.
    scalar_input = not isinstance(notices, (list, tuple))
    items = [notices] if scalar_input else list(notices)
    pub_numbers = [_pub_number(n) for n in items]

    # Resolve (publication_number -> (url, fmt)) for every input entry.
    resolved: dict = {}
    if direct:
        # Build the API v3 document URL deterministically; no Search round-trip.
        for pub in pub_numbers:
            if pub:
                resolved[pub] = (
                    TED_NOTICE_URL.format(num=pub, fmt=fmt),
                    fmt,
                )
    else:
        # Resolve real artifact links via the Search API in batches (no key).
        links_by_pubnum: dict = {}
        valid = [p for p in pub_numbers if p]
        for i in range(0, len(valid), page_size):
            batch = valid[i : i + page_size]
            body = {
                "query": "publication-number IN (" + " ".join(batch) + ")",
                "fields": ["publication-number", "links"],
                "limit": page_size,
                "page": 1,
                "paginationMode": "PAGE_NUMBER",
            }
            resp = httpx.post(TED_SEARCH_URL, json=body, timeout=timeout)
            resp.raise_for_status()
            for notice in resp.json().get("notices", []):
                links_by_pubnum[notice.get("publication-number")] = notice.get(
                    "links", {}
                )
        for pub in pub_numbers:
            resolved[pub] = _pick_notice_url(links_by_pubnum.get(pub, {}))

    results = []
    for pub in pub_numbers:
        url, used_fmt = resolved.get(pub, (None, None))
        if not url:
            if debug:
                print(f"No downloadable link resolved for {pub}")
            results.append(None)
            continue
        if debug:
            print(f"Resolved {pub} -> {used_fmt}: {url}")
        results.append(
            fetch_and_extract_document(
                url,
                max_pages=max_pages,
                debug=debug,
                config=config,
                download_formats=used_fmt,
                timeout=timeout,
                return_full=return_full,
                user_agent=user_agent,
                retries=retries,
                retry_wait=retry_wait,
                retry_backoff=retry_backoff,
                retry_max_wait=retry_max_wait,
                api_key=api_key,
            )
        )

    return results[0] if scalar_input else results
