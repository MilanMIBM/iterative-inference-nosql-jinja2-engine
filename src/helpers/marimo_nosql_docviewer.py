"""A marimo document viewer for the NoSQL backends used in this project.

This is the document-store analogue of ``mo.ui.file_browser()`` (which browses
S3 / local object storage). Instead of buckets and keys it browses the
databases / keyspaces, collections / tables and JSON documents exposed by the
clients built in :mod:`src.helpers.nosql_database_helper_functions`:

    * Cloudant   - ``database -> document``        (no keyspace tier)
    * AstraDB    - ``keyspace -> collection -> document``
    * HCD        - ``keyspace -> collection -> document``
    * MongoDB    - ``database -> collection -> document``

The widget renders two navigation dropdowns (the "segment" selectors) and a
scrollable list of the documents in the selected collection, each shown with a
file-like name derived from its ``_id`` and an optional display key (see
:func:`_build_display_names`). Selecting a document loads it and exposes it on
``.value``.

Both dropdowns live inside the widget's own frontend (rather than as separate
``mo.ui.dropdown`` elements) because marimo dropdowns cannot have their option
list repointed after construction, and switching keyspace/database must rebuild
the collection list. Keeping the selectors in the anywidget lets Python observe
a single trait change and repopulate everything below it.

The cross-backend listing / fetching logic lives here rather than in
``nosql_database_helper_functions`` because it is UI-only; the actual document
reads go through :func:`retrieve_documents` from that module so the query path
stays shared with the rest of the project.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

import marimo as mo
import anywidget
import traitlets

from .nosql_database_helper_functions import (
    _detect_backend,
    _get_nested_value,
    _is_astra_compatible,
    retrieve_documents,
)


# ---------------------------------------------------------------------------
# Backend navigation: list segments / collections / documents
# ---------------------------------------------------------------------------
#
# Each backend exposes a different hierarchy. To give the widget a single mental
# model we flatten every backend to (at most) two navigable tiers above the
# document:
#
#   segment    - the top selector. Keyspace for astra/hcd, database for
#                cloudant/mongodb. ``segment_label`` names it for the UI.
#   collection - the second selector. Collection/table for astra/hcd/mongodb.
#                Cloudant has no tier below the database, so its single
#                "collection" is the database itself and the collection selector
#                is hidden.
#
# ``_id`` plus an optional display key then names each document like a file.


def _list_segments(db_client, backend: str) -> List[str]:
    """List the top navigation tier (keyspaces or databases) for *backend*."""
    if _is_astra_compatible(backend):
        try:
            admin = db_client.get_database_admin()
            return sorted(admin.list_keyspaces())
        except Exception:
            # Fall back to whatever keyspace the client is already bound to.
            current = getattr(db_client, "keyspace", None)
            return [current] if current else []

    if backend == "mongodb":
        try:
            return sorted(db_client.client.list_database_names())
        except Exception:
            return [db_client.name]

    # --- Cloudant: databases are the top (and only) tier. ---
    try:
        return sorted(db_client.get_all_dbs().get_result())
    except Exception:
        return []


def _default_segment(db_client, backend: str, segments: List[str]) -> Optional[str]:
    """Pick the segment the client is currently bound to, else the first one."""
    if _is_astra_compatible(backend):
        current = getattr(db_client, "keyspace", None)
        if current and current in segments:
            return current
    elif backend == "mongodb":
        if db_client.name in segments:
            return db_client.name
    return segments[0] if segments else None


def _list_collections(db_client, backend: str, segment: Optional[str]) -> List[str]:
    """List the collections/tables inside *segment* for *backend*.

    For Cloudant the database *is* the collection, so the database name is
    returned as the sole entry.
    """
    if _is_astra_compatible(backend):
        if not segment:
            return []
        try:
            return sorted(db_client.list_collection_names(keyspace=segment))
        except Exception:
            return []

    if backend == "mongodb":
        if not segment:
            return []
        try:
            database = (
                db_client if db_client.name == segment else db_client.client[segment]
            )
            return sorted(database.list_collection_names())
        except Exception:
            return []

    # --- Cloudant: no sub-tier; the database name doubles as the collection. ---
    return [segment] if segment else []


def _collection_client(db_client, backend: str, segment: Optional[str]):
    """Return a client scoped to *segment* suitable for ``retrieve_documents``.

    ``retrieve_documents`` resolves the collection/table by name from the client
    it is given, so the client must already point at the right keyspace
    (astra/hcd) or database (mongodb). Cloudant addresses databases by name on a
    single client, so the client is returned unchanged.
    """
    if _is_astra_compatible(backend):
        if segment and getattr(db_client, "keyspace", None) != segment:
            # use_keyspace mutates in place; spawn a keyspace-scoped view instead
            # so we never disturb the caller's client.
            try:
                return db_client._copy(keyspace=segment)
            except Exception:
                db_client.use_keyspace(segment)
        return db_client

    if backend == "mongodb":
        if segment and db_client.name != segment:
            return db_client.client[segment]
        return db_client

    return db_client


def _fetch_documents(
    db_client,
    backend: str,
    segment: Optional[str],
    collection: Optional[str],
    limit: int,
    selectors: Optional[Dict[str, Any]] = None,
    fields: Optional[Union[List[str], Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Fetch up to *limit* documents from the selected collection.

    ``selectors`` and ``fields`` mirror :func:`retrieve_documents`. When
    *selectors* is None the default "match everything" filter is used (Cloudant
    needs ``{"_id": {"$gt": None}}``; the others take ``{}``). When *fields* is
    given it is forwarded as a projection; the ``_id`` field is always added so
    documents stay addressable for selection.
    """
    if not collection:
        return []

    scoped = _collection_client(db_client, backend, segment)

    if selectors is None:
        selectors = {"_id": {"$gt": None}} if backend == "cloudant" else {}

    fields = _ensure_id_field(fields)

    docs = retrieve_documents(
        db_client=scoped,
        db_name=collection,
        selectors=selectors,
        fields=fields,
        limit=limit,
        docs_only=True,
        provider=backend,
    )
    return docs or []


