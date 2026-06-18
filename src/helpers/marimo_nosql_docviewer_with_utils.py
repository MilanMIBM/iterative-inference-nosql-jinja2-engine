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

import copy
import json
import re
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import marimo as mo
import anywidget
import traitlets

from .nosql_database_helper_functions import (
    _detect_backend,
    _get_nested_value,
    _is_astra_compatible,
    _resolve_collection_name,
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
# Document utilities: duplicate / download / delete selected documents
# ---------------------------------------------------------------------------
#
# These power the action buttons at the bottom of the widget. They operate on a
# list of already-loaded document dicts (the widget's current selection) and go
# through the same backend client the listing path uses, so a backend addressed
# by ``segment``/``collection`` is reached the same way ``_fetch_documents``
# reaches it (via ``_collection_client``).


def _n_docs(count: int) -> str:
    """Pluralize a document count for status messages."""
    return "1 document" if count == 1 else f"{count} documents"


def _new_id() -> str:
    """Generate a fresh document id matching ``upload_single_document``'s scheme."""
    date_suffix = datetime.now().strftime("%d%m%Y")
    return f"{str(uuid.uuid4())}_{date_suffix}"


def _duplicate_documents(
    db_client,
    backend: str,
    segment: Optional[str],
    collection: Optional[str],
    docs: List[Dict[str, Any]],
) -> int:
    """Insert a copy of each document in *docs* with a fresh ``_id``.

    Each duplicate is a deep copy of the original with the identity fields
    (``_id`` and, for Cloudant, ``_rev``) replaced by a new UUID-based ``_id`` so
    the insert never collides with the source document. Returns the number of
    duplicates written.
    """
    if not collection or not docs:
        return 0

    scoped = _collection_client(db_client, backend, segment)

    duplicates: List[Dict[str, Any]] = []
    for doc in docs:
        clone = copy.deepcopy(doc)
        clone.pop("_id", None)
        clone.pop("_rev", None)  # Cloudant revision token; meaningless on a copy.
        clone["_id"] = _new_id()
        duplicates.append(clone)

    if _is_astra_compatible(backend):
        collection_name = _resolve_collection_name(scoped, collection)
        scoped.get_collection(collection_name).insert_many(duplicates)
    elif backend == "mongodb":
        scoped[collection].insert_many(duplicates)
    else:  # cloudant
        scoped.post_bulk_docs(
            db=collection, bulk_docs={"docs": duplicates}
        ).get_result()

    return len(duplicates)


def _delete_documents(
    db_client,
    backend: str,
    segment: Optional[str],
    collection: Optional[str],
    docs: List[Dict[str, Any]],
) -> int:
    """Delete each document in *docs* from the collection. Returns count deleted.

    Documents are addressed by ``_id``. Cloudant additionally needs each
    document's ``_rev`` (revision token) to delete it; the loaded documents carry
    it when present, and any without a ``_rev`` are fetched on demand so a
    projection that dropped ``_rev`` still deletes correctly.
    """
    if not collection or not docs:
        return 0

    ids = [doc["_id"] for doc in docs if "_id" in doc]
    if not ids:
        return 0

    scoped = _collection_client(db_client, backend, segment)

    if _is_astra_compatible(backend):
        collection_name = _resolve_collection_name(scoped, collection)
        result = scoped.get_collection(collection_name).delete_many(
            {"_id": {"$in": ids}}
        )
        return getattr(result, "deleted_count", 0) or 0

    if backend == "mongodb":
        result = scoped[collection].delete_many({"_id": {"$in": ids}})
        return result.deleted_count

    # --- Cloudant: delete via a bulk op of {_id, _rev, _deleted}. ---
    revs = {doc["_id"]: doc["_rev"] for doc in docs if "_id" in doc and "_rev" in doc}
    missing = [doc_id for doc_id in ids if doc_id not in revs]
    if missing:
        fetched = retrieve_documents(
            db_client=scoped,
            db_name=collection,
            selectors={"_id": {"$in": missing}},
            fields=["_id", "_rev"],
            limit=len(missing),
            docs_only=True,
            provider=backend,
        )
        for doc in fetched or []:
            if "_id" in doc and "_rev" in doc:
                revs[doc["_id"]] = doc["_rev"]

    delete_docs = [
        {"_id": doc_id, "_rev": revs[doc_id], "_deleted": True}
        for doc_id in ids
        if doc_id in revs
    ]
    if not delete_docs:
        return 0
    scoped.post_bulk_docs(db=collection, bulk_docs={"docs": delete_docs}).get_result()
    return len(delete_docs)


def _sanitize_filename(name: str) -> str:
    """Make *name* safe to use as a file/zip name across platforms."""
    cleaned = re.sub(r"[^\w.\-]+", "_", str(name)).strip("_.")
    return cleaned or "document"


def _downloads_dir() -> Path:
    """Return the user's Downloads folder, falling back to the home directory."""
    downloads = Path.home() / "Downloads"
    if downloads.is_dir():
        return downloads
    try:
        downloads.mkdir(parents=True, exist_ok=True)
        return downloads
    except OSError:
        return Path.home()


def _download_documents_zip(
    backend: str,
    segment: Optional[str],
    collection: Optional[str],
    docs: List[Dict[str, Any]],
) -> Path:
    """Write *docs* as individual JSON files inside a zip in the Downloads folder.

    The archive is named ``<provider>_<segment-or-collection>.zip`` -- for
    Cloudant/MongoDB the segment is the database, for AstraDB/HCD it is the
    keyspace; the collection is appended when it differs from the segment so the
    name stays unambiguous. Each document becomes ``<_id>.json`` inside the zip,
    with a numeric suffix appended on name collisions. Returns the archive path.
    """
    scope = collection or segment or "documents"
    if segment and collection and collection != segment:
        scope = f"{segment}_{collection}"
    base_name = _sanitize_filename(f"{backend}_{scope}")

    target_dir = _downloads_dir()
    zip_path = target_dir / f"{base_name}.zip"
    # Never clobber an existing archive: add " (1)", " (2)", ... like a browser.
    counter = 1
    while zip_path.exists():
        zip_path = target_dir / f"{base_name} ({counter}).zip"
        counter += 1

    used_names: Dict[str, int] = {}
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for index, doc in enumerate(docs):
            stem = _sanitize_filename(str(doc.get("_id", f"document_{index}")))
            seen = used_names.get(stem, 0)
            used_names[stem] = seen + 1
            arcname = f"{stem}.json" if seen == 0 else f"{stem}_{seen}.json"
            payload = json.dumps(doc, indent=2, ensure_ascii=False, default=str)
            archive.writestr(arcname, payload)

    return zip_path


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

    let chosenCount = multiselect ? selectedSet.size : (selected >= 0 ? 1 : 0);

    let footer = document.createElement("div");
    footer.className = "ndv-footer";
    if (error) {
      footer.textContent = "";
    } else {
      let total = items ? items.length : 0;
      footer.textContent =
        fmtCount(total) + (chosenCount ? `  -  ${chosenCount} selected` : "");
    }
    el.appendChild(footer);

    // --- Action row (outside the document box), right-aligned. Order:
    // deselect_all (link, only when something is selected), select_all (link),
    // then the Duplicate / Download / Delete buttons. The buttons are disabled
    // with no selection; clicking dispatches an action to Python via the
    // `action` trait, bumping `action_token` so repeating the same action still
    // fires. The select/deselect links only apply in multiselect mode.
    let actions = document.createElement("div");
    actions.className = "ndv-actions";

    let busy = model.get("busy");
    let total = items ? items.length : 0;

    let dispatch = action => {
      if (chosenCount === 0 || busy) return;
      model.set("action_token", (model.get("action_token") || 0) + 1);
      model.set("action", action);
      model.save_changes();
    };

    let addLink = (text, onClick, extraClass) => {
      let link = document.createElement("span");
      link.className = "ndv-link" + (extraClass ? " " + extraClass : "");
      link.textContent = text;
      link.setAttribute("role", "button");
      link.tabIndex = 0;
      link.addEventListener("click", onClick);
      link.addEventListener("keydown", e => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick();
        }
      });
      actions.appendChild(link);
    };

    if (multiselect && total > 0) {
      if (chosenCount > 0) {
        addLink("deselect_all", () => {
          model.set("selected_indices", []);
          model.save_changes();
        });
      }
      addLink("select_all", () => {
        model.set(
          "selected_indices",
          Array.from({ length: total }, (_, i) => i)
        );
        model.save_changes();
      }, "ndv-link-select-all");
    }

    [
      ["duplicate", "Duplicate documents"],
      ["download", "Download documents"],
      ["delete", "Delete documents"],
    ].forEach(([action, caption]) => {
      let btn = document.createElement("button");
      btn.type = "button";
      btn.className = "ndv-btn ndv-btn-" + action;
      btn.textContent = caption;
      btn.disabled = chosenCount === 0 || busy;
      btn.addEventListener("click", () => dispatch(action));
      actions.appendChild(btn);
    });
    el.appendChild(actions);

    let status = model.get("status");
    if (status) {
      let statusBox = document.createElement("div");
      statusBox.className =
        "ndv-status" + (model.get("status_error") ? " ndv-status-error" : "");
      statusBox.textContent = status;
      el.appendChild(statusBox);
    }
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
  model.on("change:busy", renderView);
  model.on("change:status", renderView);
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
  --ndv-success: #1f7a44;
  --ndv-shadow: rgba(0, 0, 0, 0.1);

  /* Subtle button hues (download = green, delete = red). */
  --ndv-bg-success: #eef7f0;
  --ndv-bg-success-hover: #dcefe2;
  --ndv-border-success: #b6dcc2;
  --ndv-bg-danger: #fcefee;
  --ndv-bg-danger-hover: #f7dcda;
  --ndv-border-danger: #efc4c1;
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
.nosql-docviewer-widget .ndv-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  margin-top: 10px;
}
.nosql-docviewer-widget .ndv-link {
  font-size: 12px;
  color: var(--ndv-text-secondary);
  text-decoration: underline;
  text-underline-offset: 2px;
  cursor: pointer;
}
.nosql-docviewer-widget .ndv-link:hover {
  color: var(--ndv-accent);
}
.nosql-docviewer-widget .ndv-link:focus-visible {
  outline: none;
  box-shadow: 0 0 0 2px var(--ndv-accent);
  border-radius: 2px;
}
/* select_all gets a subtle blue hue to read as the primary link. */
.nosql-docviewer-widget .ndv-link-select-all {
  color: var(--ndv-accent);
}
.nosql-docviewer-widget .ndv-link-select-all:hover {
  color: var(--ndv-accent);
  opacity: 0.8;
}
.nosql-docviewer-widget .ndv-btn {
  font-family: inherit;
  font-size: 13px;
  font-weight: 500;
  color: var(--ndv-text-primary);
  background: var(--ndv-bg-input);
  border: 1px solid var(--ndv-border-color);
  border-radius: 4px;
  padding: 6px 12px;
  cursor: pointer;
  transition: background-color 0.12s ease, border-color 0.12s ease,
    opacity 0.12s ease;
}
.nosql-docviewer-widget .ndv-btn:hover:not(:disabled) {
  background: var(--ndv-bg-hover);
  border-color: var(--ndv-accent);
}
.nosql-docviewer-widget .ndv-btn:focus-visible {
  outline: none;
  box-shadow: 0 0 0 2px var(--ndv-accent);
}
.nosql-docviewer-widget .ndv-btn:disabled {
  cursor: default;
  opacity: 0.5;
}
/* Download: subtle green hue. Delete: subtle red hue. Duplicate keeps the
   neutral default. Hues use dedicated vars so dark mode can re-tune them. */
