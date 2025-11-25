#!/bin/bash

pip install crhelper -t ./package
cd ./package
zip -r ../request_quota_increase.zip .
cd ..
zip -g request_quota_increase.zip request_quota_increase.py