def _ensure_id_field(
    fields: Optional[Union[List[str], Dict[str, Any]]],
) -> Optional[Union[List[str], Dict[str, Any]]]:
    """Add ``_id`` to a projection so selected documents stay addressable.

    Returns *fields* unchanged when it is None (no projection). For a list
    projection ``_id`` is appended when absent; for a dict projection it is set
    truthy when absent. The display name still needs ``_id`` (and ideally the
    chosen ``name_key``) present, so callers should include the name field in
    *fields* themselves if they project it away.
    """
    if fields is None:
        return None
    if isinstance(fields, list):
        return fields if "_id" in fields else [*fields, "_id"]
    if isinstance(fields, dict):
        inner = fields.get("fields")
        if isinstance(inner, list):
            if "_id" not in inner:
                fields = {**fields, "fields": [*inner, "_id"]}
            return fields
        if "_id" not in fields:
            return {**fields, "_id": 1}
        return fields
    return fields


# ---------------------------------------------------------------------------
# Document display names
# ---------------------------------------------------------------------------


def _resolve_name_key(
    name_key: Union[str, Dict[str, str]],
    collection: Optional[str],
    default: str = "doc_name",
) -> str:
    """Resolve ``name_key`` to the display field for *collection*.

    ``name_key`` may be a single field name applied to every collection, or a
    ``{collection: field}`` mapping so each collection can name its documents
    from a different key. For the mapping form, a ``""`` (empty-string) entry, if
    present, serves as the fallback for collections not listed; otherwise the
    module default (``"doc_name"``) is used.
    """
    if isinstance(name_key, dict):
        if collection is not None and collection in name_key:
            return name_key[collection]
        return name_key.get("", default)
    return name_key