.nosql-docviewer-widget .ndv-btn-download {
  color: var(--ndv-success);
  background: var(--ndv-bg-success);
  border-color: var(--ndv-border-success);
}
.nosql-docviewer-widget .ndv-btn-download:hover:not(:disabled) {
  background: var(--ndv-bg-success-hover);
  border-color: var(--ndv-success);
}
.nosql-docviewer-widget .ndv-btn-delete {
  color: var(--ndv-error);
  background: var(--ndv-bg-danger);
  border-color: var(--ndv-border-danger);
}
.nosql-docviewer-widget .ndv-btn-delete:hover:not(:disabled) {
  background: var(--ndv-bg-danger-hover);
  border-color: var(--ndv-error);
}
.nosql-docviewer-widget .ndv-status {
  font-size: 12px;
  color: var(--ndv-text-secondary);
  margin-top: 8px;
}
.nosql-docviewer-widget .ndv-status-error {
  color: var(--ndv-error);
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
  --ndv-success: #7fd1a0;
  --ndv-shadow: rgba(0, 0, 0, 0.3);

  /* Subtle button hues, re-tuned for the dark surface. */
  --ndv-bg-success: #1b3327;
  --ndv-bg-success-hover: #234433;
  --ndv-border-success: #2f5a41;
  --ndv-bg-danger: #3a2120;
  --ndv-bg-danger-hover: #4a2826;
  --ndv-border-danger: #5e3431;
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

    # Action buttons: the frontend sets ``action`` (and bumps ``action_token`` so
    # an identical repeat still triggers the observer); ``busy`` disables the
    # buttons mid-op and ``status``/``status_error`` report the outcome.
    action = traitlets.Unicode("").tag(sync=True)
    action_token = traitlets.Int(default_value=0).tag(sync=True)
    busy = traitlets.Bool(default_value=False).tag(sync=True)
    status = traitlets.Unicode("").tag(sync=True)
    status_error = traitlets.Bool(default_value=False).tag(sync=True)


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
        # React to action-button clicks. ``action_token`` is bumped on every
        # click (even a repeat of the same action), so observing it -- not
        # ``action`` -- ensures the handler runs each time.
        widget.observe(self._on_action, names="action_token")

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

    # -- action buttons: duplicate / download / delete ----------------------

    def _set_status(self, message: str, *, is_error: bool = False) -> None:
        widget = self._raw_widget
        widget.status = message
        widget.status_error = is_error

    def _on_action(self, change) -> None:
        """Dispatch a frontend button click to the matching backend op.

        Runs the op on the current selection (``.value``), then -- for the
        mutating ops -- reloads the document list so the panel reflects the
        change. ``busy`` gates the buttons for the duration; ``status`` carries
        the result (or the error message) back to the frontend.
        """
        del change
        widget = self._raw_widget
        action = widget.action
        selected = self.value  # snapshot before any reload clears the selection

        if not selected:
            self._set_status("Select at least one document first.", is_error=True)
            return

        segment = widget.segment or None
        collection = (segment if not self._has_collection_tier else widget.collection) or None

        widget.busy = True
        self._set_status("")
        try:
            if action == "duplicate":
                count = _duplicate_documents(
                    self._db_client, self._backend, segment, collection, selected
                )
                self._load_documents(segment, collection)
                self._set_status(f"Duplicated {_n_docs(count)}.")
            elif action == "download":
                zip_path = _download_documents_zip(
                    self._backend, segment, collection, selected
                )
                self._set_status(
                    f"Downloaded {_n_docs(len(selected))} to {zip_path}."
                )
            elif action == "delete":
                count = _delete_documents(
                    self._db_client, self._backend, segment, collection, selected
                )
                self._load_documents(segment, collection)
                self._set_status(f"Deleted {_n_docs(count)}.")
            else:
                self._set_status(f"Unknown action: {action}", is_error=True)
        except Exception as exc:
            self._set_status(f"{action.capitalize()} failed: {exc}", is_error=True)
        finally:
            widget.busy = False

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
