"""
SPARQL-based notice retrieval against the TED Open Data Service (ODS).

This module is a companion to ``tenders_electronic_daily_helpers`` and provides
``fetch_and_extract_document_sparkql`` - the SPARQL/ODS counterpart to that
module's ``fetch_and_extract_document``.

Why SPARQL instead of downloading the rendered document?

The TED v3 API has no endpoint that returns a published notice's HTML/PDF content
by publication number (the ``/v3/notices/{num}/{fmt}`` route is eNotices2-only and
returns ``403`` for arbitrary notices; the Search API only hands back ``links`` to
``ted.europa.eu`` URLs that are gated behind ``202`` and must be polled). The TED
Open Data Service, however, exposes the notice's *structured content* as RDF via a
public SPARQL endpoint - synchronously, with no API key and no rate-gate. For an
enrichment/profiling pipeline this is both more reliable and more useful than
scraping rendered HTML.

Endpoint (canonical, from the official ODS Python sample):
``https://publications.europa.eu/webapi/rdf/sparql``. The ODS query editor at
``https://data.ted.europa.eu/`` is a UI over this same endpoint.

Key data-model facts (verified against the live endpoint):

* Ontology prefix: ``epo: <http://data.europa.eu/a4g/ontology#>``.
* A notice is typed ``epo:Notice`` and carries its publication number as a plain
  ``xsd:string`` literal via ``epo:hasNoticePublicationNumber``.
* Publication numbers in the store are zero-padded to 8 digits before the
  ``-YYYY`` year (e.g. ``00331119-2025``). Links/UIs often show the unpadded form
  (``331119-2025``); :func:`normalize_publication_number` reconciles this.
* Each notice lives inside a named graph that may also contain *sibling* notices
  (e.g. a referenced previous notice). A naive ``?s ?p ?o`` over the graph returns
  those siblings too; the default here scopes to the **target notice's** forward
  reachable subgraph.
"""

from typing import Any, List, Optional, Union
import re

# Canonical TED Open Data Service SPARQL endpoint.
TED_SPARQL_ENDPOINT = "https://publications.europa.eu/webapi/rdf/sparql"

# eProcurement Ontology namespace.
EPO = "http://data.europa.eu/a4g/ontology#"

# Map a friendly serialization name to (HTTP Accept value, rdflib format).
# ``rdflib_format`` is only used when ``as_dataframe`` is requested (for a SELECT)
# or when the caller wants an rdflib Graph; for raw string output we return the
# bytes the endpoint serialized directly.
_RDF_FORMATS = {
    "turtle": "text/turtle",
    "ttl": "text/turtle",
    "ntriples": "application/n-triples",
    "nt": "application/n-triples",
    "json-ld": "application/ld+json",
    "jsonld": "application/ld+json",
    "rdfxml": "application/rdf+xml",
    "rdf": "application/rdf+xml",
    "xml": "application/rdf+xml",
}

# A TED publication number: 1+ digits, a hyphen, then a 4-digit year.
_PUBNUM_RE = re.compile(r"(\d{1,8})-(\d{4})")


def normalize_publication_number(value: str) -> str:
    """
    Normalize a TED publication number to the ODS-stored, zero-padded form.

    The ODS triplestore keys notices on an 8-digit, zero-padded number followed
    by the year, e.g. ``00331119-2025``. Links and the TED website frequently
    show the unpadded form (``331119-2025``). This pads the numeric part to 8
    digits. It is idempotent: an already-padded number passes through unchanged.

    Args:
        value (str): A publication number such as ``"331119-2025"`` or
            ``"00331119-2025"``.

    Returns:
        str: The zero-padded publication number, e.g. ``"00331119-2025"``.

    Raises:
        ValueError: If ``value`` does not contain a ``<digits>-<year>`` pattern.
    """
    match = _PUBNUM_RE.search(value.strip())
    if not match:
        raise ValueError(f"Not a recognizable TED publication number: {value!r}")
    number, year = match.group(1), match.group(2)
    return f"{int(number):08d}-{year}"


