# iterative-inference-nosql-jinja2-engine

A toolkit for **context engineering and iterative LLM inference** backed by NoSQL document databases. Prompts, system templates, model parameters, and organisational context are stored as structured documents, rendered at inference time using [Jinja2](https://jinja.palletsprojects.com/en/stable/), and passed to any supported inference provider.

Supported inference providers (via a single provider-agnostic client):

- [IBM watsonx.ai](https://www.ibm.com/products/watsonx-ai)
- [IBM watsonx Orchestrate](https://www.ibm.com/products/watsonx-orchestrate) (cloud and Cloud Pak for Data)
- [Red Hat AI Inference on IBM Cloud](https://cloud.ibm.com/inference/overview)
- Any **OpenAI SDK-compatible** endpoint

Supported database backends: **Datastax AstraDB & HyperConvergedDatabase (HCD)**, **MongoDB**, **IBM Cloudant**. Elasticsearch support is planned and in the works.

---

## Repository Structure

```text
.
├── src/                        # Core helper modules
│   ├── helpers/                # Database, auth, and UI helpers
│   └── utils/                  # Environment variable utilities
├── examples/                   # JSON schemas and seed documents for each document type
│   ├── db_structure_templates/ # Field-level schema definitions
│   └── json_documents/         # Ready-to-upload example documents
├── docs/
    └── cheatsheets/            # Jinja2 and Cloudant query reference docs
```

---

## src/

The `src/` directory contains the core Python modules that handle database access, authentication, and Marimo UI utilities. All database functions are provider-agnostic - they accept any supported `db_client` object and dispatch to the correct backend automatically.

### src/helpers/

| File                                  | Purpose                                                                                                                                                                                                                                       |
| ------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `nosql_database_helper_functions.py`  | Provider-agnostic database layer for IBM Cloudant, Datastax AstraDB, Datastax HCD, and MongoDB. Covers client initialisation, CRUD, Jinja2 template rendering, iteration document management, schema inference, and bulk JSON file upload.    |
| `inference_helper_functions.py`       | Provider-agnostic inference layer. Single `initialize_inference_client()` and model-listing/calling helpers for IBM watsonx.ai, IBM watsonx Orchestrate, Red Hat AI Inference, OpenAI SDK-compatible endpoints, and IBM Consulting Advantage. |
| `auth_helper_functions.py`            | IBM Cloud authentication utilities - IAM token retrieval, Zen auth header generation, watsonx.ai client setup, and watsonx Orchestrate token management with support for IAM, MCSP, MCSP v2, and CPD auth modes.                              |
| `marimo_widget_helper_functions.py`   | Marimo UI helpers - schema-driven DataFrame creation for data editors, column definitions from JSON templates, and a hidden auto-refresh ticker for polling-based reactive cells.                                                             |
| `marimo_sortable_kv.py`               | Custom Marimo anywidget for editing ordered key/value lists in the UI.                                                                                                                                                                        |
| `marimo_sortable_textarea.py`         | Custom Marimo anywidget for editing ordered lists of multi-line text blocks.                                                                                                                                                                  |
| `data_validation_helper_functions.py` | Client-side helpers for calling the deployable JSON Schema data validators (the counterpart to the deployable watsonx.ai validator functions in this repo).                                                                                   |

### src/utils/

| File                        | Purpose                                                                                                                                   |
| --------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `load_all_dotenv.py`        | Loads a single `.env` file or all `.env*` files in a directory. Useful for managing credentials across multiple environments or services. |
| `wxai_ai_service_deploy.py` | Deploys a watsonx.ai AI service to a deployment space.                                                                                    |
| `wxai_ai_service_upload.py` | Uploads / registers a watsonx.ai AI service asset.                                                                                        |
| `wxai_functions_deploy.py`  | Deploys a watsonx.ai Python function to a deployment space.                                                                               |
| `wxai_functions_upload.py`  | Uploads / registers a watsonx.ai Python function asset.                                                                                   |

---

## Marimo Applications

Interactive notebooks built with [Marimo](https://marimo.io/). Run any of them with `marimo run <filename>`.

| File                                         | Purpose                                                                                                                                                                                                                                                                                 |
| -------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `org_document_drafting.py`                   | Interactive editor for creating and uploading organisation context documents. Covers client name, description, language, terminology mappings, taxonomy, offerings, and location data. Supports Cloudant, AstraDB, HCD, and MongoDB backends.                                           |
| `iterative_generation_demonstration_v3.3.py` | Full end-to-end iterative generation demo. Loads system templates and model parameters from the database, retrieves organisation context, renders Jinja2 prompts, runs N rounds of generation against any supported provider, and writes results and token counts back to the database. |

---

## examples/

### examples/db_structure_templates/

JSON schema files that define the expected field structure for each document type stored in the database. Use these as a reference when creating new documents or extending existing ones.

| File                        | Document type                  | Description                                                                                                                                                                                             |
| --------------------------- | ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `organization_context.json` | Organisation context           | Client name, description, language, terminology mappings, taxonomy, offerings, and location operations.                                                                                                 |
| `generation_context.json`   | Iteration / generation context | Iteration ID, org ID, parameter set, system template name, iteration length, user context fields, and the `generation_content` envelope that accumulates messages, results, and metadata across rounds. |
| `model_parameters.json`     | Model parameters               | Named parameter set containing a `model_id` and generation params (`temperature`, `max_completion_tokens`, `top_p`, `stop`, etc.).                                                                      |
| `system_templates.json`     | System templates               | Named template set containing a system prompt, context field, output structure example, and a `next_question_user_message` for multi-turn workflows. All string fields support Jinja2.                  |

### examples/json_documents/

Ready-to-upload seed documents for each collection. Upload them to a running database with `upload_example_documents()` or `upload_folder_to_database()`.

| Folder                  | Contents                                                                                                              |
| ----------------------- | --------------------------------------------------------------------------------------------------------------------- |
| `system-templates/`     | Example system prompt templates with Jinja2 placeholders for client name, org description, taxonomy, and terminology. |
| `model-parameters/`     | Example named parameter sets for different generation styles (e.g. conservative, creative).                           |
| `generation-context/`   | Example initialisation documents for starting an iterative generation workflow.                                       |
| `organization-context/` | Example organisation context documents for testing template rendering.                                                |

---

## docs/cheatsheets/

Reference documents for the two main query and templating systems used across the project.

| File                                     | Description                                                                                                                                             |
| ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `jinja2_templating_cheatsheet.md`        | Comprehensive Jinja2 reference - variables, filters, tests, control structures, loops, macros, template inheritance, whitespace control, and operators. |
| `cloudant_query_parameter_cheatsheet.md` | Cloudant Mango query syntax and selector operators with examples.                                                                                       |
| `cloudant_query_guidelines.md`           | Guidance on designing efficient Cloudant queries, index usage, and common patterns.                                                                     |

---

## How Jinja2 Rendering Works

System templates are stored in the database as Jinja2 strings. At inference time, `render_jinja2_templates()` renders them using fields from the retrieved organisation context and any additional context documents passed in.

System template (stored in the database):

```jinja
You are an expert assistant for {{ client_name }}.

{{ org_description }}
{% if terminology_mapping %}

Terminology:
{% for item in terminology_mapping %}- Use "{{ item.replacement }}" instead of "{{ item.original }}"
{% endfor %}{% endif %}
{% if taxonomy %}

Key terms:
{% for item in taxonomy %}- {{ item.term }}: {{ item.definition }}
{% endfor %}{% endif %}
```

Organisation context document (stored in the database):

```json
{
  "client_name": "Acme Corp",
  "org_description": "A global logistics firm specialising in cold-chain delivery.",
  "terminology_mapping": [{ "original": "shipment", "replacement": "consignment" }],
  "taxonomy": [{ "term": "POD", "definition": "Proof of Delivery" }]
}
```

Rendered system prompt:

```md
You are an expert assistant for Acme Corp.

A global logistics firm specialising in cold-chain delivery.

Terminology:
- Use "consignment" instead of "shipment"

Key terms:
- POD: Proof of Delivery
```

Undefined template variables are left as-is rather than raising an error, so the same template works across organisations with different context shapes.

---

## Configuration

Copy `.env` and populate the credentials for the backends you plan to use:

| Variable                                                                                               | Service                  |
| ------------------------------------------------------------------------------------------------------ | ------------------------ |
| `WX_API_KEY` (or `IBM_CLOUD_API_KEY`), `WX_URL`, `WX_PROJECT_ID`, `WX_SPACE_ID`                        | IBM watsonx.ai           |
| `WXO_API_KEY`, `WXO_INSTANCE_URL`, `WXO_AUTH_TYPE`                                                     | IBM watsonx Orchestrate  |
| `RHAI_INF_PROJECT`, `RHAI_INF_REGION`, `RHAI_INF_DEFAULT_MODEL`                                        | Red Hat AI Inference     |
| `CLOUDANT_URL`, `CLOUDANT_APIKEY`                                                                      | IBM Cloudant             |
| `ASTRA_DB_API_ENDPOINT`, `ASTRA_DB_APPLICATION_TOKEN`, `ASTRA_DB_KEYSPACE`                             | Datastax AstraDB         |
| `DATASTAX_HCD_ENDPOINT`, `DATASTAX_HCD_API_USER`, `DATASTAX_HCD_API_PASSWORD`, `DATASTAX_HCD_KEYSPACE` | Datastax HCD             |
| `MONGODB_ENDPOINT`, `MONGODB_USERNAME`, `MONGODB_PASSWORD`, `MONGODB_CERT_PATH`                        | MongoDB                  |
| `COS_URL_ENDPOINT`, `COS_ACCESS_KEY`, `COS_SECRET_KEY`                                                 | IBM Cloud Object Storage |
| `CHAT_MODEL`                                                                                           | Default chat model id    |

`WXO_AUTH_TYPE` selects the watsonx Orchestrate auth mode: `ibm_iam`, `mcsp`, `mcsp_v2`, or `cpd`.

Multiple `.env` files in a directory are supported via `load_all_dotenv.py`.

---

## Requirements

- Python 3.12+
- Key dependencies: `ibm-watsonx-ai`, `ibm-watsonx-orchestrate`, `openai`, `ibmcloudant`, `astrapy`, `pymongo`, `elasticsearch`, `jinja2`, `marimo`, `pydantic-ai`, `pycountry`, `python-dotenv`

Install all dependencies with:

```bash
uv sync
# or
pip install -r requirements.txt
```

---