def _lookup_name_value(doc: Dict[str, Any], name_key: str) -> Any:
    """Read *name_key* from *doc*, supporting dot-notated nested access.

    A dotted key like ``"org_context.client_name"`` walks into nested dicts
    (via :func:`_get_nested_value`). If the dotted walk finds nothing, the key
    is also tried as a single flat key, so a literal field name that happens to
    contain a dot still resolves.
    """
    if "." in name_key:
        value = _get_nested_value(doc, name_key)
        if value is not None:
            return value
    return doc.get(name_key)


def _build_display_names(
    docs: List[Dict[str, Any]],
    name_key: str,
    name_mode: str,
) -> List[str]:
    """Build a file-like display name for each document.

    The name is derived from the document's ``_id`` and an optional display key
    (``name_key``, e.g. ``"doc_name"``):

        * ``name_mode="append"``  -> ``"**<name_key value>** (<_id>)"`` (just the
          ``_id`` when the key is absent/blank). The ``**...**`` markers ask the
          frontend to render the value in bold (see ``_render_name`` in the ESM).
        * ``name_mode="replace"`` -> ``"<name_key value>"`` (falls back to the
          ``_id`` when the key is absent/blank). When the same value occurs more
          than once it is disambiguated with a ``(n)`` suffix in order of
          appearance, e.g. ``"report"``, ``"report (1)"``, ``"report (2)"``.

    Returned names line up positionally with *docs*.
    """
    raw_names: List[str] = []
    for doc in docs:
        doc_id = str(doc.get("_id", "")).strip()
        display_value = _lookup_name_value(doc, name_key)
        display_value = "" if display_value is None else str(display_value).strip()

        if name_mode == "replace":
            raw_names.append(display_value or doc_id or "(no id)")
        else:  # "append" (default)
            if display_value and doc_id:
                # ``**...**`` marks the display value for bold; the frontend
                # renders this minimal markdown safely (see _render_name in the
                # ESM). Document text itself is escaped before the markers are
                # interpreted, so embedded ``**`` in a value can't inject markup.
                raw_names.append(f"**{display_value}** ({doc_id})")
            else:
                raw_names.append(doc_id or display_value or "(no id)")

    # Disambiguate collisions (only meaningful for "replace", but harmless
    # elsewhere): the first occurrence keeps the bare name, later ones get
    # " (1)", " (2)", ... in order of appearance.
    counts: Dict[str, int] = {}
    result: List[str] = []
    for name in raw_names:
        seen = counts.get(name, 0)
        result.append(name if seen == 0 else f"{name} ({seen})")
        counts[name] = seen + 1
    return result


# ---------------------------------------------------------------------------
# anywidget: segment / collection selectors + document list panel
# ---------------------------------------------------------------------------