def publication_number_from_input(value: str) -> str:
    """
    Resolve a publication number from either a bare number or a TED URL.

    Accepts inputs like:

    * ``"331119-2025"`` / ``"00331119-2025"`` (a publication number), or
    * ``"https://ted.europa.eu/en/notice/331119-2025/html"`` (a TED URL), or
    * any string containing a ``<digits>-<year>`` token.

    The extracted number is normalized via :func:`normalize_publication_number`.

    Args:
        value (str): A publication number or a URL containing one.

    Returns:
        str: The normalized (zero-padded) publication number.

    Raises:
        ValueError: If no publication number can be found in ``value``.
    """
    return normalize_publication_number(value)


def _build_query(publication_number: str, whole_graph: bool) -> str:
    """
    Build the CONSTRUCT query for a single (already-normalized) publication number.

    When ``whole_graph`` is False (default), the result is the **target notice's
    forward-reachable subgraph**: the notice node plus every resource it
    references (transitively), following predicates outward. This excludes most
    sibling notices that merely share the named graph, while still including the
    handful of nodes the target genuinely links to.

    When ``whole_graph`` is True, every triple in the named graph that contains
    the notice is returned (simplest, but includes batched sibling notices).
    """
    if whole_graph:
        pattern = (
            f'    ?notice epo:hasNoticePublicationNumber "{publication_number}" .\n'
            "    ?s ?p ?o .\n"
        )
    else:
        # ``(!<urn:x>)*`` is a property path matching any predicate (the negated
        # set never matches the dummy IRI), so it walks the graph forward from
        # ?notice transitively. Each reached resource ?s then contributes its
        # own triples.
        pattern = (
            f'    ?notice epo:hasNoticePublicationNumber "{publication_number}" .\n'
            "    ?notice (!<urn:x>)* ?s .\n"
            "    ?s ?p ?o .\n"
        )
    return (
        f"PREFIX epo: <{EPO}>\n"
        "CONSTRUCT { ?s ?p ?o }\n"
        "WHERE {\n"
        "  GRAPH ?g {\n"
        f"{pattern}"
        "  }\n"
        "}\n"
    )


def _run_construct(
    query: str,
    accept: str,
    timeout: float,
    user_agent: Optional[str],
) -> bytes:
    """Execute a CONSTRUCT query and return the serialized RDF bytes."""
    import httpx

    headers = {"Accept": accept}
    if user_agent:
        headers["User-Agent"] = user_agent
    response = httpx.get(
        TED_SPARQL_ENDPOINT,
        params={"query": query},
        headers=headers,
        timeout=timeout,
        follow_redirects=True,
    )
    response.raise_for_status()
    return response.content


# TED public notice URL template. The website uses the UNPADDED publication
# number (e.g. ``331119-2025``). The ``xml`` artifact clears the anonymous
# ``202`` rate-gate far more readily than ``html``/``pdf`` do, which is why the
# render chain fetches XML and renders it via the API rather than downloading the
# rendered document directly.
TED_NOTICE_URL = "https://ted.europa.eu/en/notice/{num}/{fmt}"

# TED API v3 server-side render endpoint. Takes the notice XML (base64) and
# returns rendered HTML/PDF; requires a Bearer API key.
TED_RENDER_URL = "https://api.ted.europa.eu/v3/notices/render"


