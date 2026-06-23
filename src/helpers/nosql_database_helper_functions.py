from __future__ import annotations

from ibmcloudant.cloudant_v1 import CloudantV1
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from pathlib import Path

import certifi
import marimo as mo
import pandas as pd
from astrapy import DataAPIClient
from astrapy.authentication import UsernamePasswordTokenProvider
from astrapy.constants import Environment as DataStaxEnvironment
from pymongo import MongoClient
from pymongo.database import Database as MongoDatabase
from jinja2 import Environment, UndefinedError
import json
import uuid
import copy
import yaml
import os
import re


# ---------------------------------------------------------------------------
# Backend detection
# ---------------------------------------------------------------------------


def _detect_backend(db_client, provider: Optional[str] = None) -> str:
    """Return 'cloudant', 'astradb', 'hcd' or 'mongodb' based on client type or explicit provider."""
    if provider:
        return provider.strip().lower()
    if isinstance(db_client, CloudantV1):
        return "cloudant"
    if isinstance(db_client, MongoDatabase):
        return "mongodb"
    return "astradb"


def _is_astra_compatible(backend: str) -> bool:
    """Return True for backends that share the astrapy code path (astradb, hcd)."""
    return backend in ("astradb", "hcd")


# ---------------------------------------------------------------------------
# Private helpers (used internally by AstraDB path)
# ---------------------------------------------------------------------------


def _get_nested_value(doc: Dict[str, Any], dotted_key: str) -> Any:
    current: Any = doc
    for key in dotted_key.split("."):
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def _set_nested_value(target: Dict[str, Any], dotted_key: str, value: Any) -> None:
    keys = dotted_key.split(".")
    current = target
    for key in keys[:-1]:
        existing = current.get(key)
        if not isinstance(existing, dict):
            current[key] = {}
        current = current[key]
    current[keys[-1]] = value


def _project_docs(
    docs: List[Dict[str, Any]], fields: List[str]
) -> List[Dict[str, Any]]:
    projected_docs: List[Dict[str, Any]] = []
    for doc in docs:
        projected: Dict[str, Any] = {}
        for field in fields:
            value = _get_nested_value(doc, field)
            if value is not None:
                _set_nested_value(projected, field, value)
        projected_docs.append(projected)
    return projected_docs


def _normalize_fields(
    fields: Optional[Union[List[str], Dict[str, Any]]],
) -> Optional[List[str]]:
    if fields is None:
        return None
    if isinstance(fields, list):
        return fields
    if isinstance(fields, dict):
        nested = fields.get("fields")
        if isinstance(nested, list):
            return nested
        return [key for key, include in fields.items() if include]
    raise ValueError("fields must be a list of strings or a dict")


def _normalize_sort(
    sort: Optional[Union[List[Dict[str, str]], Dict[str, Union[int, str]]]],
) -> Optional[Dict[str, int]]:
    if sort is None:
        return None

    if isinstance(sort, dict):
        normalized: Dict[str, int] = {}
        for field, direction in sort.items():
            if isinstance(direction, str):
                normalized[field] = -1 if direction.lower().startswith("desc") else 1
            else:
                normalized[field] = int(direction)
        return normalized

    if isinstance(sort, list):
        normalized = {}
        for item in sort:
            if not isinstance(item, dict) or len(item) != 1:
                continue
            field, direction = next(iter(item.items()))
            normalized[field] = -1 if str(direction).lower().startswith("desc") else 1
        return normalized or None

    raise ValueError("sort must be a dict or a list of dicts")


def _resolve_collection_name(
    astra_db,
    requested_name: str,
    default_collection: Optional[str] = None,
) -> str:
    if astra_db is None:
        return requested_name

    try:
        collections = set(astra_db.list_collection_names())
    except Exception:
        collections = set()

    if requested_name in collections:
        return requested_name
    if default_collection and default_collection in collections:
        return default_collection
    return requested_name


# ---------------------------------------------------------------------------
# Provider-agnostic database helpers
# ---------------------------------------------------------------------------


def ensure_database_exists(
    db_client,
    db_name: str,
    provider: Optional[str] = None,
    create: bool = True,
) -> bool:
    """
    Ensure the target database/collection exists.

    For Cloudant, checks if the database exists and creates it if not.
    For AstraDB, checks if the collection exists and creates it if not.
    For MongoDB, collections are created implicitly on first write.

    Args:
        db_client: Initialized database client (CloudantV1, AstraDB Database,
            or MongoDB Database).
        db_name: Database name (Cloudant) or collection name (AstraDB/MongoDB).
        provider: Optional explicit backend ("cloudant", "astradb", or "mongodb").
            When omitted the backend is detected from the client type.
        create: If True (default), create the database/collection when it does
            not exist. If False, only check existence and return False when missing.

    Returns:
        True if the database/collection exists or was created successfully.
        False if it does not exist and create is False.
    """
    backend = _detect_backend(db_client, provider)

    if backend == "cloudant":
        try:
            db_client.get_database_information(db=db_name)
            return True
        except Exception:
            if not create:
                return False
            try:
                db_client.put_database(db=db_name)
                return True
            except Exception as e:
                print(f"Failed to create database {db_name}: {str(e)}")
                raise

    if _is_astra_compatible(backend):
        try:
            existing = set(db_client.list_collection_names())
            if db_name not in existing:
                if not create:
                    return False
                db_client.create_collection(db_name)
            return True
        except Exception as e:
            print(f"Failed to ensure {backend} collection {db_name}: {str(e)}")
            raise

    if backend == "mongodb":
        try:
            existing = set(db_client.list_collection_names())
            if db_name not in existing:
                if not create:
                    return False
                db_client.create_collection(db_name)
            return True
        except Exception as e:
            print(f"Failed to ensure MongoDB collection {db_name}: {str(e)}")
            raise

    return True