_ESM = """
function render({ model, el }) {
  el.classList.add("nosql-docviewer-widget");

  function fmtCount(n) {
    return n === 1 ? "1 document" : `${n} documents`;
  }

  // Render a display name with minimal, *safe* markdown: only `**bold**` is
  // honoured. The raw text is HTML-escaped first so untrusted document content
  // (ids / name values) can never inject markup; only the escaped `**` markers
  // are then turned into <b> tags. Returns an HTML string for innerHTML.
  function renderName(name) {
    let escaped = String(name)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
    return escaped.replace(/\\*\\*(.+?)\\*\\*/g, "<b>$1</b>");
  }

  function buildSelect(className, label, options, value, onChange) {
    let wrap = document.createElement("label");
    wrap.className = "ndv-select-wrap";

    let cap = document.createElement("span");
    cap.className = "ndv-select-label";
    cap.textContent = label;
    wrap.appendChild(cap);

    let select = document.createElement("select");
    select.className = className;
    options.forEach(opt => {
      let o = document.createElement("option");
      o.value = opt;
      o.textContent = opt;
      if (opt === value) o.selected = true;
      select.appendChild(o);
    });
    if (options.length === 0) {
      let o = document.createElement("option");
      o.textContent = "(none)";
      o.disabled = true;
      select.appendChild(o);
      select.disabled = true;
    }
    select.addEventListener("change", () => onChange(select.value));
    wrap.appendChild(select);
    return wrap;
  }

  function renderView() {
    el.replaceChildren();

    let label = model.get("label");
    if (label) {
      let heading = document.createElement("div");
      heading.className = "ndv-label";
      heading.textContent = label;
      el.appendChild(heading);
    }

    // --- Navigation selectors (segment + optional collection tier). ---
    let nav = document.createElement("div");
    nav.className = "ndv-nav";

    nav.appendChild(
      buildSelect(
        "ndv-segment",
        model.get("segment_label"),
        model.get("segments"),
        model.get("segment"),
        v => { model.set("segment", v); model.save_changes(); }
      )
    );

    if (model.get("has_collection_tier")) {
      nav.appendChild(
        buildSelect(
          "ndv-collection",
          model.get("collection_label"),
          model.get("collections"),
          model.get("collection"),
          v => { model.set("collection", v); model.save_changes(); }
        )
      );
    }
    el.appendChild(nav);

    // --- Document list. ---
    let container = document.createElement("div");
    container.className = "ndv-list";

    let items = model.get("items");
    let multiselect = model.get("multiselect");
    let selected = model.get("selected_index");
    let selectedSet = new Set(model.get("selected_indices") || []);
    let error = model.get("error");

    let isSelected = index =>
      multiselect ? selectedSet.has(index) : index === selected;

    // In multiselect mode a plain click toggles membership; in single mode it
    // sets the lone selection. Python mirrors `selected_index` into
    // `selected_indices` so `.value` is uniform across both modes.
    let toggle = index => {
      if (multiselect) {
        if (selectedSet.has(index)) selectedSet.delete(index);
        else selectedSet.add(index);
        model.set("selected_indices", Array.from(selectedSet).sort((a, b) => a - b));
      } else {
        model.set("selected_index", index);
      }
      model.save_changes();
    };

    if (error) {
      let errBox = document.createElement("div");
      errBox.className = "ndv-empty ndv-error";
      errBox.textContent = error;
      container.appendChild(errBox);
    } else if (!items || items.length === 0) {
      let empty = document.createElement("div");
      empty.className = "ndv-empty";
      empty.textContent = "No documents in this collection";
      container.appendChild(empty);
    } else {
      items.forEach((item, index) => {
        let on = isSelected(index);
        let row = document.createElement("div");
        row.className = "ndv-row" + (on ? " selected" : "");
        row.dataset.index = index;
        row.tabIndex = 0;
        row.setAttribute("role", "option");
        row.setAttribute("aria-selected", on ? "true" : "false");

        if (multiselect) {
          let box = document.createElement("span");
          box.className = "ndv-check" + (on ? " checked" : "");
          if (on) {
            box.innerHTML = `
              <svg width="10" height="10" viewBox="0 0 14 14" fill="none">
                <path d="M3 7.5l3 3 5-6" stroke="currentColor" stroke-width="2"
                      stroke-linecap="round" stroke-linejoin="round"/>
              </svg>`;
          }
          row.appendChild(box);
        }

        let icon = document.createElement("span");
        icon.className = "ndv-icon";
        icon.innerHTML = `
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
            <path d="M4 1.5h5L13 5.5v9a.5.5 0 0 1-.5.5h-9a.5.5 0 0 1-.5-.5v-12a.5.5 0 0 1 .5-.5z"
                  stroke="currentColor" stroke-width="1" fill="none"/>
            <path d="M9 1.5V5.5h4" stroke="currentColor" stroke-width="1" fill="none"/>
          </svg>`;

        let name = document.createElement("span");
        name.className = "ndv-name";
        name.innerHTML = renderName(item.name);
        // Tooltip stays plain text: drop the bold markers, keep the words.
        name.title = String(item.name).replace(/\\*\\*(.+?)\\*\\*/g, "$1");

        row.appendChild(icon);
        row.appendChild(name);

        row.addEventListener("click", () => toggle(index));
        row.addEventListener("keydown", e => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            toggle(index);
          }
        });

        container.appendChild(row);
      });
    }
    el.appendChild(container);

    let footer = document.createElement("div");
    footer.className = "ndv-footer";
    if (error) {
      footer.textContent = "";
    } else {
      let total = items ? items.length : 0;
      let chosen = multiselect ? selectedSet.size : (selected >= 0 ? 1 : 0);
      footer.textContent =
        fmtCount(total) + (chosen ? `  -  ${chosen} selected` : "");
    }
    el.appendChild(footer);
  }

  renderView();
  // A full re-render keeps the selectors and list consistent whenever Python
  // repopulates any tier (e.g. new collections after a segment switch).
  model.on("change:items", renderView);
  model.on("change:multiselect", renderView);
  model.on("change:selected_index", renderView);
  model.on("change:selected_indices", renderView);
  model.on("change:label", renderView);
  model.on("change:segments", renderView);
  model.on("change:segment", renderView);
  model.on("change:collections", renderView);
  model.on("change:collection", renderView);
  model.on("change:error", renderView);
}

export default { render };
"""