def _download_notice_xml(
    unpadded_number: str,
    timeout: float,
    user_agent: Optional[str],
    retries: int,
    retry_wait: float,
    debug: bool,
) -> bytes:
    """
    Download a notice's source XML from the TED website, polling through the
    ``202`` rate-gate.

    TED renders the XML artifact on demand: a ``202 Accepted`` (often with an
    empty body) means "not ready yet, retry". This re-requests until a ``200``
    with content arrives or ``retries`` is exhausted.

    Raises:
        RuntimeError: If the XML never becomes available within ``retries``.
    """
    import httpx
    import time

    url = TED_NOTICE_URL.format(num=unpadded_number, fmt="xml")
    headers = {"User-Agent": user_agent} if user_agent else {}
    last_status = None
    for attempt in range(1, max(1, retries) + 1):
        response = httpx.get(
            url, timeout=timeout, follow_redirects=True, headers=headers
        )
        last_status = response.status_code
        if response.status_code == 200 and response.content:
            if debug:
                print(f"  notice XML ready after {attempt} attempt(s) ({url})")
            return response.content
        if debug:
            print(
                f"  notice XML not ready (HTTP {response.status_code}), "
                f"attempt {attempt}/{retries}"
            )
        if attempt < max(1, retries):
            time.sleep(retry_wait)
    raise RuntimeError(
        f"Notice XML not available after {retries} attempts "
        f"(last HTTP {last_status}) for {url}"
    )


def _render_notice(
    xml_bytes: bytes,
    render_format: str,
    language: str,
    api_key: str,
    timeout: float,
) -> bytes:
    """
    Render notice XML to HTML/PDF via the TED API ``/v3/notices/render`` endpoint.

    Args:
        xml_bytes: The notice's source XML.
        render_format: ``"HTML"`` or ``"PDF"``.
        language: 2-letter language code (e.g. ``"en"``).
        api_key: TED API key (sent as a Bearer token).
        timeout: HTTP request timeout in seconds.

    Returns:
        The rendered document bytes (HTML or PDF).
    """
    import httpx
    import base64

    payload = {
        "file": base64.b64encode(xml_bytes).decode(),
        "format": render_format,
        "language": language,
    }
    response = httpx.post(
        TED_RENDER_URL,
        json=payload,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=timeout,
    )
    response.raise_for_status()
    return response.content