def retrieve_documents(
    db_client,
    db_name: str,
    selectors: Dict[str, Any],
    fields: Optional[Union[List[str], Dict[str, Any]]] = None,
    sort: Optional[Union[List[Dict[str, str]], Dict[str, Union[int, str]]]] = None,
    limit: int = 100,
    docs_only: bool = False,
    provider: Optional[str] = None,
) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Retrieve documents from Cloudant or AstraDB.

    Args:
        db_client: Initialized database client (CloudantV1 or AstraDB Database).
        db_name: Database name (Cloudant) or collection name (AstraDB).
        selectors: Query selectors / filter to match documents.
        fields: Fields to return. List of field names or dict with field spec.
        sort: Sort configuration. Accepts both Cloudant-style list-of-dicts
            and AstraDB-style dict formats.
        limit: Maximum number of documents to return. Defaults to 100.
        docs_only: If True, returns only the documents list.
        provider: Optional explicit backend ("cloudant","astradb","mongodb").

    Returns:
        dict with 'docs' key (full response) or list of dicts (docs_only=True).
    """
    backend = _detect_backend(db_client, provider)

    # Check if the target database/collection/table exists before querying.
    if backend == "cloudant":
        try:
            db_client.get_database_information(db=db_name)
        except Exception:
            print(f"{db_name} does not exist")
            return []
    elif _is_astra_compatible(backend):
        if db_client is None:
            print(f"{db_name} does not exist")
            return []
        try:
            if db_name not in set(db_client.list_collection_names()):
                print(f"{db_name} does not exist")
                return []
        except Exception:
            print(f"{db_name} does not exist")
            return []
    elif backend == "mongodb":
        if db_client is None:
            print(f"{db_name} does not exist")
            return []
        try:
            if db_name not in set(db_client.list_collection_names()):
                print(f"{db_name} does not exist")
                return []
        except Exception:
            print(f"{db_name} does not exist")
            return []

    try:
        if _is_astra_compatible(backend):
            if db_client is None:
                return [] if docs_only else {"docs": []}

            collection_name = _resolve_collection_name(db_client, db_name)

            query_kwargs: Dict[str, Any] = {
                "filter": selectors,
                "limit": limit,
            }
            sort_clause = _normalize_sort(sort)
            if sort_clause is not None:
                query_kwargs["sort"] = sort_clause

            collection = db_client.get_collection(collection_name)
            docs = list(collection.find(**query_kwargs))

            normalized_fields = _normalize_fields(fields)
            if normalized_fields is not None:
                docs = _project_docs(docs, normalized_fields)

            if docs_only:
                return docs
            return {"docs": docs}

        if backend == "mongodb":
            if db_client is None:
                return [] if docs_only else {"docs": []}

            collection = db_client[db_name]

            normalized_fields = _normalize_fields(fields)
            projection = None
            if normalized_fields is not None:
                projection = {f: 1 for f in normalized_fields}

            mongo_sort = _normalize_sort(sort)
            sort_list = list(mongo_sort.items()) if mongo_sort is not None else None

            cursor = collection.find(selectors, projection)
            if sort_list is not None:
                cursor = cursor.sort(sort_list)
            cursor = cursor.limit(limit)

            docs = list(cursor)
            for doc in docs:
                if "_id" in doc and not isinstance(doc["_id"], str):
                    doc["_id"] = str(doc["_id"])

            if docs_only:
                return docs
            return {"docs": docs}

        # --- Cloudant path ---
        if fields is not None:
            fields_to_retrieve = (
                {"fields": fields} if isinstance(fields, list) else fields
            )
            if not isinstance(fields, (list, dict)):
                raise ValueError("fields must be a list of strings or a dict")
            fields_param = fields_to_retrieve["fields"]
        else:
            fields_param = None

        # Normalise sort into Cloudant's list-of-dicts format.
        cloudant_sort: Optional[List[Dict[str, str]]] = None
        if sort is not None:
            if isinstance(sort, dict):
                cloudant_sort = [{k: str(v)} for k, v in sort.items()]
            else:
                cloudant_sort = sort

        query_params: Dict[str, Any] = {
            "db": db_name,
            "selector": selectors,
            "limit": limit,
        }
        if fields_param is not None:
            query_params["fields"] = fields_param
        if cloudant_sort is not None:
            query_params["sort"] = cloudant_sort

        retrieved_docs = db_client.post_find(**query_params).get_result()

        if docs_only:
            return retrieved_docs.get("docs")
        return retrieved_docs

    except Exception as exc:
        raise RuntimeError(
            "retrieve_documents failed "
            f"(provider={backend}, db_name={db_name}, "
            f"selectors={selectors}, fields={fields}, limit={limit}, "
            f"docs_only={docs_only}, "
            f"cause_type={type(exc).__name__}, cause={exc})"
        ) from exc


def bulk_update_docs(
    db_client,
    db_name: str,
    docs: List[Dict[str, Any]],
    batch_size: int = 100,
    provider: Optional[str] = None,
) -> List[Any]:
    """
    Update existing documents in Cloudant or AstraDB using bulk operations.

    For Cloudant, documents must have both ``_id`` and ``_rev``.
    For AstraDB, documents must have ``_id``.

    Args:
        db_client: Initialized database client.
        db_name: Target database/collection name.
        docs: List of document dicts to update.
        batch_size: Number of documents per bulk operation. Defaults to 100.
        provider: Optional explicit backend ("cloudant","astradb","hcd","mongodb").

    Returns:
        List of bulk operation response dicts.
    """
    backend = _detect_backend(db_client, provider)

    if not docs:
        raise ValueError("No documents provided for update.")

    ensure_database_exists(db_client, db_name, provider=backend)

    try:
        if _is_astra_compatible(backend):
            for i, doc in enumerate(docs):
                if "_id" not in doc:
                    raise ValueError(
                        f"Document at index {i} is missing '_id'. "
                        f"This is required to update an existing {backend} document."
                    )
            if db_client is None:
                raise ValueError(
                    f"{backend} client is None. Cannot perform bulk update."
                )

            collection_name = _resolve_collection_name(db_client, db_name)
            collection = db_client.get_collection(collection_name)
            batches = [
                docs[i : i + batch_size] for i in range(0, len(docs), batch_size)
            ]

            responses: list = []
            for batch in mo.status.progress_bar(
                batches,
                title=f"Updating {backend} documents",
                subtitle=f"Updating {len(docs)} document(s) in '{collection_name}'",
                remove_on_exit=True,
            ):
                batch_responses = []
                try:
                    for doc in batch:
                        doc_id = doc["_id"]
                        update_data = {k: v for k, v in doc.items() if k != "_id"}
                        result = collection.update_one(
                            filter={"_id": doc_id},
                            update={"$set": update_data},
                        )
                        batch_responses.append(
                            {
                                "id": doc_id,
                                "ok": result.update_info.get("updatedExisting", False),
                                "matched_count": result.matched_count,
                                "modified_count": result.modified_count,
                            }
                        )
                    responses.append(batch_responses)
                except Exception as e:
                    print(f"Error updating batch in '{collection_name}': {e}")
                    raise

            return responses

        if backend == "mongodb":
            for i, doc in enumerate(docs):
                if "_id" not in doc:
                    raise ValueError(
                        f"Document at index {i} is missing '_id'. "
                        "This is required to update an existing MongoDB document."
                    )
            if db_client is None:
                raise ValueError("MongoDB client is None. Cannot perform bulk update.")

            collection = db_client[db_name]
            batches = [
                docs[i : i + batch_size] for i in range(0, len(docs), batch_size)
            ]

            responses: list = []
            for batch in mo.status.progress_bar(
                batches,
                title="Updating MongoDB documents",
                subtitle=f"Updating {len(docs)} document(s) in '{db_name}'",
                remove_on_exit=True,
            ):
                batch_responses = []
                try:
                    for doc in batch:
                        doc_id = doc["_id"]
                        update_data = {k: v for k, v in doc.items() if k != "_id"}
                        result = collection.update_one(
                            {"_id": doc_id},
                            {"$set": update_data},
                        )
                        batch_responses.append(
                            {
                                "id": doc_id,
                                "ok": result.matched_count > 0,
                                "matched_count": result.matched_count,
                                "modified_count": result.modified_count,
                            }
                        )
                    responses.append(batch_responses)
                except Exception as e:
                    print(f"Error updating batch in '{db_name}': {e}")
                    raise

            return responses

        # --- Cloudant path ---
        for i, doc in enumerate(docs):
            if "_id" not in doc or "_rev" not in doc:
                raise ValueError(
                    f"Document at index {i} is missing '_id' or '_rev'. "
                    "Both are required to update an existing Cloudant document."
                )

        batches = [docs[i : i + batch_size] for i in range(0, len(docs), batch_size)]

        responses = []
        for batch in mo.status.progress_bar(
            batches,
            title="Updating Cloudant documents",
            subtitle=f"Updating {len(docs)} document(s) in '{db_name}'",
            remove_on_exit=True,
        ):
            try:
                response = db_client.post_bulk_docs(
                    db=db_name,
                    bulk_docs={"docs": batch},
                ).get_result()

                batch_by_id = {doc["_id"]: doc for doc in batch}
                for result in response:
                    doc_id = result.get("id")
                    new_rev = result.get("rev")
                    if doc_id and new_rev and doc_id in batch_by_id:
                        batch_by_id[doc_id]["_rev"] = new_rev

                responses.append(response)
            except Exception as e:
                print(f"Error updating batch in '{db_name}': {e}")
                raise

        return responses

    except (ValueError, RuntimeError):
        raise
    except Exception as exc:
        raise RuntimeError(
            f"bulk_update_docs failed "
            f"(provider={backend}, db_name={db_name}, "
            f"num_docs={len(docs)}, batch_size={batch_size}, "
            f"cause_type={type(exc).__name__}, cause={exc})"
        ) from exc


def strip_surrogates(text: str) -> str:
    """Drop lone/unpaired UTF-16 surrogates from a string.

    Such surrogates (e.g. from broken emoji like flag pairs) are valid Python
    ``str`` but cannot be UTF-8 encoded, which crashes JSON serialization on
    upload. Properly-paired emoji survive.
    """
    return text.encode("utf-8", "surrogatepass").decode("utf-8", "ignore")


def clean_document(obj: Any) -> Any:
    """Recursively strip whitespace, drop empty values, and remove lone
    UTF-16 surrogates from dict keys and string values so the document is
    safe to JSON-serialize and upload.
    """
    if isinstance(obj, dict):
        cleaned = {}
        for k, v in obj.items():
            if k is None:
                continue
            key = strip_surrogates(str(k)).strip()
            if key == "":
                continue
            cleaned_value = clean_document(v)
            if cleaned_value in (None, "", [], {}):
                continue
            cleaned[key] = cleaned_value
        return cleaned
    elif isinstance(obj, list):
        cleaned_list = []
        for item in obj:
            cleaned_item = clean_document(item)
            if cleaned_item in (None, "", [], {}):
                continue
            cleaned_list.append(cleaned_item)
        return cleaned_list
    elif isinstance(obj, str):
        return strip_surrogates(obj).strip()
    else:
        return obj


def bulk_upload_docs(
    db_client,
    db_name: str,
    docs: Union[Dict, List[Dict]],
    batch_size: int = 100,
    provider: Optional[str] = None,
) -> List[List[Dict]]:
    """
    Upload documents to Cloudant or AstraDB using bulk operations.

    Args:
        db_client: Initialized database client.
        db_name: Target database/collection name.
        docs: Documents - dict with 'results' key or direct list.
        batch_size: Number of documents per bulk operation. Defaults to 100.
        provider: Optional explicit backend ("cloudant","astradb","hcd","mongodb").

    Returns:
        List of bulk operation responses.
    """
    backend = _detect_backend(db_client, provider)

    if isinstance(docs, dict):
        if "results" in docs:
            results_list = docs["results"]
        else:
            raise ValueError("Invalid results format - missing 'results' array")
    elif isinstance(docs, list):
        results_list = docs
    else:
        raise ValueError(
            "Invalid results format - must be dict with 'results' key or list"
        )

    if not results_list:
        raise ValueError("No results to upload")

    ensure_database_exists(db_client, db_name, provider=backend)

    batches = [
        results_list[i : i + batch_size]
        for i in range(0, len(results_list), batch_size)
    ]

    if _is_astra_compatible(backend):
        responses: list = []
        for batch in mo.status.progress_bar(
            batches,
            title=f"Uploading to {backend}",
            subtitle=f"Uploading {len(results_list)} documents",
            remove_on_exit=True,
        ):
            try:
                collection_name = _resolve_collection_name(db_client, db_name)
                collection = db_client.get_collection(collection_name)
                result = collection.insert_many(batch)
                responses.append(result.inserted_ids)
            except Exception as e:
                print(f"Error uploading batch: {str(e)}")
                raise
        return responses

    if backend == "mongodb":
        responses: list = []
        for batch in mo.status.progress_bar(
            batches,
            title="Uploading to MongoDB",
            subtitle=f"Uploading {len(results_list)} documents",
            remove_on_exit=True,
        ):
            try:
                collection = db_client[db_name]
                result = collection.insert_many(batch)
                responses.append([str(oid) for oid in result.inserted_ids])
            except Exception as e:
                print(f"Error uploading batch: {str(e)}")
                raise
        return responses

    # --- Cloudant path ---
    responses = []
    for batch in mo.status.progress_bar(
        batches,
        title="Uploading to Cloudant",
        subtitle=f"Uploading {len(results_list)} documents",
        remove_on_exit=True,
    ):
        try:
            response = db_client.post_bulk_docs(
                db=db_name, bulk_docs={"docs": batch}
            ).get_result()
            responses.append(response)
        except Exception as e:
            print(f"Error uploading batch: {str(e)}")
            raise

    return responses


def upload_single_document(
    db_client,
    db_name: str,
    doc: Dict,
    doc_id: Optional[str] = None,
    provider: Optional[str] = None,
) -> Dict:
    """
    Upload a single document to Cloudant or AstraDB.

    Args:
        db_client: Initialized database client (CloudantV1 or AstraDB Database).
        db_name: Target database/collection name.
        doc: Document to upload.
        doc_id: Custom document ID. If not provided, a UUID with date suffix
            will be generated.
        provider: Optional explicit backend ("cloudant","astradb","mongodb").

    Returns:
        Response dict containing document ID information.
    """
    backend = _detect_backend(db_client, provider)

    ensure_database_exists(db_client, db_name, provider=backend)

    if "_id" not in doc:
        if doc_id:
            doc["_id"] = doc_id
        else:
            date_suffix = datetime.now().strftime("%d%m%Y")
            doc["_id"] = f"{str(uuid.uuid4())}_{date_suffix}"

    if _is_astra_compatible(backend):
        collection_name = _resolve_collection_name(db_client, db_name)
        collection = db_client.get_collection(collection_name)
        result = collection.insert_one(doc)
        return {"id": result.inserted_id, "ok": True}

    if backend == "mongodb":
        collection = db_client[db_name]
        result = collection.insert_one(doc)
        return {"id": str(result.inserted_id), "ok": True}

    # --- Cloudant path ---
    response = db_client.post_document(db=db_name, document=doc).get_result()
    return response


def get_document_schema(
    db_client,
    db_name: str,
    selectors: Dict,
    limit: int = 1,
    provider: Optional[str] = None,
) -> Dict:
    """
    Retrieve a JSON schema of key names from documents matching the selector.

    Args:
        db_client: Initialized database client (CloudantV1 or AstraDB Database).
        db_name: Database/collection name to query.
        selectors: JSON object describing criteria used to select documents.
        limit: Maximum number of documents to sample for schema. Defaults to 1.
        provider: Optional explicit backend ("cloudant","astradb","mongodb").

    Returns:
        JSON schema dict with property names and inferred types.
    """
    docs = retrieve_documents(
        db_client=db_client,
        db_name=db_name,
        selectors=selectors,
        limit=limit,
        docs_only=True,
        provider=provider,
    )

    if not docs:
        return {"type": "object", "properties": {}}

    def infer_type(value) -> Dict:
        if value is None:
            return {"type": "null"}
        elif isinstance(value, bool):
            return {"type": "boolean"}
        elif isinstance(value, int):
            return {"type": "integer"}
        elif isinstance(value, float):
            return {"type": "number"}
        elif isinstance(value, str):
            return {"type": "string"}
        elif isinstance(value, list):
            if not value:
                return {"type": "array", "items": {}}
            item_types = [infer_type(item) for item in value]
            return {"type": "array", "items": item_types[0]}
        elif isinstance(value, dict):
            return {
                "type": "object",
                "properties": {k: infer_type(v) for k, v in value.items()},
            }
        else:
            return {"type": "string"}

    all_properties: Dict = {}
    for doc in docs:
        for key, value in doc.items():
            if key not in all_properties:
                all_properties[key] = infer_type(value)

    return {"type": "object", "properties": all_properties}


# ---------------------------------------------------------------------------
# Shared / provider-agnostic utilities
# ---------------------------------------------------------------------------


def _extract_delimited_blocks(raw_yaml: str, delimiter: str) -> List[str]:
    """Extract the text of YAML blocks fenced by a delimiter line.

    Handles both separator style (``<yaml>\\n---\\n<yaml>``) and fenced style
    (``---\\n<yaml>\\n---``). A delimiter line is a line consisting solely of the
    *delimiter* pattern (optionally surrounded by whitespace). The text between
    consecutive delimiter lines - and any leading text before the first
    delimiter / trailing text after the last - is returned as a candidate block.

    Args:
        raw_yaml: The full source string.
        delimiter: A regex matching the fence token on its own line (e.g.
            ``r"-{3,}"`` for three-or-more dashes).

    Returns:
        A list of stripped, non-empty block strings. Returns an empty list when
        no delimiter line is present.
    """
    # A delimiter line: start-of-line, optional ws, the token, optional ws, EOL.
    fence_re = re.compile(rf"(?m)^[ \t]*{delimiter}[ \t]*$")
    if not fence_re.search(raw_yaml):
        return []

    # Split on delimiter lines; the pieces between them are the candidate blocks.
    blocks = fence_re.split(raw_yaml)
    return [block.strip() for block in blocks if block.strip()]


def parse_yaml_documents(
    raw_yaml,
    safe_load: bool = True,
    extract_delimited: bool = True,
    delimiter: str = r"-{3,}",
    fallback_to_full: bool = True,
):
    """Parse one or more YAML documents out of a raw string.

    By default the string is treated as containing YAML blocks fenced by a
    delimiter line (3-or-more dashes), e.g.::

        ---
        type: slider
        ---

    or separated by them (``doc1\\n---\\ndoc2``). Each block is parsed
    independently and the dict results are collected.

    Args:
        raw_yaml: The source string to parse. Non-string input returns ``None``.
        safe_load: If ``True`` (default), parse each block with
            ``yaml.safe_load`` (with a key-quoting repair retry) and keep only
            dict results. If ``False``, return the raw block strings instead of
            parsed objects.
        extract_delimited: If ``True`` (default), extract blocks fenced/separated
            by *delimiter* before parsing. If ``False``, the whole string is
            treated as a single YAML document.
        delimiter: Regex matching the fence token on its own line. Defaults to
            ``r"-{3,}"`` (three or more dashes). Adjust to use a different fence,
            e.g. ``r"={3,}"`` or ``r"~~~"``.
        fallback_to_full: If ``True`` (default) and *extract_delimited* is on but
            no delimiter line is found, fall back to parsing the entire string as
            one document instead of returning nothing. Set ``False`` to require
            delimiters strictly (returns ``None`` when none are present).

    Returns:
        - A single dict when exactly one document parses.
        - A list of documents when several parse.
        - ``None`` when nothing parses.
        (When ``safe_load=False`` the same shape applies to raw block strings.)
    """
    if not isinstance(raw_yaml, str) or not raw_yaml.strip():
        return None

    if extract_delimited:
        cleaned = _extract_delimited_blocks(raw_yaml, delimiter)
        if not cleaned:
            # No fence present: optionally treat the whole string as one doc.
            cleaned = [raw_yaml.strip()] if fallback_to_full else []
    else:
        # Delimiter extraction disabled: hand the whole string to PyYAML, which
        # natively understands the standard "---" document separator via
        # safe_load_all. This keeps multi-doc streams working without our own
        # fence splitting.
        if safe_load:
            try:
                docs = [d for d in yaml.safe_load_all(raw_yaml) if isinstance(d, dict)]
                return docs[0] if len(docs) == 1 else docs if docs else None
            except yaml.YAMLError:
                # Fall through to the per-block repair path below.
                cleaned = [raw_yaml.strip()]
        else:
            cleaned = [raw_yaml.strip()]

    if not cleaned:
        return None

    if safe_load:
        parsed = []
        for doc in cleaned:
            try:
                parsed.append(yaml.safe_load(doc))
            except yaml.YAMLError:
                fixed = re.sub(
                    r"^\s{2,}(\w[\w\s]*?):\s*(.+)$",
                    r"  '\1': \2",
                    doc,
                    flags=re.MULTILINE,
                )
                try:
                    parsed.append(yaml.safe_load(fixed))
                except yaml.YAMLError:
                    pass
        parsed = [p for p in parsed if isinstance(p, dict)]
    else:
        parsed = cleaned

    return parsed[0] if len(parsed) == 1 else parsed if parsed else None


def render_jinja2_templates(
    docs: Union[Dict, List[Dict]],
    context_docs: Optional[Union[Dict, List[Dict]]] = None,
    render_top_level_first: bool = True,
) -> Union[Dict, List[Dict]]:
    """
    Render all Jinja2 templates in retrieved documents using the document's own keys/values.

    Creates an in-memory copy of the document(s) with all Jinja2 template strings
    rendered using the document itself as the context, optionally augmented with
    additional context documents.

    Args:
        docs: Result from retrieve_documents(). Can be:
            - A dict with 'docs' key (full response)
            - A list of document dicts (docs_only=True result)
            - A single document dict
        context_docs: Optional additional documents to use as template context.
            Variables from these documents are merged into the context before
            rendering. Can be:
            - A dict with 'docs' key (full response from retrieve_documents)
            - A list of document dicts
            - A single document dict
            Variables from context_docs are added first, then the document's own
            variables are added (allowing document values to override context_docs).
        render_top_level_first: If True (default), renders templates in order from
            top-level keys down to deeper nested ones. This allows nested templates
            to reference already-rendered values from higher levels. If False,
            renders all templates in a single pass.

    Returns:
        A copy of the input with all Jinja2 templates rendered:
            - If input was dict with 'docs' key, returns same structure with rendered docs
            - If input was list, returns list of rendered documents
            - If input was single dict, returns rendered document
    """
    env = Environment()
    env.globals["uuid4"] = lambda: str(uuid.uuid4())
    env.filters["slugify"] = _slugify
    env.filters["country_info"] = _country_info
    env.filters["dedupe_cased"] = _dedupe_cased
    env.filters["street_info"] = _street_info
    env.filters["clean_text"] = _clean_text

    def extract_docs_list(input_docs) -> List[Dict]:
        """Extract a list of documents from various input formats."""
        if input_docs is None:
            return []
        if isinstance(input_docs, dict):
            if "docs" in input_docs:
                return input_docs["docs"]
            else:
                return [input_docs]
        elif isinstance(input_docs, list):
            return input_docs
        return []

    context_docs_list = extract_docs_list(context_docs)

    def build_context(doc: Dict, extra_context_docs: List[Dict] = None) -> Dict:
        """Build a context dict from all document keys for template rendering.

        Flattens nested dicts recursively so that keys at any depth are accessible
        directly in templates. Later keys overwrite earlier ones if there are conflicts.

        Extra context docs are flattened first, then the main document is flattened,
        allowing the main document's values to override context doc values.
        """
        context = {}

        def flatten(obj: Dict, target: Dict) -> None:
            for key, value in obj.items():
                target[key] = value
                if isinstance(value, dict):
                    flatten(value, target)

        if extra_context_docs:
            for ctx_doc in extra_context_docs:
                flatten(ctx_doc, context)

        flatten(doc, context)
        return context

    def render_value(value, context: Dict):
        """Recursively render Jinja2 templates in a value.

        If a template contains undefined variables, it is left as-is
        (useful for instructional text that contains template syntax as examples).
        """
        if isinstance(value, str):
            if "{{" in value or "{%" in value:
                try:
                    template = env.from_string(value)
                    return template.render(context)
                except UndefinedError:
                    return value
            return value
        elif isinstance(value, dict):
            return {k: render_value(v, context) for k, v in value.items()}
        elif isinstance(value, list):
            return [render_value(item, context) for item in value]
        else:
            return value

    def render_document(doc: Dict) -> Dict:
        """Render all templates in a single document."""
        doc_copy = copy.deepcopy(doc)

        if render_top_level_first:

            def get_max_depth(obj, current_depth=0) -> int:
                """Get the maximum nesting depth of a dict."""
                if not isinstance(obj, dict):
                    return current_depth
                if not obj:
                    return current_depth
                return max(get_max_depth(v, current_depth + 1) for v in obj.values())

            def render_at_depth(
                obj, context: Dict, target_depth: int, current_depth: int = 0
            ):
                """Render only values at a specific depth."""
                if isinstance(obj, dict):
                    result = {}
                    for k, v in obj.items():
                        if current_depth == target_depth:
                            result[k] = render_value(v, context)
                        elif isinstance(v, dict):
                            result[k] = render_at_depth(
                                v, context, target_depth, current_depth + 1
                            )
                        elif isinstance(v, list) and current_depth < target_depth:
                            result[k] = [
                                (
                                    render_at_depth(
                                        item, context, target_depth, current_depth + 1
                                    )
                                    if isinstance(item, dict)
                                    else item
                                )
                                for item in v
                            ]
                        else:
                            result[k] = v
                    return result
                return obj

            max_depth = get_max_depth(doc_copy)
            max_iterations = max_depth + 2
            for _ in range(max_iterations):
                previous = copy.deepcopy(doc_copy)
                for depth in range(max_depth + 1):
                    doc_copy = render_at_depth(
                        doc_copy, build_context(doc_copy, context_docs_list), depth
                    )
                if doc_copy == previous:
                    break

            return doc_copy
        else:
            context = build_context(doc_copy, context_docs_list)
            return render_value(doc_copy, context)

    if isinstance(docs, dict):
        if "docs" in docs:
            rendered_docs = [render_document(doc) for doc in docs["docs"]]
            result = copy.deepcopy(docs)
            result["docs"] = rendered_docs
            return result
        else:
            return render_document(docs)
    elif isinstance(docs, list):
        return [render_document(doc) for doc in docs]
    else:
        raise ValueError("docs must be a dict or list")


def _decompose_cell(value) -> List[str]:
    """Flatten a single dataframe cell into a list of plain string values.

    Cells may arrive in several encodings, all of which collapse here to a flat
    list of strings:
        - JSON-string arrays:      '["KJELLER"]'            -> ["KJELLER"]
        - JSON-string objects:     '{"eng":["Forsvarets"]}' -> ["Forsvarets"]
        - already-parsed lists/dicts (same handling, no json.loads needed)
        - bare scalars:            'NOR'                    -> ["NOR"]

    Empty / NaN cells yield an empty list. Anything unparseable falls back to its
    string form so no data is silently dropped.
    """
    try:
        if pd.isna(value):
            return []
    except (TypeError, ValueError):
        pass  # arrays/dicts raise on isna; they are handled below

    # Parse JSON-encoded strings; leave already-structured values as-is.
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        try:
            value = json.loads(stripped)
        except (json.JSONDecodeError, ValueError):
            return [stripped]

    def walk(obj) -> List[str]:
        if obj is None:
            return []
        if isinstance(obj, str):
            return [obj] if obj.strip() else []
        if isinstance(obj, dict):
            out = []
            for v in obj.values():
                out.extend(walk(v))
            return out
        if isinstance(obj, (list, tuple, set)):
            out = []
            for v in obj:
                out.extend(walk(v))
            return out
        # numbers, bools, etc.
        return [str(obj)]

    return walk(value)


def _slug(name: str) -> str:
    """Normalise a column/variable name for matching.

    Lowercases and collapses non-alphanumeric runs to a single underscore so a
    column like ``organisation-city-buyer`` and the Jinja2 variable
    ``organisation_city_buyer`` resolve to the same key (``organisation_city_buyer``).

    ASCII-only by design: column and variable identifiers are ASCII, so any
    non-ASCII run is collapsed. For human-readable values (e.g. org names) use
    :func:`_slugify` instead, which preserves Unicode letters.
    """
    return re.sub(r"[^0-9a-z]+", "_", str(name).lower()).strip("_")


def _slugify(value: str) -> str:
    """UTF-8 aware slug for human-readable values (the ``slugify`` filter).

    Unlike :func:`_slug` (used for ASCII column/variable matching), this
    preserves Unicode letters and digits so accented alphabets are not eaten:
    ``Registerenheten i Brønnøysund`` becomes ``registerenheten_i_brønnøysund``
    rather than ``registerenheten_i_br_nn_ysund``. Runs of any other character
    collapse to a single underscore and leading/trailing underscores are
    stripped.
    """
    # \W matches any non-"word" character; with the default Unicode semantics
    # for str patterns, "word" characters include Unicode letters and digits.
    # casefold() lowercases more aggressively than lower() for Unicode (e.g. ß).
    return re.sub(r"[\W]+", "_", str(value).casefold(), flags=re.UNICODE).strip("_")


def _country_info(code: Any) -> Dict[str, Any]:
    """Resolve a country code/name to its identifiers, name, and flag.

    Registered as the ``country_info`` Jinja2 filter. ``code`` is whatever the
    source provides (e.g. an ISO 3166-1 alpha-3 code like ``NOR``); pycountry's
    case-insensitive ``lookup`` also accepts alpha-2, numeric, or the name. The
    returned dict carries ``country_id_shorthand`` (alpha-2) alongside
    ``country_id`` (the original input), ``country``, and ``flag``. If the
    country can't be resolved the original value is preserved and the resolved
    fields are left ``None`` so rendering never fails on bad input.
    """
    import pycountry

    info = {
        "country_id": code,
        "country_id_shorthand": None,
        "country": None,
        "flag": None,
    }
    if not code:
        return info
    try:
        match = pycountry.countries.lookup(str(code))
    except LookupError:
        return info
    info["country_id_shorthand"] = getattr(match, "alpha_2", None)
    info["country"] = getattr(match, "name", None)
    info["flag"] = getattr(match, "flag", None)
    return info


def _street_info(value: Any) -> Any:
    """Return the street value unchanged.

    Registered as the ``street_info`` Jinja2 filter. Currently a pass-through:
    the raw street string is kept as-is (no splitting of house number, no
    lookup). Exists as a named seam so the template can mark street fields and
    the parsing/enrichment can be added here later without touching templates.
    """
    return value


def _clean_text(value: Any) -> Any:
    """Strip leading/trailing whitespace from string values.

    Registered as the ``clean_text`` Jinja2 filter. A single string has its
    surrounding whitespace removed (e.g. ``" Brussels"`` -> ``"Brussels"``);
    a list/tuple is mapped element-wise (each string stripped, non-strings
    passed through). Any other type is returned unchanged. Use this on
    free-text fields (cities, streets, ...) *before* de-duplication so that
    entries differing only by stray surrounding spaces collapse together.
    """
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple)):
        return [_clean_text(item) for item in value]
    return value


def _dedupe_cased(values: Any) -> List[Any]:
    """Drop case-insensitive duplicate strings, preferring the better-cased form.

    Registered as the ``dedupe_cased`` Jinja2 filter. When two entries differ
    only by letter case (e.g. ``"Oslo"`` and ``"oslo"``), only one is kept: the
    variant that is *not* all-lowercase wins, so ``["Moss", "Oslo", "oslo"]``
    collapses to ``["Moss", "Oslo"]``. First-seen order is preserved. Non-string
    items pass through untouched and are de-duplicated by identity/equality.
    """
    if not isinstance(values, (list, tuple)):
        return values

    best: Dict[str, Any] = {}  # casefolded key -> chosen value
    order: List[str] = []  # casefolded keys, in first-seen order
    passthrough: List[Any] = []

    for item in values:
        if not isinstance(item, str):
            if item not in passthrough:
                passthrough.append(item)
            continue
        key = item.casefold()
        if key not in best:
            best[key] = item
            order.append(key)
        else:
            # Prefer a non-all-lowercase variant over an all-lowercase one.
            current = best[key]
            if current.islower() and not item.islower():
                best[key] = item

    return [best[k] for k in order] + passthrough


def render_template_from_dataframe(
    template: str,
    df: pd.DataFrame,
    *,
    is_path: bool = True,
    extra_context: Optional[Dict[str, Any]] = None,
    coupled_fields: Optional[Dict[str, Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """Render any Jinja2 (YAML) template against a whole dataframe.

    Template- and dataframe-agnostic: the *template* declares what to extract.
    Every Jinja2 variable it references that slug-matches a dataframe column is
    treated as an aggregated field. For each such variable, the matching column
    is decomposed across *every* row (via :func:`_decompose_cell`), flattened to
    strings, and de-duplicated (order-preserving). The resulting list is bound to
    that variable before rendering.

    Adding a new aggregated field therefore needs only a new ``{{ variable }}``
    in the template whose name slug-matches a dataframe column -- no Python
    change required. Feed in different templates and/or dataframes freely; no
    column names or keys are hardcoded here.

    Variables the template references that do *not* match a column (e.g. a fixed
    ``name``, ``language``, or the ``uuid4`` global) are left to ``extra_context``
    or to template defaults / globals.

    If the template references a variable named ``rows``, it is bound to a list
    with one dict per dataframe row (each cell decomposed to a flat list of
    strings, keyed by both the original column name and its slug). This gives a
    template true *per-record* access -- email, phone, and notice id from the
    *same* row stay together -- which the aggregated/de-duplicated column
    variables above cannot provide. A companion ``rows_raw`` (same shape, but
    each cell parsed with its structure preserved rather than flattened) lets a
    template navigate nested cells such as ``links`` (``format -> lang -> url``).
    Both are only computed when referenced, so existing templates are unaffected.

    Coupled fields keep multiple columns *row-aligned* instead of aggregating and
    de-duplicating each independently. Each entry maps a template variable to a
    ``{output_key: column}`` mapping; the variable is bound to a list with one
    dict per dataframe row (rows where every mapped cell is empty are skipped).
    For example::

        coupled_fields={"contact_details": {
            "email": "organisation-email-buyer",
            "phone": "organisation-tel-buyer",
            "notice-id": "notice-identifier",
        }}

    binds ``contact_details`` to ``[{"email": ..., "phone": ..., "notice-id": ...},
    ...]`` so each record's email, phone, and notice identifier stay together.
    Rows are skipped when every non-identifier value is empty (so a row carrying
    only a notice id, with no email or phone, produces no entry); keys named
    ``id``/``*-id``/``*_id`` are treated as identifiers for this check.

    Args:
        template: Either a path to a ``.j2`` file (default) or the template
            source text itself (set ``is_path=False``).
        df: Any dataframe whose rows feed the aggregated fields.
        is_path: If True, ``template`` is read from disk; otherwise used as-is.
        extra_context: Non-aggregated values (fixed scalars the template needs).
            These take precedence and are not overwritten by column aggregation.
        coupled_fields: Optional ``{variable: {output_key: column}}`` mapping for
            row-aligned fields (see above). Columns are matched by slug, like the
            aggregated fields. These take precedence over column aggregation for
            the same variable name.

    Returns:
        The rendered template parsed into a JSON object (a ``dict``). The
        template is rendered as YAML, then ``yaml.safe_load``-ed so callers get
        a ready-to-store document rather than a raw string.
    """
    from jinja2 import meta

    source = Path(template).read_text() if is_path else template

    env = Environment()
    env.globals["uuid4"] = lambda: str(uuid.uuid4())
    env.filters["slugify"] = _slugify
    env.filters["country_info"] = _country_info
    env.filters["dedupe_cased"] = _dedupe_cased
    env.filters["street_info"] = _street_info
    env.filters["clean_text"] = _clean_text

    # Discover which variables the template actually references.
    referenced = meta.find_undeclared_variables(env.parse(source))

    # Index dataframe columns by their slug so template variables can match them.
    columns_by_slug = {_slug(col): col for col in df.columns}

    extra_context = extra_context or {}
    extra_slugs = {_slug(k) for k in extra_context}

    context: Dict[str, Any] = dict(extra_context)

    for var in referenced:
        var_slug = _slug(var)
        # extra_context wins; never override an explicitly supplied value.
        if var_slug in extra_slugs:
            continue
        column = columns_by_slug.get(var_slug)
        if column is None:
            continue  # not a dataframe-backed field (e.g. uuid4, a default)

        seen = set()
        values: List[str] = []
        for cell in df[column].tolist():
            for item in _decompose_cell(cell):
                if item not in seen:
                    seen.add(item)
                    values.append(item)
        context[var] = values

    # Raw per-row access: when a template references `rows` (or `rows_raw`),
    # expose one dict per dataframe row so it can build truly row-aligned
    # structures itself, keyed by both the original column name and its slug.
    # This preserves the per-record coupling that the aggregated, de-duplicated
    # column variables above intentionally discard.
    #   - `rows`     : each cell decomposed to a flat list of strings.
    #   - `rows_raw` : each cell parsed but structure-preserved (dict/list/
    #                  scalar), for navigating nested data like `links`.
    if (
        ("rows" in referenced or "rows_raw" in referenced)
        and "rows" not in extra_slugs
        and "rows_raw" not in extra_slugs
    ):
        slug_by_column = {col: _slug(col) for col in df.columns}

        def _parse_cell(value):
            """Parse a cell to its structured value, preserving nesting.

            Unlike :func:`_decompose_cell` (which flattens dicts/lists to a list
            of strings), this keeps the original structure so templates can
            navigate nested data such as ``links`` (``format -> lang -> url``).
            JSON-encoded strings are decoded; everything else is returned as-is.
            Empty / NaN cells become ``None``.
            """
            try:
                if pd.isna(value):
                    return None
            except (TypeError, ValueError):
                pass  # arrays/dicts raise on isna; handled below
            if isinstance(value, str):
                stripped = value.strip()
                if not stripped:
                    return None
                try:
                    return json.loads(stripped)
                except (json.JSONDecodeError, ValueError):
                    return stripped
            return value

        rows: List[Dict[str, Any]] = []
        rows_raw: List[Dict[str, Any]] = []
        for _, row in df.iterrows():
            record: Dict[str, Any] = {}
            record_raw: Dict[str, Any] = {}
            for col in df.columns:
                slug = slug_by_column[col]
                record[col] = record[slug] = _decompose_cell(row[col])
                record_raw[col] = record_raw[slug] = _parse_cell(row[col])
            rows.append(record)
            rows_raw.append(record_raw)
        context["rows"] = rows
        context["rows_raw"] = rows_raw

    # Row-aligned coupled fields: keep multiple columns together per record
    # instead of aggregating/de-duplicating each independently.
    for var, key_to_column in (coupled_fields or {}).items():
        if var not in referenced:
            continue
        # Resolve each output key's column by slug (like aggregated fields).
        resolved = {
            key: columns_by_slug.get(_slug(col)) for key, col in key_to_column.items()
        }
        resolved = {key: col for key, col in resolved.items() if col is not None}
        if not resolved:
            continue

        # Identifier-like keys anchor a record but do not by themselves justify
        # emitting one: a row with only a notice id (no email/phone) is dropped.
        payload_keys = [
            key
            for key in resolved
            if not (key == "id" or key.endswith("-id") or key.endswith("_id"))
        ]

        records: List[Dict[str, Any]] = []
        for _, row in df.iterrows():
            record = {}
            for key, col in resolved.items():
                items = _decompose_cell(row[col])
                record[key] = items[0] if items else None
            if any(record[key] is not None for key in payload_keys):
                records.append(record)
        context[var] = records

    rendered = env.from_string(source).render(**context)
    return yaml.safe_load(rendered)


# ---------------------------------------------------------------------------
# Miscellaneous Support Functions
# ---------------------------------------------------------------------------


def _count_documents(db_client, db_name: str, backend: str) -> int:
    """Return the number of documents in a database/collection for the given backend."""
    if _is_astra_compatible(backend):
        collection_name = _resolve_collection_name(db_client, db_name)
        collection = db_client.get_collection(collection_name)
        return collection.count_documents({}, upper_bound=1_000_000_000)

    if backend == "mongodb":
        collection = db_client[db_name]
        return collection.count_documents({})

    # --- Cloudant path ---
    info = db_client.get_database_information(db=db_name).get_result()
    return info.get("doc_count", 0)


def check_database_status(
    db_names: Union[str, List[str]],
    db_client,
    db_provider: Optional[str] = None,
    create: bool = False,
    return_doc_count: bool = True,
) -> List[dict]:
    """
    Check if databases exist and return status with emojis.

    Args:
        db_names: A single database/collection name or a list of names to check.
        db_client: Initialized database client (CloudantV1, AstraDB Database,
            or MongoDB Database).
        db_provider: Optional explicit backend ("cloudant", "astradb", or "mongodb").
            When omitted the backend is detected from the client type.
        create: If True, create the database/collection when it does not exist.
            Defaults to False (check only).
        return_doc_count: If True, include a ``documents`` field with the number
            of documents in each existing database/collection. Defaults to False.

    Returns:
        A list of dicts, one per database name, each containing:
            - db_name: The database/collection name.
            - status: True if exists, False otherwise.
            - display_marker: ✅ if exists, ❌ otherwise.
            - documents: Number of documents (only when return_doc_count=True).
    """
    if isinstance(db_names, str):
        db_names = [db_names]

    backend = _detect_backend(db_client, db_provider)

    results = []
    for db_name in db_names:
        try:
            exists = ensure_database_exists(
                db_client, db_name, db_provider, create=create
            )
            result = {
                "db_name": db_name,
                "status": exists,
                "display_marker": "✅" if exists else "❌",
            }
            if return_doc_count:
                result["documents"] = (
                    _count_documents(db_client, db_name, backend) if exists else 0
                )
            results.append(result)
        except Exception as e:
            result = {
                "db_name": db_name,
                "status": False,
                "display_marker": "❌",
            }
            if return_doc_count:
                result["documents"] = 0
            results.append(result)
            print(e)

    return results


# ---------------------------------------------------------------------------
# Database initialisation (inherently provider-specific)
# ---------------------------------------------------------------------------


def initialize_astradb_database(
    api_endpoint: str,
    token: str,
    keyspace: Optional[str] = None,
):
    """Initialize Astra DB Database client; return None when required inputs are missing."""
    if not api_endpoint or not token:
        return None

    client = DataAPIClient(token=token)
    return client.get_database(api_endpoint=api_endpoint, keyspace=keyspace or None)


def initialize_hcd_database(
    api_endpoint: str,
    username: str,
    password: str,
    keyspace: Optional[str] = None,
):
    """Initialize a DataStax HCD Database client; return None when required inputs are missing."""
    if not api_endpoint or not username or not password:
        return None

    token = UsernamePasswordTokenProvider(username, password)
    client = DataAPIClient(environment=DataStaxEnvironment.HCD)
    db = client.get_database(
        api_endpoint, token=token, keyspace=keyspace or "default_keyspace"
    )
    db.get_database_admin().create_keyspace(
        keyspace or "default_keyspace",
        update_db_keyspace=True,
    )
    return db


def initialize_mongodb_database(
    endpoint: str,
    username: str,
    password: str,
    cert_path: Optional[str] = None,
    mongodb_atlas: bool = False,
    hostname: Optional[str] = None,
    db_name: Optional[str] = None,
) -> Optional[MongoDatabase]:
    """Initialize MongoDB Database client; return None when required inputs are missing.

    Supports two connection layouts selected via *mongodb_atlas*:

    **IBM Cloud (default, ``mongodb_atlas=False``)** - matches the
    ``_mongodb_ibm.env.TEMPLATE`` layout (MONGODB_ENDPOINT, MONGODB_USERNAME,
    MONGODB_PASSWORD, MONGODB_CERT_PATH). The *endpoint* is expected to contain
    the full MongoDB URI including the database name in the path component,
    e.g.::

        mongodb://HOST:PORT/ibmclouddb?authSource=admin&replicaSet=replset&tls=true

    Username and password placeholders (``$USERNAME``, ``$PASSWORD``) in the
    endpoint are replaced at runtime. If TLS is used, *cert_path* should point
    to the PEM certificate file. The database is taken from the URI's default
    database.

    **MongoDB Atlas (``mongodb_atlas=True``)** - matches the Atlas SRV layout
    (MONGODB_ENDPOINT, MONGODB_USERNAME, MONGODB_PASSWORD, MONGODB_DB,
    MONGODB_HOSTNAME), e.g.::

        mongodb+srv://$MONGODB_USERNAME:$MONGODB_PASSWORD@$MONGODB_HOSTNAME/?appName=$MONGODB_DB

    The ``$MONGODB_USERNAME``, ``$MONGODB_PASSWORD``, ``$MONGODB_HOSTNAME`` and
    ``$MONGODB_DB`` placeholders are replaced at runtime. TLS is negotiated
    automatically by the ``mongodb+srv://`` scheme, so *cert_path* is ignored.
    The Atlas URI carries no default database, so *db_name* must be supplied
    to select the working database.

    Args:
        endpoint: MongoDB connection URI (with the placeholders described
            above for the selected layout).
        username: MongoDB username.
        password: MongoDB password.
        cert_path: Optional path to a TLS/SSL PEM certificate file (IBM layout
            only; ignored when *mongodb_atlas* is True).
        mongodb_atlas: When True, use the Atlas SRV layout instead of the IBM
            Cloud layout.
        hostname: Atlas cluster hostname used to fill the ``$MONGODB_HOSTNAME``
            placeholder (Atlas layout only).
        db_name: Database name used to fill the ``$MONGODB_DB`` placeholder and
            to select the working database (required for the Atlas layout).

    Returns:
        A ``pymongo.database.Database`` instance, or ``None`` when required
        inputs are missing.
    """
    if not endpoint or not username or not password:
        return None

    if mongodb_atlas:
        if not hostname or not db_name:
            return None

        connection_string = (
            endpoint.replace("$MONGODB_USERNAME", username)
            .replace("$MONGODB_PASSWORD", password)
            .replace("$MONGODB_HOSTNAME", hostname)
            .replace("$MONGODB_DB", db_name)
        )

        client = MongoClient(connection_string)
        return client[db_name]

    connection_string = endpoint.replace("$USERNAME", username).replace(
        "$PASSWORD", password
    )

    client_kwargs: Dict[str, Any] = {}
    if cert_path:
        resolved_cert = os.path.abspath(cert_path)
        if os.path.isfile(resolved_cert):
            client_kwargs["tls"] = True
            client_kwargs["tlsCAFile"] = resolved_cert

    client = MongoClient(connection_string, **client_kwargs)
    resolved_db_name = client.get_default_database().name
    return client[resolved_db_name]


def initialize_cloudant_database(
    cloudant_url: str,
    cloudant_apikey: str,
) -> Optional[CloudantV1]:
    """Initialize Cloudant Database client; return None when required inputs are missing."""
    if not cloudant_url or not cloudant_apikey:
        return None

    authenticator = IAMAuthenticator(cloudant_apikey)
    cloudant = CloudantV1(authenticator=authenticator)

    cloudant.set_service_url(cloudant_url)
    cloudant.http_client.verify = certifi.where()
    os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

    return cloudant


# ---------------------------------------------------------------------------
# File / folder helpers
# ---------------------------------------------------------------------------


def load_json_documents(
    folder_path: str,
    skip_corrupted: bool = True,
) -> List[Dict]:
    """
    Load all JSON files from a folder.

    Args:
        folder_path: Path to the folder containing JSON files.
        skip_corrupted: If True, skip files with '_corrupted' in the name.
            Defaults to True.

    Returns:
        List of loaded JSON documents.
    """
    documents = []
    folder = Path(folder_path)

    if not folder.exists():
        raise FileNotFoundError(f"Folder not found: {folder_path}")

    for json_file in folder.glob("*.json"):
        if skip_corrupted and "_corrupted" in json_file.name:
            print(f"Skipping corrupted file: {json_file.name}")
            continue

        try:
            with open(json_file, "r", encoding="utf-8") as f:
                doc = json.load(f)
                documents.append(doc)
                print(f"Loaded: {json_file.name}")
        except json.JSONDecodeError as e:
            print(f"Error parsing {json_file.name}: {e}")
            continue

    return documents


def upload_folder_to_database(
    db_client,
    folder_path: str,
    db_name: str,
    skip_corrupted: bool = True,
    batch_size: int = 100,
    provider: Optional[str] = None,
) -> List[Dict]:
    """
    Load all JSON files from a folder and upload them to a database.

    Args:
        db_client: Initialized database client (CloudantV1 or AstraDB Database).
        folder_path: Path to folder containing JSON files.
        db_name: Target database/collection name.
        skip_corrupted: If True, skip files with '_corrupted' in name.
            Defaults to True.
        batch_size: Number of documents per bulk operation. Defaults to 100.
        provider: Optional explicit backend ("cloudant","astradb","mongodb").

    Returns:
        List of bulk operation responses.
    """
    docs = load_json_documents(folder_path, skip_corrupted=skip_corrupted)

    if not docs:
        print(f"No documents found in {folder_path}")
        return []

    print(f"Uploading {len(docs)} documents to '{db_name}'...")
    responses = bulk_upload_docs(
        db_client=db_client,
        db_name=db_name,
        docs=docs,
        batch_size=batch_size,
        provider=provider,
    )
    print(f"Upload complete: {db_name}")

    return responses


def upload_documents_from_mapping(
    db_client,
    file_templates: Dict[str, List[str]],
    skip_corrupted: bool = True,
    batch_size: int = 100,
    provider: Optional[str] = None,
) -> Dict[str, List]:
    """
    Upload documents to databases using a mapping of db names to file/folder paths.

    Each key is a target database/collection name. Each value is a list of paths
    that can be individual JSON files or directories. Directories are loaded with
    ``load_json_documents``; individual files are read directly.

    Args:
        db_client: Initialized database client (CloudantV1, AstraDB Database,
            or MongoDB Database).
        file_templates: Mapping of ``{db_name: [path, ...]}``. Paths may be
            individual ``.json`` files or directories containing ``.json`` files.
        skip_corrupted: If True, skip files with '_corrupted' in their name
            when loading from directories. Defaults to True.
        batch_size: Number of documents per bulk operation. Defaults to 100.
        provider: Optional explicit backend ("cloudant", "astradb", or "mongodb").

    Returns:
        Dict mapping each db name to the list of bulk-upload responses for that db.
    """
    all_responses: Dict[str, List] = {}

    for db_name, paths in file_templates.items():
        docs: List[Dict] = []

        for raw_path in paths:
            p = Path(raw_path)
            if p.is_dir():
                docs.extend(load_json_documents(str(p), skip_corrupted=skip_corrupted))
            elif p.is_file():
                if skip_corrupted and "_corrupted" in p.name:
                    print(f"Skipping corrupted file: {p.name}")
                    continue
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        doc = json.load(f)
                    if isinstance(doc, list):
                        docs.extend(doc)
                    else:
                        docs.append(doc)
                    print(f"Loaded: {p.name}")
                except json.JSONDecodeError as e:
                    print(f"Error parsing {p.name}: {e}")
            else:
                print(f"Path not found, skipping: {raw_path}")

        if not docs:
            print(f"No documents found for '{db_name}', skipping upload.")
            all_responses[db_name] = []
            continue

        print(f"Uploading {len(docs)} document(s) to '{db_name}'...")
        responses = bulk_upload_docs(
            db_client=db_client,
            db_name=db_name,
            docs=docs,
            batch_size=batch_size,
            provider=provider,
        )
        print(f"Upload complete: {db_name}")
        all_responses[db_name] = responses

    return all_responses


def purge_databases(
    db_client,
    db_names: Union[str, List[str]],
    reupload: bool = False,
    file_templates: Optional[Dict[str, List[str]]] = None,
    skip_corrupted: bool = True,
    batch_size: int = 100,
    provider: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Delete all documents in the provided databases/collections (by name).

    Optionally re-upload documents from a directory/file mapping afterwards,
    matching how documents are uploaded initially via
    ``upload_documents_from_mapping`` (used in ``prepare_databases.py`` and
    ``iterative_generation_demonstration_v3.3.py``).

    The databases/collections themselves are left in place; only their
    documents are removed.

    Args:
        db_client: Initialized database client (CloudantV1, AstraDB Database,
            or MongoDB Database).
        db_names: A single database/collection name or a list of names to purge.
        reupload: If True, re-upload documents after purging using
            ``file_templates``. Defaults to False.
        file_templates: Mapping of ``{db_name: [path, ...]}`` used when
            ``reupload`` is True. Paths may be individual ``.json`` files or
            directories containing ``.json`` files. Required when reupload=True.
        skip_corrupted: If True, skip files with '_corrupted' in their name
            when re-uploading from directories. Defaults to True.
        batch_size: Number of documents per bulk operation. Defaults to 100.
        provider: Optional explicit backend ("cloudant", "astradb", "hcd",
            or "mongodb"). When omitted the backend is detected from the client.

    Returns:
        Dict with:
            - "purged": mapping of db_name -> number of documents deleted.
            - "reuploaded": mapping of db_name -> upload responses (only present
              when reupload is True).
    """
    backend = _detect_backend(db_client, provider)

    if isinstance(db_names, str):
        db_names = [db_names]

    purged: Dict[str, int] = {}

    for db_name in db_names:
        try:
            if _is_astra_compatible(backend):
                collection_name = _resolve_collection_name(db_client, db_name)
                collection = db_client.get_collection(collection_name)
                result = collection.delete_many({})
                purged[db_name] = getattr(result, "deleted_count", 0) or 0

            elif backend == "mongodb":
                collection = db_client[db_name]
                result = collection.delete_many({})
                purged[db_name] = result.deleted_count

            else:  # cloudant
                docs = retrieve_documents(
                    db_client=db_client,
                    db_name=db_name,
                    selectors={"_id": {"$gt": None}},
                    fields=["_id", "_rev"],
                    limit=100000,
                    docs_only=True,
                    provider=backend,
                )
                deleted = 0
                if docs:
                    delete_docs = [
                        {"_id": d["_id"], "_rev": d["_rev"], "_deleted": True}
                        for d in docs
                        if "_id" in d and "_rev" in d
                    ]
                    if delete_docs:
                        db_client.post_bulk_docs(
                            db=db_name, bulk_docs={"docs": delete_docs}
                        ).get_result()
                        deleted = len(delete_docs)
                purged[db_name] = deleted

            print(f"Purged {purged[db_name]} document(s) from '{db_name}'")
        except Exception as e:
            print(f"Failed to purge '{db_name}': {e}")
            purged[db_name] = 0

    summary: Dict[str, Any] = {"purged": purged}

    if reupload:
        if not file_templates:
            raise ValueError("file_templates is required when reupload=True.")
        summary["reuploaded"] = upload_documents_from_mapping(
            db_client=db_client,
            file_templates=file_templates,
            skip_corrupted=skip_corrupted,
            batch_size=batch_size,
            provider=backend,
        )

    return summary