_CSS = """
.nosql-docviewer-widget {
  font-family: system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
  max-width: 100%;
  color-scheme: light dark;

  --ndv-bg-container: #ffffff;
  --ndv-bg-item: #ffffff;
  --ndv-bg-hover: #f8f9fa;
  --ndv-bg-selected: #e7f0fd;
  --ndv-bg-footer: #f4f5f7;
  --ndv-bg-input: #ffffff;
  --ndv-border-color: #e1e5e9;
  --ndv-text-primary: #172b4d;
  --ndv-text-secondary: #6b778c;
  --ndv-accent: #0052cc;
  --ndv-error: #b3261e;
  --ndv-shadow: rgba(0, 0, 0, 0.1);
}
.nosql-docviewer-widget .ndv-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--ndv-text-primary);
  margin-bottom: 6px;
}
.nosql-docviewer-widget .ndv-nav {
  display: flex;
  gap: 10px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}
.nosql-docviewer-widget .ndv-select-wrap {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
  flex: 1;
}
.nosql-docviewer-widget .ndv-select-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--ndv-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}
.nosql-docviewer-widget select {
  font-family: inherit;
  font-size: 13px;
  color: var(--ndv-text-primary);
  background: var(--ndv-bg-input);
  border: 1px solid var(--ndv-border-color);
  border-radius: 4px;
  padding: 5px 8px;
  outline: none;
  cursor: pointer;
  min-width: 0;
}
.nosql-docviewer-widget select:focus {
  border-color: var(--ndv-accent);
}
.nosql-docviewer-widget select:disabled {
  cursor: default;
  opacity: 0.6;
}
.nosql-docviewer-widget .ndv-list {
  background: var(--ndv-bg-container);
  border: 1px solid var(--ndv-border-color);
  border-radius: 6px 6px 0 0;
  overflow-y: auto;
  max-height: 320px;
  box-shadow: 0 1px 3px var(--ndv-shadow);
}
.nosql-docviewer-widget .ndv-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  background: var(--ndv-bg-item);
  border-bottom: 1px solid var(--ndv-border-color);
  cursor: pointer;
  transition: background-color 0.12s ease;
  outline: none;
}
.nosql-docviewer-widget .ndv-row:last-child {
  border-bottom: none;
}
.nosql-docviewer-widget .ndv-row:hover {
  background-color: var(--ndv-bg-hover);
}
.nosql-docviewer-widget .ndv-row.selected {
  background-color: var(--ndv-bg-selected);
}
.nosql-docviewer-widget .ndv-row:focus-visible {
  box-shadow: inset 0 0 0 2px var(--ndv-accent);
}
.nosql-docviewer-widget .ndv-check {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 14px;
  flex-shrink: 0;
  border: 1px solid var(--ndv-border-color);
  border-radius: 3px;
  background: var(--ndv-bg-input);
  color: #ffffff;
}
.nosql-docviewer-widget .ndv-check.checked {
  background: var(--ndv-accent);
  border-color: var(--ndv-accent);
}
.nosql-docviewer-widget .ndv-icon {
  display: flex;
  align-items: center;
  color: var(--ndv-text-secondary);
  flex-shrink: 0;
}
.nosql-docviewer-widget .ndv-name {
  font-size: 13px;
  color: var(--ndv-text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.nosql-docviewer-widget .ndv-empty {
  padding: 16px 10px;
  font-size: 13px;
  color: var(--ndv-text-secondary);
  text-align: center;
}
.nosql-docviewer-widget .ndv-empty.ndv-error {
  color: var(--ndv-error);
}
.nosql-docviewer-widget .ndv-footer {
  font-size: 11px;
  color: var(--ndv-text-secondary);
  padding: 4px 10px;
  background: var(--ndv-bg-footer);
  border: 1px solid var(--ndv-border-color);
  border-top: none;
  border-radius: 0 0 6px 6px;
  min-height: 14px;
}

/* Dark mode: marimo toggles `.dark` (and some hosts `.dark-theme`). */
.dark .nosql-docviewer-widget,
.dark-theme .nosql-docviewer-widget {
  --ndv-bg-container: #1e1e1e;
  --ndv-bg-item: #2a2a2a;
  --ndv-bg-hover: #333333;
  --ndv-bg-selected: #14375e;
  --ndv-bg-footer: #262626;
  --ndv-bg-input: #2a2a2a;
  --ndv-border-color: #3a3a3a;
  --ndv-text-primary: #e0e0e0;
  --ndv-text-secondary: #a0a0a0;
  --ndv-accent: #4d9fff;
  --ndv-error: #f2b8b5;
  --ndv-shadow: rgba(0, 0, 0, 0.3);
}
"""


