Coding and deploying AI services manually
[Check for Updates here](https://dataplatform.cloud.ibm.com/docs/content/wsj/analyze-data/ai-services-manual-coding.html?context=wx&audience=wdp)

The manual coding approach for deploying AI services involves writing custom code to deploy and manage AI services. This approach provides full control over the deployment process and allows for customization to meet specific requirements.

Process overview
The following graphic illustrates the process of coding AI services.

You can create a notebook that contains the AI service and connections within the Project. The AI service captures the logic of your RAG application and contains the generation function, which is a deployable unit of code. The generation function is promoted to the deployment space, which is used to create a deployment. The deployment is exposed as a REST API endpoint that can be accessed by other applications. You can send a request to the REST API endpoint to use the deployed AI service for inferencing. The deployed AI service processes the request and returns a response.

Manual coding use case

Tasks for creating and deploying AI services
Follow these steps to create, deploy, and manage AI services:

Create an AI service: Define an AI service in a notebook by using Python. The AI service must meet specific requirements for deploying as an AI service.
Test AI service: Test the coding logic of your AI service locally.
Create AI service assets: After you create and test the AI service, you must package the AI service as a deployable asset.
Deploy AI service assets: Deploy the AI service asset as an online or a batch deployment.
Testing AI service deployment: Test your deployed AI service for online inferencing or batch scoring.
Manage AI services: Access and update the deployment details. Scale or delete the deployment from the user interface or programmatically.
Creating AI services in a notebook
To deploy an AI service, you can create an AI service directly in a notebook. You must define your AI service in Python and it must meet certain requirements. To deploy an AI service, you must create a watsonx.ai Runtime repository asset and upload the Python file to the asset.

Defining an AI service with Python client library
To define an AI service in a notebook by using the watsonx.ai Python client library, follow these steps:

To work with AI service in Python, install the ibm-watsonx-ai Python SDK:

```python
from ibm_watsonx_ai import APIClient
from ibm_watsonx_ai import Credentials

credentials = Credentials(
    url=url, api_key=apikey
)

client = APIClient(credentials)
client.set.default_space(space_id=space_id)
```

Define your AI service in Python by using the following layout. Depending on your use case, you must include at least one of these functions as a nested function:

```python
generate()
generate_stream()
generate_batch()
```
For more information, see Requirements for creating an AI service.

```python
 def basic_generate_demo(context, model="google/flan-t5-xl", **parameters):
 # "parameters" is a reserved argument and will be enabled in future

 # generate token from task credentials api
 task_token = context.generate_token()

     def generate(context):
         user_token = context.get_token()  # extract token from header
         user_headers = context.get_headers()
         json_body = context.get_json()

         # example 1: json
         return {
             "headers": {
                 "Content-Type": "application/json",
                 "user-custom-header": "my-header-x1",
             },
             "body": {
                 "model": model
             },
         }

     def generate_stream(context):
         user_token = context.get_token()  # extract token from header
         user_headers = context.get_headers()
         json_body = context.get_json()

         # return a generator
         data_to_stream = json_body.get("sse", "Default message!")
         for x in data_to_stream:
             yield x

     def generate_batch(input_data_references, output_data_reference):
         # generate token from task credentials api
         task_token = context.generate_token()
         # do something.
         # ...

     return generate, generate_stream, generate_batch
```



Requirements for defining an AI service

The AI service captures the logic of your generative AI use case (such as a Retrieval-augmented generation application) and handles the REST API call to the deployment endpoint /ml/v4/deployments.

Follow these guidelines to define an AI service:
Create a Python function. You can specify any name for your function. To learn more about the function parameters, see the watsonx.ai REST API documentation.
Depending on your use case, the Python function that you want to deploy must include at least one of these functions as a nested function in its scope:

```python
generate()
generate_stream()
generate_batch()
```

When you use the watsonx.ai Python client library to save the Python function that contains a reference to an outer function, only the code in the scope of the outer function (including its nested functions) is saved. The code outside the outer function's scope is not be saved and therefore is not be available when you deploy the function.

Guidelines for defining the generate() function
The generate() function can be used to process your authorization token. This function handles the REST call to the inference endpoint /ml/v4/deployments/{id_or_name}/ai_service.

Follow these guidelines to define the generate() function inside the AI service:

You must use the name generate to define the function.
You can only provide one argument to the generate() function: context.
The generate() function must return a value of the data type dict (dictionary).
Optional: You can optionally specify the body or header keys.

Example generate():
```python
def generate(context):
    user_token = context.get_token()
    headers = context.get_headers()
    json_body = context.get_json()

    return {
        "headers": {
             "Content-Type": "text/plain"
        },
        "body": "Hello WatsonX"
    }
```

Guidelines for defining the generate_stream() function
You can use the generate_stream() function for generative AI use cases that require streaming. This function handles the REST call to the Server-Sent Events (SSE) inference endpoint POST /ml/v4/deployments/{id_or_name}/ai_service_stream.

Follow these guidelines to define the generate_stream() function inside the AI service:

You must use the name generate_stream to define the function.
You can only provide one argument to the generate_stream() function: context.

Example generate_stream():
```python
def generate_stream(context):
    user_token = context.get_token()
    headers = context.get_headers()
    json_body = context.get_json()

    for x in ["Hello", "WatsonX", "!"]:
        yield x
```

Output

id: 1
event: message
data: Hello

id: 2
event: message
data: WatsonX

id: 3
event: message
data: !

id: 4
event: eos

Guidelines for defining the generate_batch() function
The generate_batch() function can be used for use cases that require batch inferencing. This function handles the REST API call to the jobs endpoint /ml/v4/deployments_jobs.

Follow these guidelines to define the generate_batch() function inside the AI service:

You must use the name generate_batch() to define the function.

Example generate_batch():

```python
def generate_batch(input_data_references: list[dict], output_data_reference: dict):
    # context from outer function is visible
    batch_token = context.generate_token()
    print(f"batch_token: {batch_token[-5:]}", flush=True)
    print(
        f"generate_batch:\n{input_data_references=}\n{output_data_reference=}",
        flush=True,
    )
```

Sample code to create an AI service
The sample code defines an AI service deployable_ai_service_f1. When a REST API request is sent to the /ml/v4/deployments endpoint, deployable_ai_service_f1 is called. The function takes a JSON input payload and includes the following nested functions as part of it's scope:

generate(): Makes a REST API call to the /ml/v4/deployments/{id_or_name}/ai_service endpoint. It takes in a context object, extracts the token, headers, and JSON body, and returns a response based on the mode key in the JSON body. The response format can be JSON, bytes, or string, with optional custom headers.
generate_stream(): Makes a REST API call to the SSE (Server-Sent Events) inference endpoint /ml/v4/deployments/{id_or_name}/ai_service_stream. It takes in a context object, extracts the token, headers, and JSON body, and returns a stream of SSE events that are indicated by eos (End of Stream).
generate_batch(): Makes a REST API call to the jobs endpoint /ml/v4/deployments_jobs. It takes in input_data_references and output_data_reference from the request JSON body, generates a batch token, and logs the input and output data references.

```python
def deployable_ai_service_f1(context, params={"k1": "v1"}, **custom):
    """
    The outer function handles the REST call to the deployment endpoint
    POST /ml/v4/deployments

        context.generate_token() - generate a token from the task credentials

    To use `generate` and `generate_stream`, the deployment has to be ONLINE
    To use `generate_batch`, the deployment has to be BATCH
    """
    task_token = context.generate_token()
    print(f"outer function: {task_token[-5:]}", flush=True)

    def generate(context) -> dict:
        """
        The `generate` function handles the REST call to the inference endpoint
        POST /ml/v4/deployments/{id_or_name}/ai_service

            context.get_token()     - get the Bearer token from the header of the request
            context.get_json()      - get the body of the request
            context.get_headers()   - get the headers of the request

        The generate function should return a dict
        The following optional keys are supported currently
        - body
        - headers

        This particular example accepts a json body of the format:
        { "mode" : <value> }

        Depending on the <value> of the mode, it will return different response

        """
        user_token = context.get_token()
        headers = context.get_headers()
        json_body = context.get_json()
        print(f"my_generate: {user_token=}", flush=True)
        print(f"request headers: {headers=}", flush=True)
        print(f"json body: {json_body=}", flush=True)

        match json_body.get("mode", "no-match"):
            case "json":
                # response Content-Type is "application/json"
                return {
                    "headers": {
                        "Content-Type": "application/json",
                        "User-Defined-Head": "x-genai",
                    },
                    "body": {
                        "user_token": user_token[-5:],
                        "task_token": task_token[-5:],
                        "json_body": json_body,
                        "params": params,
                        "custom": custom,
                    },
                }
            case "json-no-header":
                # response Content-Type is "application/json"
                return {
                    "body": {
                        "user_token": user_token[-5:],
                        "task_token": task_token[-5:],
                        "json_body": json_body,
                        "params": params,
                        "custom": custom,
                    },
                }
            case "json-custom-header":
                # response Content-Type is "text/plain; charset=utf-8; test-2"
                return {
                    "headers": {
                        "Content-Type": "text/plain; charset=utf-8; test-2",
                        "User-Defined-Head": "x-genai",
                    },
                    "body": {
                        "user_token": user_token[-5:],
                        "task_token": task_token[-5:],
                        "json_body": json_body,
                        "params": params,
                        "custom": custom,
                    },
                }
            case "bytes":
                # response Content-Type is "application/octet-stream"
                return {
                    "headers": {
                        "Content-Type": "application/octet-stream",
                        "User-Defined-Head": "x-genai",
                    },
                    "body": b"12345678910",
                }
            case "bytes-no-header":
                # response Content-Type is 'text/html; charset=utf-8'
                return {
                    "body": b"12345678910",
                }
            case "bytes-custom-header":
                # response Content-Type is "text/plain; charset=utf-8; test-2"
                return {
                    "headers": {
                        "Content-Type": "text/plain; charset=utf-8; test-2",
                        "User-Defined-Head": "x-genai",
                    },
                    "body": b"12345678910",
                }
            case "str":
                # response Content-Type is "text/plain"
                return {
                    "headers": {
                        "Content-Type": "text/plain",
                        "User-Defined-Head": "x-genai",
                    },
                    "body": f"Hello WatsonX: {json_body}",
                }
            case "str-no-header":
                # response Content-Type is "text/html; charset=utf-8"
                return {
                    "body": f"Hello WatsonX: {json_body}",
                }
            case "str-custom-header":
                # response Content-Type is "application/octet-stream; charset=utf-8; test-2"
                return {
                    "headers": {
                        "Content-Type": "application/octet-stream; charset=utf-8; test-2",
                        "User-Defined-Head": "x-genai",
                    },
                    "body": f"Hello WatsonX: {json_body}",
                }
            case "negative-str-return":
                # Bad request
                return "Should give 400 bad request"
            case _:
                # response Content-Type is "text/html; charset=utf-8"
                return {"body": "No match"}

    def generate_stream(context):
        """
        The generate_stream function handles the REST call to the SSE inference endpoint
        POST /ml/v4/deployments/{id_or_name}/ai_service_stream

            context.get_token()     - get the Bearer token from the header of the request
            context.get_json()      - get the body of the request
            context.get_headers()   - get the headers of the request

        The generate_stream function be a python `generator` with yield
        The data in yield will the "data" for the SSE event

        Example: The following request json
            { "sse": ["Hello" , "", "WatsonX"," ", "!"]}
        will return the following stream of events
            --------------
            id: 1
            event: message
            data: Hello

            id: 2
            event: message
            data:

            id: 3
            event: message
            data: WatsonX

            id: 4
            event: message
            data:

            id: 5
            event: message
            data: !

            id: 6
            event: eos
            ---------------
        The end of the stream will be marked by the event "eos"

        """
        user_token = context.get_token()
        headers = context.get_headers()
        json_body = context.get_json()
        print(f"generate_stream: {user_token=}", flush=True)
        print(f"generate_stream: {headers=}", flush=True)
        print(f"generate_stream: {json_body=}", flush=True)

        import time
        for x in json_body.get("sse", ["default", "message"]):
            time.sleep(1)
            yield x

    def generate_batch(input_data_references: list[dict], output_data_reference: dict) -> None:
        """
        The generate_batch function handles the REST jobs endpoint
        POST /ml/v4/deployments_jobs

            Arguments to the function are from the json body of the request to jobs
            - input_data_references : scoring.input_data_references
            - output_data_reference : scoring.output_data_reference

        context.generate_token() : can access context object
        from outer function scope if token is required
        """
        batch_token = context.generate_token()
        print(f"batch_token: {batch_token[-5:]}", flush=True)
        print(
            f"generate_batch:\n{input_data_references=}\n{output_data_reference=}",
            flush=True,
        )

    return generate, generate_stream, generate_batch
```

Testing AI services
After you create your AI service, you can test the coding logic of your AI service by using the watsonx.ai Python client library.

Testing AI services with Python client library
To test the logic of your AI service locally by using the RuntimeContext class of the watsonx.ai Python client library, follow these steps:

Use the RuntimeContext class of the Python client library to test your AI service locally:

```python
from ibm_watsonx_ai.deployments import RuntimeContext

context = RuntimeContext(
    api_client=client, request_payload_json={}
)

# custom is optional argument which is specified during the time of creation of deployment
custom_object = {"space_id": space_id}

generate, generate_stream, generate_batch = basic_generate_demo(context, **custom_object)
```


For more information, see watsonx.ai Python client library documentation for using RuntimeContext for AI services.

Depending on your use case, you can test the generate(), generate_stream(), or generate_batch() functions as follows:

To test the generate() function:

```python
context.request_payload_json = { "test": "ai_service inference payload"}
print(generate(context))

```
To test the generate_stream() function:

```python
context.request_payload_json = {"sse": ["ai_service_stream", "inference", "test"]}
for data in generate_stream(context):
    print(data)
```

To test the generate_batch() function:

```python
input_data_references = [
    {
        "type": "connection_asset",
        "connection": {"id": "2d07a6b4-8fa9-43ab-91c8-befcd9dab8d2"},
        "location": {
            "bucket": "wml-v4-fvt-batch-pytorch-connection-input",
            "file_name": "testing-123",
        },
    }
]
output_data_reference = {
    "type": "data_asset",
    "location": {"name": "nb-pytorch_output.zip"},
}

generate_batch(input_data_references, output_data_reference)
```


Creating AI service assets
To deploy an AI service, you must create a repository asset in watsonx.ai Runtime that contains the AI service and upload the Python file to the asset.

Requirements for creating AI service assets
When you use an integrated development environment (IDE) such as VSCode, Eclipse, PyCharm, or more to build your generative AI application, you must create a Python file to store your AI service. After you define the function, you must compress the AI service to create a gzip archive (.gz file format).

When you use the watsonx.ai Python client library to create your AI service asset, the library automatically stores the function in gzip archive for you. However, when you create an AI service asset by using the REST API, you must follow the process of manually compressing your Python file in a gzip archive.

You must use the runtime-25.1-py3.12 or runtime-24.1-py3.11 software specification to create and deploy an AI service asset that is coded in Python.

Creating AI service assets with Python client library
You can use the store_ai_service function of the watsonx.ai Python client library to create an AI service asset.

The following code sample shows how to create an AI service asset by using the Python client library:

```python
documentation_request = {
    "application/json": {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "parameters": {
                "properties": {
                    "max_new_tokens": {"type": "integer"},
                    "top_p": {"type": "number"},
                },
                "required": ["max_new_tokens", "top_p"],
            },
        },
        "required": ["query"],
    }
}

documentation_response = {
    "application/json": {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": {"query": {"type": "string"}, "result": {"type": "string"}},
        "required": ["query", "result"],
    }
}


meta_props = {
    client.repository.AIServiceMetaNames.NAME: "AI service example",
    client.repository.AIServiceMetaNames.DESCRIPTION: "This is AI service function",
    client.repository.AIServiceMetaNames.SOFTWARE_SPEC_ID: client.software_specifications.get_id_by_name(
        "runtime-25.1-py3.12"
    ),
    client.repository.AIServiceMetaNames.REQUEST_DOCUMENTATION: documentation_request,
    client.repository.AIServiceMetaNames.RESPONSE_DOCUMENTATION: documentation_response,
}

stored_ai_service_details = client.repository.store_ai_service(
    basic_generate_demo, meta_props
)

ai_service_id = client.repository.get_ai_service_id(stored_ai_service_details)
print("The AI service asset id:", ai_service_id)

```


Note:
The REQUEST_DOCUMENTATION and RESPONSE_DOCUMENTATION parameters are optional. You can use these parameters to store the schema of the request and response of generate and generate_stream functions.
The function call client.repository.store_ai_service saves the AI service function basic_generate_demo into a gzip file internally.
For more information, see watsonx.ai Python client library documentation for creating an AI service asset.

Creating an AI service asset with REST API
You can use the /ml/v4/ai_services REST API endpoint to create the AI services asset in the watsonx.ai Runtime repository. For more information, see watsonx.ai REST API documentation.

Deploying AI service assets
Depending on your use case, you can create an online or a batch deployment for your AI services asset from your deployment space. Deploy your AI service programmatically by using the watsonx.ai REST API, or Python client library.

Types of deployments for AI service
Depending on your use case, you can deploy the AI service asset as an online or a batch deployment. Choose the deployment type based on the functions used in the AI service.

You must create an online deployment for your AI service asset for online scoring (AI service contains the generate() function) or streaming applications (AI service contains the generate_stream() function).
You must create a batch deployment for your AI service asset for batch scoring applications (AI service contains the generate_batch() function).
Prerequisites
You must set up your task credentials for deploying your AI services. For more information, see Adding task credentials.
You must promote your AI services asset to your deployment space.
Deploying AI services with Python client library
You can create an online or a batch deployment for your AI service asset by using the Python client library.

Creating online deployment
The following example shows how to create an online deployment for your AI service by using the watsonx.ai Python client library:

```python
deployment_details = client.deployments.create(
    artifact_id=ai_service_id,
    meta_props={
        client.deployments.ConfigurationMetaNames.NAME: "ai-service - online test",
        client.deployments.ConfigurationMetaNames.ONLINE: {},
        client.deployments.ConfigurationMetaNames.HARDWARE_SPEC: {
            "id": client.hardware_specifications.get_id_by_name("XS")
        },
    },
)
deployment_id = client.deployments.get_uid(deployment_details)
print("The deployment id:", deployment_id)
```

Creating batch deployment
The following example shows how to create a batch deployment for your AI service by using the watsonx.ai Python client library:

```python
deployment_details = client.deployments.create(
    artifact_id=ai_service_id,
    meta_props={
        client.deployments.ConfigurationMetaNames.NAME: f"ai-service - batch",
        client.deployments.ConfigurationMetaNames.BATCH: {},
        client.deployments.ConfigurationMetaNames.HARDWARE_SPEC: {
            "id": client.hardware_specifications.get_id_by_name("XS")
        },
    },
)
deployment_id = client.deployments.get_uid(deployment_details)
print("The batch deployment id:", deployment_id)

Deploying AI services with REST API
You can use the /ml/v4/deployments watsonx.ai REST API endpoint to create an online or a batch deployment for your AI service asset.

Creating online deployment
The following example shows how to create an online deployment for your AI service by using the REST API:

# POST /ml/v4/deployments
response = requests.post(
    f'{HOST}/ml/v4/deployments?version={VERSION}',
    headers=headers,
    verify=False,
    json={
        "space_id": space_id,
        "name": "genai flow online",
        "custom": {
            "key1": "value1",
            "key2": "value2",
            "model": "meta-llama/llama-3-8b-instruct"
        },
        "asset": {
            "id": asset_id
        },
        "online": {}
    }
)
```


Creating batch deployment
The following example shows how to create a batch deployment for your AI service by using the REST API:

```python
response = requests.post(
    f'{HOST}/ml/v4/deployments?version={VERSION}',
    headers=headers,
    verify=False,
    json={
        "hardware_spec": {
          "id": "........",
          "num_nodes": 1
        },
        "space_id": space_id,
        "name": "ai service batch dep",
        "custom": {
            "key1": "value1",
            "key2": "value2",
            "model": "meta-llama/llama-3-8b-instruct"
        },
        "asset": {
            "id": asset_id
        },
        "batch": {}
    }
)
print(f'POST {HOST}/ml/v4/deployments?version={VERSION}', response.status_code)
print(json.dumps(response.json(), indent=2))

dep_id = response.json()["metadata"]["id"]

print(f"{dep_id=}")
```