def upload_example_documents(
    db_client,
    base_path: str,
    folder_db_mapping: Optional[Dict[str, str]] = None,
    skip_corrupted: bool = True,
    provider: Optional[str] = None,
) -> Dict[str, List[Dict]]:
    """
    Upload all example documents from subfolders to their corresponding databases.

    Args:
        db_client: Initialized database client (CloudantV1 or AstraDB Database).
        base_path: Path to the base folder containing subfolders
            (e.g., 'examples/json_documents').
        folder_db_mapping: Mapping of folder names to database names. Defaults to:
            {"ORG_CONTEXT": "org_context", "MODEL_PARAMETERS": "model_parameters",
            "GENERATION_CONTEXT": "generation_context"}
        skip_corrupted: If True, skip files with '_corrupted' in name.
            Defaults to True.
        provider: Optional explicit backend ("cloudant","astradb","mongodb").

    Returns:
        Dict mapping database names to their upload responses.
    """
    if folder_db_mapping is None:
        folder_db_mapping = {
            "ORG_CONTEXT": "org_context",
            "MODEL_PARAMETERS": "model_parameters",
            "GENERATION_CONTEXT": "generation_context",
        }

    base = Path(base_path)
    if not base.exists():
        raise FileNotFoundError(f"Base path not found: {base_path}")

    all_responses = {}

    for folder_name, db_name in folder_db_mapping.items():
        folder_path = base / folder_name

        if not folder_path.exists():
            print(f"Folder not found, skipping: {folder_path}")
            continue

        responses = upload_folder_to_database(
            db_client=db_client,
            folder_path=str(folder_path),
            db_name=db_name,
            skip_corrupted=skip_corrupted,
            provider=provider,
        )
        all_responses[db_name] = responses

    return all_responses