class NoSQLDocViewer(anywidget.AnyWidget):
    """anywidget rendering the segment/collection selectors and document list.

    All navigation state lives in traits so a single Python observer can react
    to a selector change and repopulate the tiers below it. ``items`` is a list
    of ``{"name": str}`` dicts positionally aligned with the loaded documents.
    When ``multiselect`` is False the chosen document is ``selected_index`` (or
    ``-1``); when True the chosen documents are ``selected_indices``.
    """

    _esm = traitlets.Unicode(_ESM).tag(sync=True)
    _css = traitlets.Unicode(_CSS).tag(sync=True)

    label = traitlets.Unicode("").tag(sync=True)
    segment_label = traitlets.Unicode("Segment").tag(sync=True)
    collection_label = traitlets.Unicode("Collection").tag(sync=True)
    has_collection_tier = traitlets.Bool(default_value=True).tag(sync=True)

    segments = traitlets.List(traitlets.Unicode()).tag(sync=True)
    segment = traitlets.Unicode("").tag(sync=True)
    collections = traitlets.List(traitlets.Unicode()).tag(sync=True)
    collection = traitlets.Unicode("").tag(sync=True)

    items = traitlets.List(traitlets.Dict()).tag(sync=True)
    multiselect = traitlets.Bool(default_value=False).tag(sync=True)
    selected_index = traitlets.Int(default_value=-1).tag(sync=True)
    selected_indices = traitlets.List(traitlets.Int()).tag(sync=True)
    error = traitlets.Unicode("").tag(sync=True)


# ---------------------------------------------------------------------------
# Public element
# ---------------------------------------------------------------------------


