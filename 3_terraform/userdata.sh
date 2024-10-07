#!/bin/bash
sudo apt-get update -y
sudo apt-get install -y python3-pip
pip3 install flask boto3  # Install your app dependencies
git clone https://github.com/CVTPRN/Szakdolgozat /home/app  # Clone your app
cd /home/ubuntu/app
python3 app.py  # Run your app