# ---------------------------------------------------------------------------
# Iteration document helpers
# ---------------------------------------------------------------------------


def create_iteration_document(
    db_client,
    db_name: str,
    iteration_id: str,
    user_id: str,
    org_id: str,
    parameter_set_name: str,
    system_template_name: str,
    user_context: Dict[str, Any],
    iteration_length: int = 5,
    next_question_user_message: Optional[Dict[str, Any]] = None,
    starter_messages: Dict[str, Any] = None,
    language: str = None,
    provider: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a new iteration document in the database.

    Args:
        db_client: Initialized database client (CloudantV1 or AstraDB Database).
        db_name: Target database/collection name.
        iteration_id: Unique iteration identifier.
        user_id: User identifier.
        org_id: Organization ID.
        parameter_set_name: Name of the parameter set being used.
        system_template_name: Name of the system template being used.
        user_context: User-provided context for the iterative generation.
        iteration_length: Number of iterative generation steps (default 5).
        next_question_user_message: User message template for subsequent iterations.
        starter_messages: Starting system prompt and user input messages
            (fallback template in function).
        language: Desired output language.
        provider: Optional explicit backend ("cloudant","astradb","mongodb").

    Returns:
        Created iteration document.
    """
    backend = _detect_backend(db_client, provider)

    starter_messages_template = starter_messages or [
        {
            "role": "system",
            "content": "{{ system_prompt }}{% if context %}\n\nContext:\n{{ context }}{% endif %}{% if language %}\n\nOutput Language: {{ language }}{% endif %}",
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "{% if user_context %}{% for key, value in user_context.items() %}{% if value %}\n{{ key | replace('_', ' ') | title }}: {{ value }}{% endif %}{% endfor %}{% endif %}",
                }
            ],
        },
    ]

    default_next_question = next_question_user_message or {
        "role": "user",
        "content": [{"type": "text", "text": "Generate Next Output."}],
    }

    iteration_doc = {
        "_id": str(uuid.uuid4()),
        "iteration_id": iteration_id,
        "user_id": user_id,
        "org_id": org_id,
        "next_question_user_message": default_next_question,
        "parameter_set_name": parameter_set_name,
        "system_template_name": system_template_name,
        "iteration_length": iteration_length,
        "user_context": user_context,
        "language": language,
        "generation_content": {
            "messages": starter_messages_template,
            "results": [],
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "total_tokens": 0,
                "iterations_completed": 0,
            },
        },
    }

    ensure_database_exists(db_client, db_name, provider=backend)

    try:
        if _is_astra_compatible(backend):
            collection = db_client.get_collection(db_name)
            collection.insert_one(iteration_doc)
        elif backend == "mongodb":
            collection = db_client[db_name]
            collection.insert_one(iteration_doc)
        else:
            db_client.post_document(db=db_name, document=iteration_doc).get_result()

        return iteration_doc
    except Exception as exc:
        raise RuntimeError(
            f"create_iteration_document failed "
            f"(provider={backend}, db_name={db_name}, "
            f"iteration_id={iteration_id}, cause_type={type(exc).__name__}, cause={exc})"
        ) from exc


def update_iteration_document(
    db_client,
    db_name: str,
    iteration_id: str,
    new_messages: Optional[List[Dict[str, Any]]] = None,
    new_results: Optional[List[Dict[str, Any]]] = None,
    token_count: Optional[Dict[str, Any]] = None,
    update_messages: Optional[List[Dict[str, Any]]] = None,
    provider: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Update an existing iteration document with new messages, results, and token usage.

    Args:
        db_client: Initialized database client (CloudantV1 or AstraDB Database).
        db_name: Target database/collection name.
        iteration_id: Iteration identifier to update.
        new_messages: New messages to append.
        new_results: New results to append.
        token_count: Token usage information.
        update_messages: If provided, overwrites the entire messages list.
        provider: Optional explicit backend ("cloudant","astradb","mongodb").

    Returns:
        Updated iteration document.
    """
    backend = _detect_backend(db_client, provider)

    ensure_database_exists(db_client, db_name, provider=backend)

    try:
        iteration_docs = retrieve_documents(
            db_client=db_client,
            db_name=db_name,
            selectors={"iteration_id": {"$eq": iteration_id}},
            docs_only=True,
            limit=1,
            provider=backend,
        )

        if not iteration_docs or not isinstance(iteration_docs, list):
            raise ValueError(
                f"Iteration document with iteration_id={iteration_id} not found"
            )

        iteration_doc: Dict[str, Any] = iteration_docs[0]

        if "generation_content" not in iteration_doc:
            iteration_doc["generation_content"] = {
                "messages": [],
                "results": [],
                "metadata": {},
            }

        gen = iteration_doc["generation_content"]

        if update_messages is not None:
            gen["messages"] = update_messages
        elif new_messages:
            gen.setdefault("messages", []).extend(new_messages)

        if new_results:
            gen.setdefault("results", []).extend(new_results)

        metadata: Dict[str, Any] = gen.setdefault("metadata", {})

        if token_count:
            metadata["total_tokens"] = metadata.get(
                "total_tokens", 0
            ) + token_count.get("total_tokens", 0)
            metadata["last_token_count"] = token_count

        metadata["iterations_completed"] = metadata.get("iterations_completed", 0) + 1
        metadata["last_updated"] = datetime.now().isoformat()

        if _is_astra_compatible(backend):
            collection = db_client.get_collection(db_name)
            doc_id = iteration_doc["_id"]
            update_data = {k: v for k, v in iteration_doc.items() if k != "_id"}
            collection.update_one(filter={"_id": doc_id}, update={"$set": update_data})
        elif backend == "mongodb":
            collection = db_client[db_name]
            doc_id = iteration_doc["_id"]
            update_data = {k: v for k, v in iteration_doc.items() if k != "_id"}
            collection.update_one({"_id": doc_id}, {"$set": update_data})
        else:
            db_client.post_document(db=db_name, document=iteration_doc).get_result()

        return iteration_doc
    except Exception as exc:
        raise RuntimeError(
            f"update_iteration_document failed "
            f"(provider={backend}, db_name={db_name}, "
            f"iteration_id={iteration_id}, cause_type={type(exc).__name__}, cause={exc})"
        ) from exc


def append_rendered_yaml(df, content_column="content", output_column="rendered_yaml"):
    _df = df.copy()
    _df[output_column] = _df[content_column].apply(
        lambda _text: parse_yaml_documents(_text) if isinstance(_text, str) else None
    )
    return _df


def collect_urls(df, url_column="download_urls", extension_replacement="/xml"):
    import ast

    all_urls = []
    for _entry in df[url_column]:
        if isinstance(_entry, str):
            try:
                parsed = ast.literal_eval(_entry)
            except (ValueError, SyntaxError):
                parsed = [_entry]
        else:
            parsed = _entry
        for url in parsed or []:
            all_urls.append(url.replace("/pdf", extension_replacement))
    return all_urls