class _NoSQLDocViewerElement(mo.ui.anywidget):
    """``mo.ui.anywidget`` wrapper whose ``.value`` is the selected document.

    The wrapper owns the backend client and the in-memory list of loaded
    documents. It observes the widget's ``segment``/``collection`` traits so a
    selector change refetches the relevant tier server-side, and narrows
    ``.value`` to the selected document(s) (rather than the widget's full trait
    state). ``.value`` is always a list -- empty, one, or many -- regardless of
    whether single- or multi-select is in effect.
    """

    def __init__(
        self,
        widget: NoSQLDocViewer,
        *,
        db_client,
        backend: str,
        has_collection_tier: bool,
        name_key: Union[str, Dict[str, str]],
        name_mode: str,
        multiselect: bool,
        selectors: Optional[Dict[str, Any]],
        fields: Optional[Union[List[str], Dict[str, Any]]],
        limit: int,
    ) -> None:
        # Set before super().__init__ flips _initialized to True so these stay on
        # the element (the forwarding __setattr__ would otherwise push them onto
        # the widget).
        self._db_client = db_client
        self._backend = backend
        self._has_collection_tier = has_collection_tier
        self._name_key = name_key
        self._name_mode = name_mode
        self._multiselect = multiselect
        self._selectors = selectors
        self._fields = fields
        self._limit = limit
        self._docs: List[Dict[str, Any]] = []
        self._raw_widget = widget

        super().__init__(widget)

        # React to selector changes coming from the frontend.
        widget.observe(self._on_segment_change, names="segment")
        widget.observe(self._on_collection_change, names="collection")

        # Load the initial collection's documents.
        self._load_documents(widget.segment or None, widget.collection or None)

    # -- internal: list refresh on selector changes -------------------------

    def _load_documents(
        self, segment: Optional[str], collection: Optional[str]
    ) -> None:
        widget = self._raw_widget
        # Switching collections invalidates positional selections; clear both.
        widget.selected_index = -1
        widget.selected_indices = []
        widget.error = ""

        try:
            self._docs = _fetch_documents(
                self._db_client,
                self._backend,
                segment,
                collection,
                self._limit,
                selectors=self._selectors,
                fields=self._fields,
            )
        except Exception as exc:
            self._docs = []
            widget.items = []
            widget.error = f"Failed to load documents: {exc}"
            return

        resolved_key = _resolve_name_key(self._name_key, collection)
        names = _build_display_names(self._docs, resolved_key, self._name_mode)
        widget.items = [{"name": n} for n in names]

    def _on_segment_change(self, change) -> None:
        segment = change["new"] or None
        widget = self._raw_widget

        if self._has_collection_tier:
            collections = _list_collections(self._db_client, self._backend, segment)
            collection = collections[0] if collections else None
            # Repopulate the collection tier for the newly chosen segment.
            widget.collections = collections
            # Setting ``collection`` fires _on_collection_change, which loads the
            # documents -- so only load here when it stays the same and won't fire.
            if widget.collection == (collection or ""):
                self._load_documents(segment, collection)
            else:
                widget.collection = collection or ""
        else:
            # Cloudant: the segment is the collection; load directly.
            self._load_documents(segment, segment)

    def _on_collection_change(self, change) -> None:
        segment = self._raw_widget.segment or None
        collection = change["new"] or None
        self._load_documents(segment, collection)

    # -- value --------------------------------------------------------------

    @property
    def value(self) -> List[Dict[str, Any]]:
        """The selected document(s), always as a list.

        Returns ``[]`` when nothing is selected, a single-element list in
        single-select mode, and one entry per chosen document (in display order)
        in multi-select mode.
        """
        widget = self._raw_widget
        n = len(self._docs)

        if self._multiselect:
            indices = sorted(i for i in widget.selected_indices if 0 <= i < n)
            return [self._docs[i] for i in indices]

        index = widget.selected_index
        if 0 <= index < n:
            return [self._docs[index]]
        return []

    @value.setter
    def value(self, value):
        del value
        raise RuntimeError("Setting the value of a UIElement is not allowed.")