def fetch_and_extract_document_sparkql(
    documents: Any,
    download_type: str = "turtle",
    whole_graph: bool = False,
    as_dataframe: bool = False,
    render: Optional[str] = None,
    render_language: str = "en",
    api_key: Optional[str] = None,
    timeout: float = 60.0,
    user_agent: Optional[str] = None,
    retries: int = 8,
    retry_wait: float = 2.0,
    extract: bool = False,
    extract_config: Optional[Any] = None,
    max_pages: Optional[int] = None,
    show_progress: bool = True,
    debug: bool = False,
) -> Any:
    """
    Retrieve a TED notice from the Open Data Service via SPARQL, returning
    serialized RDF (or a pandas DataFrame) - or, with ``render``, the actual
    rendered HTML/PDF document.

    This is the SPARQL/ODS counterpart to ``fetch_and_extract_document``. By
    default it queries the public ODS SPARQL endpoint for the notice's structured
    RDF content (no API key, no ``202`` rate-gate, no polling).

    **Render mode (``render="HTML"`` or ``render="PDF"``):** the structured RDF
    is *not* the rendered document, so when you actually need the HTML/PDF this
    runs a separate chain: download the notice's source XML from the TED website
    (polling through the ``202`` gate - the ``xml`` artifact clears it far more
    readily than ``html``/``pdf``), then POST it to the TED API
    ``/v3/notices/render`` endpoint, which renders it server-side. This requires a
    TED ``api_key`` (Bearer token). The raw rendered bytes are returned: HTML as a
    ``str``, PDF as ``bytes``.

    Input is flexible - each entry may be:

    * a publication number, padded or unpadded (``"00331119-2025"`` /
      ``"331119-2025"``), or
    * a TED URL containing one (``".../notice/331119-2025/html"``), or
    * a dict with a ``publication_number`` (or ``url``) key.

    Publication numbers are normalized to the ODS-stored 8-digit zero-padded form
    automatically (see :func:`normalize_publication_number`).

    Accepts a single document or a list. A scalar input yields a scalar result; a
    list input yields a list aligned with the input (``None`` for an entry that
    could not be resolved or returned no data).

    Args:
        documents: A publication number / URL / dict, or a list of those.
        download_type (str): Serialization for the returned RDF. One of
            ``"turtle"`` (default), ``"ntriples"``, ``"json-ld"``, ``"rdfxml"``
            (aliases: ``ttl``/``nt``/``jsonld``/``rdf``/``xml``). Ignored when
            ``as_dataframe`` is True or ``render`` is set.
        whole_graph (bool): When False (default), return only the target notice's
            forward-reachable subgraph. When True, return every triple in the
            named graph containing the notice (may include batched sibling
            notices). Ignored when ``render`` is set.
        as_dataframe (bool): When True, return a pandas DataFrame of
            ``subject, predicate, object`` triples instead of a serialized
            string. The notice is fetched as N-Triples and parsed without any
            RDF library (``download_type`` is ignored in this mode). Ignored when
            ``render`` is set.
        render (str, optional): When ``"HTML"`` or ``"PDF"`` (case-insensitive),
            return the rendered document instead of RDF. Requires ``api_key``.
        render_language (str): 2-letter language code for rendering. Default
            ``"en"``.
        api_key (str, optional): TED API key (Bearer token), required for
            ``render``. Defaults to the ``TED_API_KEY`` environment variable.
        timeout (float): HTTP request timeout in seconds.
        user_agent (str, optional): ``User-Agent`` header for requests.
        retries (int): XML download attempts when rendering (poll the ``202``
            gate). Default 8.
        retry_wait (float): Seconds between XML download attempts. Default 2.0.
        extract (bool): Render mode only. When True, the rendered HTML/PDF bytes
            are run through Kreuzberg's ``extract_bytes_sync`` and the extracted
            **text** (str) is returned instead of the raw HTML ``str`` / PDF
            ``bytes``. Has no effect outside ``render`` mode (the RDF/DataFrame
            path is unchanged). Defaults to False.
        extract_config: Optional Kreuzberg ``ExtractionConfig`` passed through to
            extraction when ``extract`` is True. When ``None``, Kreuzberg's
            defaults are used (overridden by a page-extraction config if
            ``max_pages`` is set).
        max_pages (int, optional): Render+extract only. Maximum number of pages
            to include from a paginated rendered document (e.g. a PDF). ``None``
            includes all pages.
        show_progress (bool): When True (default), display a
            ``mo.status.progress_bar`` (with ``remove_on_exit=True``) that
            advances once per input document, showing the current publication
            number in its subtitle. Silently disabled if marimo is unavailable
            (e.g. when called outside a marimo context). Ignored in ``render``
            mode.
        debug (bool): When True, prints progress and the query.

    Returns:
        Without ``render`` - for a scalar input: the serialized RDF (str) or a
        pandas DataFrame (or ``None``); for a list input: a list of those.
        With ``render`` - the rendered document (HTML ``str`` / PDF ``bytes``),
        scalar-in/scalar-out, with ``None`` for entries that could not be
        rendered. With ``render`` and ``extract=True`` - the extracted text
        (``str``) of each rendered document instead of its raw bytes.

    Raises:
        ValueError: If ``download_type``/``render`` is unknown, an entry has no
            resolvable publication number, or ``render`` is set without an
            ``api_key``.
    """
    import os

    if render is not None:
        return _fetch_rendered(
            documents=documents,
            render=render,
            render_language=render_language,
            api_key=api_key if api_key is not None else os.getenv("TED_API_KEY"),
            timeout=timeout,
            user_agent=user_agent,
            retries=retries,
            retry_wait=retry_wait,
            extract=extract,
            extract_config=extract_config,
            max_pages=max_pages,
            debug=debug,
        )

    fmt_key = download_type.strip().lower()
    if fmt_key not in _RDF_FORMATS:
        raise ValueError(
            f"Unknown download_type {download_type!r}; "
            f"choose from {sorted(set(_RDF_FORMATS))}"
        )
    accept = _RDF_FORMATS[fmt_key]
    # When the caller wants a DataFrame we ask the endpoint for N-Triples and
    # parse it locally (line-oriented, no RDF library needed), regardless of
    # download_type.
    request_accept = "application/n-triples" if as_dataframe else accept

    def _pub_input(doc: Any) -> str:
        if isinstance(doc, dict):
            return doc.get("publication_number") or doc.get("url") or ""
        return doc

    scalar_input = not isinstance(documents, (list, tuple))
    items = [documents] if scalar_input else list(documents)

    # Resolve the progress bar lazily: marimo isn't a hard dependency of this
    # module, so fall back to no progress UI when it's unavailable.
    progress = None
    if show_progress:
        try:
            import marimo as mo

            progress = mo.status.progress_bar(
                total=len(items),
                title="Fetching ODS notices",
                completion_title="ODS notices complete",
                remove_on_exit=True,
            )
        except Exception:  # noqa: BLE001 - any import/context failure -> no bar
            progress = None

    results: List[Any] = []

    def _process(doc: Any, bar=None) -> None:
        raw = _pub_input(doc)
        try:
            pub = publication_number_from_input(raw)
        except ValueError as exc:
            if debug:
                print(f"Skipping unresolvable input {raw!r}: {exc}")
            results.append(None)
            return

        if bar is not None:
            # increment=0 so this only sets the subtitle; the step is advanced
            # once per document after processing.
            bar.update(increment=0, subtitle=f"Fetching {pub}")

        query = _build_query(pub, whole_graph)
        if debug:
            print(f"Querying ODS for {pub} (whole_graph={whole_graph}):\n{query}")

        content = _run_construct(query, request_accept, timeout, user_agent)
        if _is_empty_rdf(content):
            if debug:
                print(f"No RDF returned for {pub}")
            results.append(None)
            return

        if as_dataframe:
            results.append(_ntriples_to_dataframe(content))
        else:
            results.append(content.decode("utf-8", errors="replace"))

    if progress is not None:
        with progress as bar:
            for doc in items:
                _process(doc, bar=bar)
                bar.update()  # advance one step per document
    else:
        for doc in items:
            _process(doc)

    return results[0] if scalar_input else results


