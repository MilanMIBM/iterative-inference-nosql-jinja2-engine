Writing deployable Python functions
[Check for Updates here](https://dataplatform.cloud.ibm.com/docs/content/wsj/analyze-data/ml-deploy-py-function-write.html?context=wx&audience=wdp)

Learn how to write a Python function and then store it as an asset that you can use to deploy models.

For a list of general requirements for deployable functions refer to General requirements for deployable functions. For information on what happens during a function deployment, refer to Function deployment process

General requirements for deployable functions
To be deployed successfully, a function must meet these requirements:

The Python function file on import must have the score function object as part of its scope. Refer to Score function requirements
Scoring input payload must meet the requirements that are listed in Scoring input requirements
The output payload expected as output of score must include the schema of the score_response variable for status code 200. Note that the prediction parameter, with an array of JSON objects as its value, is mandatory in the score output.
When you use the Python client to save a Python function that contains a reference to an outer function, only the code in the scope of the outer function (including its nested functions) is saved. Therefore, the code outside the outer function's scope will not be saved and thus will not be available when you deploy the function.
Score function requirements
Two ways to add the score function object exist:
explicitly, by user
implicitly, by the method that is used to save the Python function as an asset in the watsonx.ai Runtime repository
The score function can accept a single JSON input parameter or two parameters: payload and bearer token.
The score function must return a JSON-serializable object (for example: dictionaries or lists).
Scoring input requirements
The scoring input payload must include an array with the name values, as shown in this example schema. The input_data parameter is mandatory in the payload. The input_data parameter can also include additional name-value pairs.

{"input_data": [{
   "values": [["Hello world!"]]
               }]
}

The scoring input payload must be passed as an input parameter value for score. This way you can ensure that the value of the score input parameter is handled accordingly inside the score.

The scoring input payload must match the input requirements for the concerned Python function.

The scoring input payload must include an array that matches the Example input data schema.

Example input data schema
 {"input_data": [{
    "values": [["Hello, world!"]]
                }]
 }

Example Python code (payload and token)
#wml_python_function
def my_deployable_function():

    def score(payload, token):

        message_from_input_payload = payload.get("input_data")[0].get("values")[0][0]
        response_message = "Received message - {0}".format(message_from_input_payload)

        # Score using the pre-defined model
        score_response = {
            'predictions': [{'fields': ['Response_message_field'],
                             'values': [[response_message]]
                            }]
        }
        return score_response

    return score

score = my_deployable_function()



Testing your Python function
Here's how you can test your Python function:

input_data = { "input_data": [{ "fields": [ "message" ],
                                "values": [[ "Hello, world!" ]]
                               }
                              ]
             }
function_result = score( input_data )
print( function_result )

It returns the message "Hello, world!".

Function deployment process
The Python code of your Function asset gets loaded as a Python module by the watsonx.ai Runtime engine by using an import statement. This means that the code will be executed exactly once (when the function is deployed or each time when the corresponding pod gets restarted). The score function that is defined by the Function asset is then called in every prediction request.

Handling deployable functions
Use one of these methods to create a deployable Python function:

Creating deployable functions through REST API
Creating deployable functions through the Python client
Before you begin
You must set up your task credentials by generating an API key. For more information, see Managing task credentials.

Creating deployable functions through REST API
For REST APIs, because the Python function is uploaded directly through a file, the file must already contain the score function. Any one time import that needs to be done to be used later within the score function can be done within the global scope of the file. When this file is deployed as a Python function, the one-time imports available in the global scope get executed during the deployment and later simply reused with every prediction request.

Important:
The function archive must be a .gz file.

Sample score function file:

Score function.py
---------------------
def score(input_data):
    return {'predictions': [{'values': [['Just a test']]}]}

Sample score function with one time imports:

import subprocess
subprocess.check_output('pip install gensim --user', shell=True)
import gensim

def score(input_data):
    return {'predictions': [{'fields': ['gensim_version'], 'values': [[gensim.__version__]]}]}

Creating deployable functions through the Python client
To persist a Python function as an asset, the Python client uses the wml_client.repository.store_function method. You can persist a Python function in two ways:

Through a file that contains the Python function
Through the function object
Persisting a function through a file that contains the Python function
This method is the same as persisting the Python function file through REST APIs (score must be defined in the scope of the Python source file). For details, refer to Creating deployable functions through REST API.

Important:
When you are calling the wml_client.repository.store_function method, pass the file name as the first argument.

Persisting a function through the function object
You can persist Python function objects by creating Python Closures with a nested function named score. The score function is returned by the outer function that is being stored as a function object, when called. This score function must meet the requirements that are listed in General requirements for deployable functions. In this case, any one time imports and initial setup logic must be added in the outer nested function so that they get executed during deployment and get used within the score function. Any recurring logic that is needed during the prediction request must be added within the nested score function.

Sample Python function save by using the Python client:

def my_deployable_function():

    import subprocess
    subprocess.check_output('pip install gensim', shell=True)
    import gensim

    def score(input_data):
        import
        message_from_input_payload = payload.get("input_data")[0].get("values")[0][0]
        response_message = "Received message - {0}".format(message_from_input_payload)

        # Score using the pre-defined model
        score_response = {
            'predictions': [{'fields': ['Response_message_field', 'installed_lib_version'],
                             'values': [[response_message, gensim.__version__]]
                            }]
        }
        return score_response

    return score

function_meta = {
    client.repository.FunctionMetaNames.NAME:"test_function",
    client.repository.FunctionMetaNames.SOFTWARE_SPEC_ID: sw_spec_id
}
func_details = client.repository.store_function(my_deployable_function, function_meta)



In this scenario, the Python function takes up the job of creating a Python file that contains the score function and persisting the function file as an asset in the watsonx.ai Runtime repository:

score = my_deployable_function()