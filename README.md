# iterative-inference-nosql-jinja2-engine

A toolkit for **context engineering and iterative LLM inference** backed by NoSQL document databases. Prompts, system templates, model parameters, and organisational context are stored as structured documents, rendered at inference time using [Jinja2](https://jinja.palletsprojects.com/en/stable/), and passed to [IBM watsonx.ai](https://www.ibm.com/products/watsonx-ai) or [IBM watsonx Orchestrate](https://www.ibm.com/products/watsonx-orchestrate) for model inference.

Supported database backends: **IBM Cloudant**, **Datastax AstraDB**, **MongoDB**, Elasticsearch support is planned and in the works..

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
│   └── cheatsheets/            # Jinja2 and Cloudant query reference docs
└── plans/                      # Refactoring roadmap
```

---

## src/

The `src/` directory contains the core Python modules that handle database access, authentication, and Marimo UI utilities. All database functions are provider-agnostic - they accept any supported `db_client` object and dispatch to the correct backend automatically.

### src/helpers/

| File                                 | Purpose                                                                                                                                                                                                                      |
| ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `nosql_database_helper_functions.py` | Provider-agnostic database layer for IBM Cloudant, Datastax AstraDB, and MongoDB. Covers client initialisation, CRUD, Jinja2 template rendering, iteration document management, schema inference, and bulk JSON file upload. |
| `auth_helper_functions.py`           | IBM Cloud authentication utilities - IAM token retrieval, Zen auth header generation, watsonx.ai client setup, and watsonx Orchestrate token management with support for IAM, MCSP, MCSP v2, and CPD auth modes.             |
| `marimo_widget_helper_functions.py`  | Marimo UI helpers - schema-driven DataFrame creation for data editors, column definitions from JSON templates, and a hidden auto-refresh ticker for polling-based reactive cells.                                            |

### src/utils/

| File                 | Purpose                                                                                                                                   |
| -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `load_all_dotenv.py` | Loads a single `.env` file or all `.env*` files in a directory. Useful for managing credentials across multiple environments or services. |

---

## Marimo Applications

Interactive notebooks built with [Marimo](https://marimo.io/). Run any of them with `marimo run <filename>`.

| File                                         | Purpose                                                                                                                                                                                                                                                             |
| -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `org_document_drafting.py`                   | Interactive editor for creating and uploading organisation context documents. Covers client name, description, language, terminology mappings, taxonomy, offerings, and location data. Supports Cloudant, AstraDB, and MongoDB backends.                            |
| `iterative_generation_demonstration_v2.5.py` | Full end-to-end iterative generation demo. Loads system templates and model parameters from the database, retrieves organisation context, renders Jinja2 prompts, runs N rounds of watsonx.ai generation, and writes results and token counts back to the database. |

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

| Variable                                                                        | Service                 |
| ------------------------------------------------------------------------------- | ----------------------- |
| `WATSONX_API_KEY`, `WATSONX_PROJECT_ID`, `WATSONX_URL`                          | IBM watsonx.ai          |
| `WXO_API_KEY`, `WXO_INSTANCE_URL`                                               | IBM watsonx Orchestrate |
| `CLOUDANT_URL`, `CLOUDANT_APIKEY`                                               | IBM Cloudant            |
| `ASTRA_API_ENDPOINT`, `ASTRA_TOKEN`, `ASTRA_KEYSPACE`                           | Datastax AstraDB        |
| `MONGODB_ENDPOINT`, `MONGODB_USERNAME`, `MONGODB_PASSWORD`, `MONGODB_CERT_PATH` | MongoDB                 |

Multiple `.env` files in a directory are supported via `load_all_dotenv.py`.

---

## Requirements

- Python 3.12+
- Key dependencies: `ibm-watsonx-ai`, `ibm-watsonx-orchestrate`, `ibmcloudant`, `astrapy`, `pymongo`, `jinja2`, `marimo`, `pydantic-ai`, `python-dotenv`

Install all dependencies with:

```bash
uv sync
# or
pip install -r requirements.txt
```

---