def nosql_doc_browser(
    db_client,
    *,
    provider: Optional[str] = None,
    name_key: Union[str, Dict[str, str]] = "doc_name",
    name_mode: str = "append",
    multiselect: bool = False,
    selectors: Optional[Dict[str, Any]] = None,
    fields: Optional[Union[List[str], Dict[str, Any]]] = None,
    label: str = "Browse JSON documents",
    limit: int = 200,
) -> mo.ui.anywidget:
    """Browse and select JSON documents across the project's NoSQL backends.

    The document-store counterpart to ``mo.ui.file_browser()``. Given any client
    built by ``nosql_database_helper_functions`` (Cloudant, AstraDB, HCD or
    MongoDB) it presents:

        * a *segment* dropdown - keyspace (astra/hcd) or database
          (cloudant/mongodb);
        * a *collection* dropdown - collection/table (hidden for Cloudant, whose
          database is itself the collection);
        * a scrollable list of the documents in the selected collection, each
          named from its ``_id`` and an optional display key.

    Switching the segment rebuilds the collection list; switching either reloads
    the document list and clears the selection. Selected documents are exposed
    on ``.value`` -- always as a list (empty when nothing is selected, one entry
    in single-select mode, one entry per chosen document in multi-select mode).

    Args:
        db_client: An initialized client (CloudantV1, astrapy ``Database`` for
            AstraDB/HCD, or pymongo ``Database`` for MongoDB).
        provider: Optional explicit backend ("cloudant", "astradb", "hcd" or
            "mongodb"). Detected from the client type when omitted.
        name_key: Document key whose value augments/replaces the ``_id`` in the
            display name. Either a single field applied to every collection
            (default ``"doc_name"``) or a ``{collection: field}`` mapping so each
            collection names its documents from a different key. For the mapping
            form, a ``""`` entry, if present, is the fallback for unlisted
            collections; otherwise unlisted collections fall back to
            ``"doc_name"``. Dot notation reaches nested values, e.g.
            ``"org_context.client_name"``.
        name_mode: ``"append"`` (default) shows ``"<_id> - <name_key>"``;
            ``"replace"`` shows just the ``name_key`` value (falling back to
            ``_id``), disambiguating duplicates with a ``(n)`` suffix.
        multiselect: When True, each row toggles a checkbox so several documents
            can be selected at once. When False (default), one row is selected at
            a time. ``.value`` is a list either way.
        selectors: Optional query filter, mirroring :func:`retrieve_documents`.
            When omitted (default), every document is listed (Cloudant uses
            ``{"_id": {"$gt": None}}``; the others use ``{}``). When given, only
            documents matching the filter are listed and exposed on ``.value``.
        fields: Optional projection, mirroring :func:`retrieve_documents` -- a
            list of field names or a dict field spec. When given, the loaded
            documents (and therefore ``.value``) carry only those fields. ``_id``
            is always included so documents stay addressable; include the
            ``name_key`` field too if you project it away, or the display names
            fall back to the ``_id``.
        label: Optional heading shown above the browser.
        limit: Maximum number of documents to load per collection (default 200).

    Returns:
        A marimo UI element whose ``.value`` is a list of the selected document
        dicts (empty when nothing is selected).
    """
    if name_mode not in ("append", "replace"):
        raise ValueError("name_mode must be 'append' or 'replace'")

    backend = _detect_backend(db_client, provider)

    # Per-backend tier labels / whether a collection sub-tier exists.
    if _is_astra_compatible(backend):
        segment_label, collection_label, has_collection_tier = (
            "Keyspace",
            "Collection",
            True,
        )
    elif backend == "mongodb":
        segment_label, collection_label, has_collection_tier = (
            "Database",
            "Collection",
            True,
        )
    else:  # cloudant
        segment_label, collection_label, has_collection_tier = (
            "Database",
            "Database",
            False,
        )

    segments = _list_segments(db_client, backend)
    default_segment = _default_segment(db_client, backend, segments)
    collections = _list_collections(db_client, backend, default_segment)
    default_collection = (
        (collections[0] if collections else None)
        if has_collection_tier
        else default_segment
    )

    widget = NoSQLDocViewer(
        label=label,
        segment_label=segment_label,
        collection_label=collection_label,
        has_collection_tier=has_collection_tier,
        segments=segments,
        segment=default_segment or "",
        collections=collections,
        collection=default_collection or "",
        multiselect=multiselect,
    )

    return _NoSQLDocViewerElement(
        widget,
        db_client=db_client,
        backend=backend,
        has_collection_tier=has_collection_tier,
        name_key=name_key,
        name_mode=name_mode,
        multiselect=multiselect,
        selectors=selectors,
        fields=fields,
        limit=limit,
    )