def _fetch_rendered(
    documents: Any,
    render: str,
    render_language: str,
    api_key: Optional[str],
    timeout: float,
    user_agent: Optional[str],
    retries: int,
    retry_wait: float,
    extract: bool = False,
    extract_config: Optional[Any] = None,
    max_pages: Optional[int] = None,
    debug: bool = False,
) -> Any:
    """
    Render mode for :func:`fetch_and_extract_document_sparkql`: download each
    notice's XML and render it to HTML/PDF via the TED API.

    Returns HTML as ``str`` and PDF as ``bytes``; scalar-in/scalar-out, with
    ``None`` for entries that fail. When ``extract`` is True, the rendered bytes
    are run through Kreuzberg and the extracted text (``str``) is returned
    instead of the raw HTML/PDF.
    """
    render_format = render.strip().upper()
    if render_format not in ("HTML", "PDF"):
        raise ValueError(f"Unknown render {render!r}; choose 'HTML' or 'PDF'")
    if not api_key:
        raise ValueError(
            "render requires a TED api_key (pass api_key=... or set TED_API_KEY)"
        )

    def _pub_input(doc: Any) -> str:
        if isinstance(doc, dict):
            return doc.get("publication_number") or doc.get("url") or ""
        return doc

    # Rendered HTML/PDF carries a deterministic MIME type, so extraction skips
    # the sibling's sniff/fallback chain and hands Kreuzberg the type directly.
    extract_mime = "text/html" if render_format == "HTML" else "application/pdf"

    # When extracting, resolve the Kreuzberg config once. ``max_pages`` forces a
    # page-extraction config so per-page content is available to slice (mirrors
    # ``fetch_and_extract_document``); otherwise the caller's config (or
    # Kreuzberg's defaults) is used as-is.
    active_extract_config = extract_config
    if extract and max_pages is not None:
        from kreuzberg import ExtractionConfig, PageConfig

        existing_pages = getattr(extract_config, "pages", None)
        active_extract_config = ExtractionConfig(
            pages=PageConfig(
                extract_pages=True,
                insert_page_markers=getattr(
                    existing_pages, "insert_page_markers", None
                ),
                marker_format=getattr(existing_pages, "marker_format", None),
            )
        )
        if extract_config is not None and debug:
            print(
                "  note: max_pages set -> using a page-extraction config; "
                "other custom extract_config fields are not applied"
            )

    def _extract_text(rendered_bytes: bytes) -> str:
        """Extract text from rendered HTML/PDF bytes via Kreuzberg."""
        from kreuzberg import extract_bytes_sync

        result = extract_bytes_sync(
            rendered_bytes, mime_type=extract_mime, config=active_extract_config
        )
        if max_pages is not None:
            pages = getattr(result, "pages", None) or []
            if pages:
                return "\f".join(p.get("content", "") for p in pages[:max_pages])
        return result.content

    scalar_input = not isinstance(documents, (list, tuple))
    items = [documents] if scalar_input else list(documents)

    results: List[Any] = []
    for doc in items:
        raw = _pub_input(doc)
        try:
            # The TED website uses the UNPADDED number in its URLs; strip the
            # zero-padding that the ODS form adds.
            padded = publication_number_from_input(raw)
            number, year = padded.split("-")
            unpadded = f"{int(number)}-{year}"
        except (ValueError, AttributeError) as exc:
            if debug:
                print(f"Skipping unresolvable input {raw!r}: {exc}")
            results.append(None)
            continue

        try:
            if debug:
                print(f"Rendering {unpadded} as {render_format}")
            xml_bytes = _download_notice_xml(
                unpadded, timeout, user_agent, retries, retry_wait, debug
            )
            rendered = _render_notice(
                xml_bytes, render_format, render_language, api_key, timeout
            )
            extracted = _extract_text(rendered) if extract else None
        except Exception as exc:  # download, render, or extract failed
            if debug:
                print(f"  render failed for {unpadded}: {exc}")
            results.append(None)
            continue

        if extract:
            results.append(extracted)  # extracted text (str)
        elif render_format == "HTML":
            results.append(rendered.decode("utf-8", errors="replace"))
        else:
            results.append(rendered)  # raw PDF bytes

    return results[0] if scalar_input else results


