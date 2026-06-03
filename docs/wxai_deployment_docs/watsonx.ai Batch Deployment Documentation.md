Creating watsonx.ai batch deployments
[Check for Updates here](https://dataplatform.cloud.ibm.com/docs/content/wsj/analyze-data/deploy-batch-details.html?context=wx&audience=wdp)

Create a batch deployment to process input data from a file, data connection, or connected data in a storage bucket, and write the output to a selected destination.

Creating a batch deployment
Unlike an online deployment, where data is submitted directly to the endpoint URL for real-time scoring or processing, a batch deployment provides more control over the scoring process. Follow this sequence to create a batch deployment job:

Organize your resources in a deployment space. You can promote or add the deployable asset, and optionally add data files or data connections for scoring the deployment.
When you deploy the asset, such as a machine learning model, you choose Batch as the deployment type.
Create and configure a batch deployment job. You must specify the input data for the deployment, location for writing the output, details for running the job on a schedule or on demand. You can also configure optional settings such as hardware configuration details or options for notification.
Running the job submits the input data to the deployment endpoint, and writes the output to the output file. You can view or download the output from the Assets page of the space after the job completes successfully.
Deployable asset types for batch deployments
You can create batch deployments for these types of assets:

```
Functions:
    Python functions
AI Services:
    AI Service
Models:
    AutoAI models
    Decision Optimization models
    PMML Models
    PyTorch-Onnx models
    Scikit-learn models
    Spark MLlib models
    SPSS Modeler models
    Tensorflow models
    XGBoost models
Scripts:
    Python scripts
```
Ways to create a batch deployment
You can create a batch deployment in one of these ways:

Use a no-code approach to create a batch deployment from a deployment space.
Use code to create a batch deployment programmatically in notebooks.
Creating a batch deployment from the user interface
Follow these steps to create and test a batch deployment.

Before you begin

You must set up your task credentials by generating an API key. For more information, see Managing task credentials.

Creating a batch deployment
Follow these steps to create your batch deployment from a deployment space:

From the Assets tab in your deployment space, click the name of the model that you want to deploy.

Click New deployment.

Choose Batch as the deployment type.

Enter a name and an optional description for your deployment.

Select a hardware specification.

Restriction:
You cannot create or select custom hardware specifications from the user interface in a deployment space. To learn more about ways to create and select a hardware specification, see Managing hardware specifications for deployments.

Click Create. When status changes to Deployed, your deployment is created.

Testing a batch deployment
To test a batch deployment from your deployment space, you must create a batch job to submit data for processing.

To learn more about creating, running, and managing jobs, see Creating jobs in a deployment space.

Retrieving the endpoint for a batch deployment
You must retrieve the endpoint URL to access your batch deployment from your applications. Follow these steps to get the endpoint URL for your batch deployment:

From your deployment space, click the name of your batch deployment.
From the deployment details page, click the name of your batch job.
Note:
If you don't have an existing batch job for your batch deployment, you must create one. For more information, see Creating jobs in a deployment space.

From the batch job details page, you can access the endpoint URL for your batch deployment. Click the copy Copy to clipboard icon icon to copy the endpoint URL to your clipboard.
Retrieve endpoint URL for batch deployment

Accessing batch deployment details
You can view the configuration details such as hardware and software specifications. You can also get the deployment ID, which you can use in API calls from an endpoint.

Follow these steps to review or update the details for your batch deployment:

From the Deployments tab of your space, click a deployment name.
Click the Deployment details tab to access information that is related to your batch deployment.
View batch deployment details

Creating a batch deployment programmatically by using notebooks
You can create a batch deployment programmatically by using:

watsonx.ai Runtime Python client library.
watsonx.ai Runtime REST API.
To access sample notebooks that demonstrate how to create and manage deployments by using watsonx.ai Runtime Python client, see watsonx.ai Runtime Python client samples and examples.

Testing your batch deployment programmatically
To test your batch deployment programmatically, you must create and run a batch job. After the batch-scoring runs successfully, the results are written to a file.

Retrieving the endpoint for a batch deployment programmatically
To retrieve the endpoint URL of your batch deployment from a notebook:

List the deployments by calling the Python client method client.deployments.list().
Find the row with your deployment. The deployment endpoint URL is listed in the url column.

----- ----- -----

Data sources for scoring batch deployments

You can supply input data for a batch deployment job in several ways, including directly uploading a file or providing a link to database tables. The types of allowable input data vary according to the type of deployment job that you are creating.

For supported input types by framework, refer to Batch deployment input details by framework.

Input data can be supplied to a batch job as inline data or data reference.

Available input types for batch deployments by framework and asset type
---
Framework | Batch deployment type

Decision Optimization | Inline and Reference
Python function	| Inline
PyTorch	| Inline and Reference
Tensorflow | Inline and Reference
Scikit-learn | Inline and Reference
Python scripts | Reference
Spark MLlib	| Inline and Reference
SPSS | Inline and Reference
XGBoost	| Inline and Reference
---


Inline data description
Inline type input data for batch processing is specified in the batch deployment job's payload. For example, you can pass a CSV file as the deployment input in the UI or as a value for the scoring.input_data parameter in a notebook. When the batch deployment job is completed, the output is written to the corresponding job's scoring.predictions metadata parameter.

Data reference description
Input and output data of type data reference that is used for batch processing can be stored:

In a remote data source, for example, a cloud storage bucket or an SQL or no-SQL database.
As a local or managed data asset in a deployment space.
Details for data references include:

Data source reference type depends on the asset type. Refer to Data source reference types section in Adding data assets to a deployment space.

For data_asset type, the reference to input data must be specified as a /v2/assets href in the input_data_references.location.href parameter in the deployment job's payload. The data asset that is specified is a reference to a local or a connected data asset. Also, if the batch deployment job's output data must be persisted in a remote data source, the references to output data must be specified as a output_data_reference.location.name parameter in the deployment job's payload.

Any input and output data_asset references must be in the same space ID as the batch deployment.

If the batch deployment job's output data must be persisted in a deployment space as a local asset, output_data_reference.location.name must be specified. When the batch deployment job is completed successfully, the asset with the specified name is created in the space.

Output data can contain information on where in a remote database the data asset is located. In this situation, you can specify whether to append the batch output to the table or truncate the table and update the output data. Use the output_data_references.location.write_mode parameter to specify the values truncate or append.

Specifying truncate as value truncates the table and inserts the batch output data.

Specifying append as value appends the batch output data to the remote database table.
write_mode is applicable only for the output_data_references parameter.
write_mode is applicable only for data assets in remote databases. This parameter is not applicable for a local data assets or assets located in a local cloud storage bucket.

Example data_asset payload
```python
"input_data_references": [{
    "type": "data_asset",
    "connection": {
    },
    "location": {
        "href": "/v2/assets/<asset_id>?space_id=<space_id>"
    }
}]
```

Example connection_asset payload
```python
"input_data_references": [{
    "type": "connection_asset",
    "connection": {
        "id": "<connection_guid>"
    },
    "location": {
        "bucket": "<bucket name>",
        "file_name": "<directory_name>/<file name>"
    }
    # <other wdp-properties supported by runtimes>
}]
```

Structuring the input data
How you structure the input data, also known as the payload, for the batch job depends on the framework for the asset you are deploying.

A .csv input file or other structured data formats must be formatted to match the schema of the asset. List the column names (fields) in the first row and values to be scored in subsequent rows. For example, see the following code snippet:

PassengerId, Pclass, Name, Sex, Age, SibSp, Parch, Ticket, Fare, Cabin, Embarked
1,3,"Braund, Mr. Owen Harris",0,22,1,0,A/5 21171,7.25,,S
4,1,"Winslet, Mr. Leo Brown",1,65,1,0,B/5 200763,7.50,,S

A JSON input file must provide the same information on fields and values, by using this format:

```python
{"input_data":[{
        "fields": [<field1>, <field2>, ...],
        "values": [[<value1>, <value2>, ...]]
}]}
```

For example:

```python
{"input_data":[{
        "fields": ["PassengerId","Pclass","Name","Sex","Age","SibSp","Parch","Ticket","Fare","Cabin","Embarked"],
        "values": [[1,3,"Braund, Mr. Owen Harris",0,22,1,0,"A/5 21171",7.25,null,"S"],
                  [4,1,"Winselt, Mr. Leo Brown",1,65,1,0,"B/5 200763",7.50,null,"S"]]
}]}
```

Preparing a payload that matches the schema of an existing model
Refer to this sample code:

```c++
model_details = client.repository.get_details("<model_id>")  # retrieves details and includes schema
columns_in_schema = []
for i in range(0, len(model_details['entity']['schemas']['input'][0].get('fields'))):
    columns_in_schema.append(model_details['entity']['schemas']['input'][0].get('fields')[i]['name'])

X = X[columns_in_schema] # where X is a pandas dataframe that contains values to be scored
#(...)
scoring_values = X.values.tolist()
array_of_input_fields = X.columns.tolist()
payload_scoring = {"input_data": [{"fields": [array_of_input_fields],"values": scoring_values}]}
```

----- ----- -----

Batch deployment input details for Python functions

Follow these rules when you are specifying input details for batch deployments of Python functions.

Data type summary table:

Data	Description
Type	inline
File formats	N/A

You can deploy Python functions in watsonx.ai Runtime the same way that you can deploy models. Your tools and apps can use the watsonx.ai Python client or REST API to send data to your deployed functions in the same way that they send data to deployed models. Deploying functions gives you the ability to:

Hide details (such as credentials)
Preprocess data before you pass it to models
Handle errors
Include calls to multiple models All of these actions take place within the deployed function, instead of in your application.
Data sources
If you are specifying input/output data references programmatically:

Data source reference type depends on the asset type. Refer to the Data source reference types section in Adding data assets to a deployment space.
Notes:

For cloud storage connections such as Cloud Object Storage, you must configure Access key and Secret key, also known as HMAC credentials.
The environment variables parameter of deployment jobs is not applicable.
Make sure that the output is structured to match the output schema that is described in Execute a synchronous deployment prediction.