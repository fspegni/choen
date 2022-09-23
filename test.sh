#!/bin/bash

export PYTHONPATH=`pwd`/code:$PYTHONPATH
export DJANGO_SETTINGS_MODULE=bpmn2solidity.settings
django-admin test bpmn_parser
