def transfer_files_cos_to_cos():
    import ibm_boto3
    from ibm_botocore.client import Config
    import json
    import os
    import io

    def score(
        payload,
    ):
        """
        WatsonX.ai deployable function to transfer files from one COS instance to another.

        Expected simplified format:
        [
        {
            "source_cos_config": {
                "bucket_name": "source_bucket",
                "aws_access_key": "hmac_access_key",
                "aws_secret_access_key": "hmac_secret_access_key",
                "endpoint_url": "https://s3.eu-de.cloud-object-storage.appdomain.cloud"
            },
            "target_cos_config": {
                "bucket_name": "target_bucket",
                "aws_access_key": "hmac_access_key",
                "aws_secret_access_key": "hmac_secret_access_key",
                "endpoint_url": "https://s3.eu-de.cloud-object-storage.appdomain.cloud"
            },
            "source_objects": ["path/to/file1.pdf", "path/to/file2.csv"],
            "source_prefix": "",
            "target_prefix": "my/target/prefix",
        }
        ]

        If source_objects is empty or omitted, all objects in the source bucket
        (optionally filtered by source_prefix) will be transferred.

        Which you can run through this kind of helper function:
        ### --- --- ---

        def reformat_for_wxai_scoring(input_data):
            '''Converts input data to WatsonX.ai scoring payload format.'''
            # Convert single dict to list
            inputs = [input_data] if isinstance(input_data, dict) else input_data

            if not inputs:
                return {"input_data": [{"fields": [], "values": [[]]}]}

            # Extract fields from first object
            fields = list(inputs[0].keys())

            # Build values array
            values = [[obj.get(field, None) for field in fields] for obj in inputs]

            return {"input_data": [{"fields": fields, "values": values}]}

        ### --- --- ---
        """
        try:
            # Extract the actual payload from input_data format
            fields = payload["input_data"][0]["fields"]
            values = payload["input_data"][0]["values"][0]

            # Create a dictionary from fields and values
            params = dict(zip(fields, values))

            # Extract COS configurations
            source_cos_config = params.get("source_cos_config", {})
            target_cos_config = params.get("target_cos_config", {})

            # Verify all required config values are present
            required_configs = [
                "bucket_name",
                "aws_access_key",
                "aws_secret_access_key",
                "endpoint_url",
            ]
            missing_source = [
                k
                for k in required_configs
                if k not in source_cos_config or not source_cos_config[k]
            ]
            missing_target = [
                k
                for k in required_configs
                if k not in target_cos_config or not target_cos_config[k]
            ]
            if missing_source or missing_target:
                msgs = []
                if missing_source:
                    msgs.append(
                        f"source_cos_config missing: {', '.join(missing_source)}"
                    )
                if missing_target:
                    msgs.append(
                        f"target_cos_config missing: {', '.join(missing_target)}"
                    )
                return {
                    "predictions": [
                        {
                            "fields": ["status", "message"],
                            "values": [["error", "; ".join(msgs)]],
                        }
                    ]
                }

            # Get function parameters
            source_objects = params.get("source_objects", [])
            if isinstance(source_objects, str):
                source_objects = [source_objects]

            source_prefix = params.get("source_prefix", "")
            target_prefix = params.get("target_prefix", "")

            # Initialize source COS client
            source_client = ibm_boto3.client(
                "s3",
                aws_access_key_id=source_cos_config["aws_access_key"],
                aws_secret_access_key=source_cos_config["aws_secret_access_key"],
                config=Config(max_pool_connections=100),
                endpoint_url=source_cos_config["endpoint_url"],
            )

            # Initialize target COS client
            target_client = ibm_boto3.client(
                "s3",
                aws_access_key_id=target_cos_config["aws_access_key"],
                aws_secret_access_key=target_cos_config["aws_secret_access_key"],
                config=Config(max_pool_connections=100),
                endpoint_url=target_cos_config["endpoint_url"],
            )

            # Normalize prefixes
            if source_prefix:
                source_prefix = source_prefix.strip("/")
                if source_prefix:
                    source_prefix = f"{source_prefix}/"
            if target_prefix:
                target_prefix = target_prefix.strip("/")
                if target_prefix:
                    target_prefix = f"{target_prefix}/"

            # If no source_objects specified, list all objects in the source bucket
            if not source_objects:
                list_kwargs = {"Bucket": source_cos_config["bucket_name"]}
                if source_prefix:
                    list_kwargs["Prefix"] = source_prefix
                source_objects = []
                while True:
                    response = source_client.list_objects_v2(**list_kwargs)
                    for obj in response.get("Contents", []):
                        key = obj["Key"]
                        # Strip source_prefix so loop logic re-adds it consistently
                        if source_prefix and key.startswith(source_prefix):
                            key = key[len(source_prefix) :]
                        if key:  # skip if key was exactly the prefix (folder marker)
                            source_objects.append(key)
                    if response.get("IsTruncated"):
                        list_kwargs["ContinuationToken"] = response[
                            "NextContinuationToken"
                        ]
                    else:
                        break

                if not source_objects:
                    return {
                        "predictions": [
                            {
                                "fields": ["status", "message"],
                                "values": [
                                    ["error", "No objects found in source bucket"]
                                ],
                            }
                        ]
                    }

            # Track results for each object
            results = []
            errors = []

            for obj_key in source_objects:
                try:
                    # Build full source key
                    full_source_key = (
                        f"{source_prefix}{obj_key}" if source_prefix else obj_key
                    )

                    # Preserve the same path structure in the target
                    target_key = (
                        f"{target_prefix}{obj_key}" if target_prefix else obj_key
                    )

                    # Download from source COS into memory
                    file_buffer = io.BytesIO()
                    source_client.download_fileobj(
                        source_cos_config["bucket_name"], full_source_key, file_buffer
                    )
                    file_buffer.seek(0)

                    # Upload to target COS
                    conf = ibm_boto3.s3.transfer.TransferConfig(
                        multipart_threshold=1024**2,
                        max_concurrency=100,  # 1MB
                    )
                    target_client.upload_fileobj(
                        file_buffer,
                        target_cos_config["bucket_name"],
                        target_key,
                        Config=conf,
                    )

                    results.append(
                        {
                            "source_bucket": source_cos_config["bucket_name"],
                            "source_key": full_source_key,
                            "target_bucket": target_cos_config["bucket_name"],
                            "target_key": target_key,
                            "status": "success",
                        }
                    )

                except Exception as e:
                    errors.append({"source_key": obj_key, "error": str(e)})

            # Prepare response in watsonx.ai format
            response_data = {
                "successful_uploads": results,
                "failed_uploads": errors,
                "total_processed": len(source_objects),
                "successful_count": len(results),
                "failed_count": len(errors),
            }

            return {
                "predictions": [
                    {
                        "fields": ["status", "data"],
                        "values": [["success" if results else "error", response_data]],
                    }
                ]
            }

        except Exception as e:
            return {
                "predictions": [
                    {
                        "fields": ["status", "message"],
                        "values": [["error", f"Error processing request: {str(e)}"]],
                    }
                ]
            }

    return score


score = transfer_files_cos_to_cos()
