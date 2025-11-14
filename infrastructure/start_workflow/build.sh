#!/bin/bash
#bucket=$1
pip install crhelper -t ./package
cd ./package
zip -r ../start_workflow_lambda.zip .
cd ..
zip -g start_workflow_lambda.zip start_workflow_lambda.py
#aws s3 cp start_workflow_lambda.zip s3://"$bucket"/artifacts/start_workflow_lambda.zip

