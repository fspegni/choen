#!/bin/bash

export PYTHONPATH=`pwd`/src:$PYTHONPATH
export DJANGO_SETTINGS_MODULE=bpmn2solidity.settings
django-admin test bpmn_parser