def _is_empty_rdf(content: Optional[bytes]) -> bool:
    """True when the endpoint returned no triples (handles Turtle/N-Triples)."""
    if not content:
        return True
    stripped = content.strip()
    if not stripped or stripped == b"# Empty TURTLE":
        return True
    # N-Triples with only comments/whitespace.
    return all(
        not line or line.startswith(b"#")
        for line in (ln.strip() for ln in stripped.splitlines())
    )


# One N-Triples line: <subject> <predicate> object . - object may be an IRI, a
# blank node, or a literal (optionally with a language tag or ^^datatype).
_NT_LINE_RE = re.compile(
    r"^\s*(?P<s><[^>]*>|_:[^\s]+)\s+"
    r"(?P<p><[^>]*>)\s+"
    r'(?P<o><[^>]*>|_:[^\s]+|".*")\s*\.\s*$'
)


def _ntriples_to_dataframe(nt_bytes: bytes):
    """
    Parse N-Triples bytes into a subject/predicate/object pandas DataFrame.

    N-Triples is line-oriented, so this needs no RDF library. IRIs are returned
    without their angle brackets; literals keep their surrounding quotes (and any
    ``@lang`` / ``^^datatype`` suffix) so the original term is recoverable.
    """
    import pandas as pd

    rows = []
    for raw in nt_bytes.decode("utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = _NT_LINE_RE.match(line)
        if not match:
            continue

        def _clean(term: str) -> str:
            return term[1:-1] if term.startswith("<") and term.endswith(">") else term

        rows.append(
            {
                "subject": _clean(match.group("s")),
                "predicate": _clean(match.group("p")),
                "object": _clean(match.group("o")),
            }
        )
    return pd.DataFrame(rows, columns=["subject", "predicate", "object"])
