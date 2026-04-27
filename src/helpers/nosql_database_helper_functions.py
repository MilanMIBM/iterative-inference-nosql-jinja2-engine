from __future__ import annotations

from ibmcloudant.cloudant_v1 import CloudantV1
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from pathlib import Path

import certifi
import marimo as mo
from astrapy import DataAPIClient
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
    """Return 'cloudant', 'astradb', or 'mongodb' based on client type or explicit provider."""
    if provider:
        return provider.strip().lower()
    if isinstance(db_client, CloudantV1):
        return "cloudant"
    if isinstance(db_client, MongoDatabase):
        return "mongodb"
    return "astradb"


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

    if backend == "astradb":
        try:
            existing = set(db_client.list_collection_names())
            if db_name not in existing:
                if not create:
                    return False
                db_client.create_collection(db_name)
            return True
        except Exception as e:
            print(f"Failed to ensure AstraDB collection {db_name}: {str(e)}")
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
    elif backend == "astradb":
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
        if backend == "astradb":
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
        db_client: Initialized database client (CloudantV1 or AstraDB Database).
        db_name: Target database/collection name.
        docs: List of document dicts to update.
        batch_size: Number of documents per bulk operation. Defaults to 100.
        provider: Optional explicit backend ("cloudant","astradb","mongodb").

    Returns:
        List of bulk operation response dicts.
    """
    backend = _detect_backend(db_client, provider)

    if not docs:
        raise ValueError("No documents provided for update.")

    ensure_database_exists(db_client, db_name, provider=backend)

    try:
        if backend == "astradb":
            for i, doc in enumerate(docs):
                if "_id" not in doc:
                    raise ValueError(
                        f"Document at index {i} is missing '_id'. "
                        "This is required to update an existing AstraDB document."
                    )
            if db_client is None:
                raise ValueError("AstraDB client is None. Cannot perform bulk update.")

            collection_name = _resolve_collection_name(db_client, db_name)
            collection = db_client.get_collection(collection_name)
            batches = [
                docs[i : i + batch_size] for i in range(0, len(docs), batch_size)
            ]

            responses: list = []
            for batch in mo.status.progress_bar(
                batches,
                title="Updating AstraDB documents",
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
        db_client: Initialized database client (CloudantV1 or AstraDB Database).
        db_name: Target database/collection name.
        docs: Documents - dict with 'results' key or direct list.
        batch_size: Number of documents per bulk operation. Defaults to 100.
        provider: Optional explicit backend ("cloudant","astradb","mongodb").

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

    if backend == "astradb":
        responses: list = []
        for batch in mo.status.progress_bar(
            batches,
            title="Uploading to AstraDB",
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

    if backend == "astradb":
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


def parse_yaml_documents(raw_yaml, safe_load=True):
    raw_documents = re.findall(
        r"-{3,}\s*\n(.*?)\s*(?=-{3,})", raw_yaml, flags=re.DOTALL
    )
    cleaned = [doc.strip() for doc in raw_documents if doc.strip()]

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


# ---------------------------------------------------------------------------
# Miscellaneous Support Functions
# ---------------------------------------------------------------------------


def check_database_status(
    db_names: Union[str, List[str]],
    db_client,
    db_provider: Optional[str] = None,
    create: bool = False,
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

    Returns:
        A list of dicts, one per database name, each containing:
            - db_name: The database/collection name.
            - status: True if exists, False otherwise.
            - display_marker: ✅ if exists, ❌ otherwise.
    """
    if isinstance(db_names, str):
        db_names = [db_names]

    results = []
    for db_name in db_names:
        try:
            exists = ensure_database_exists(
                db_client, db_name, db_provider, create=create
            )
            results.append(
                {
                    "db_name": db_name,
                    "status": exists,
                    "display_marker": "✅" if exists else "❌",
                }
            )
        except Exception as e:
            results.append(
                {
                    "db_name": db_name,
                    "status": False,
                    "display_marker": "❌",
                }
            )

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


def initialize_mongodb_database(
    endpoint: str,
    username: str,
    password: str,
    cert_path: Optional[str] = None,
) -> Optional[MongoDatabase]:
    """Initialize MongoDB Database client; return None when required inputs are missing.

    Builds the connection URI from discrete credentials matching the
    ``_mongodb_ibm.env.TEMPLATE`` layout (MONGODB_ENDPOINT, MONGODB_USERNAME,
    MONGODB_PASSWORD, MONGODB_CERT_PATH).

    The *endpoint* value is expected to contain the full MongoDB URI
    (including the database name in the path component), e.g.::

        mongodb://HOST:PORT/ibmclouddb?authSource=admin&replicaSet=replset&tls=true

    Username and password placeholders (``$USERNAME``, ``$PASSWORD``) in the
    endpoint are replaced at runtime. If TLS is used, *cert_path* should
    point to the PEM certificate file.

    Args:
        endpoint: MongoDB connection URI (may contain ``$USERNAME`` /
            ``$PASSWORD`` placeholders).
        username: MongoDB username.
        password: MongoDB password.
        cert_path: Optional path to a TLS/SSL PEM certificate file.

    Returns:
        A ``pymongo.database.Database`` instance, or ``None`` when required
        inputs are missing.
    """
    if not endpoint or not username or not password:
        return None

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
    db_name = client.get_default_database().name
    return client[db_name]


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
        if backend == "astradb":
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

        if backend == "astradb":
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
