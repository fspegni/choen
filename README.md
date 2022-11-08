# Executing the enforcer

1. create a virtualenv (see the Developing -> Linux/Ubuntu without VSCode)
1. execute the following commands:
```
$ workon <your_virtual_env>
$ django-admin cli
```
A prompt appears. At this stage you can execute the following commands (each followed by a return):
```
init
load <diagram_name>
start
```
Next you can provide your input to the enforcer and see how it reacts.

# Developing

## Linux/Ubuntu without VSCode

In order to test the current status of the project, follow a guide for creating a virtualenv (e.g. [see this](https://www.freecodecamp.org/news/virtualenv-with-virtualenvwrapper-on-ubuntu-18-04/)). Next, do the following:

1. export DJANGO_SETTINGS_MODULE=bpmn2solidity.settings
1. export PYTHONPATH=/home/<USER>/git/bpmn2solidity/code:$PYTHONPATH
1. django-admin test bpmn_parser

## Windows or Linux with VSCode

1. follow this guide: https://code.visualstudio.com/docs/python


## Running the automated tests

If you want to use the terminal, after having configured your virtualenv (see Developing -> Linux/Ubuntu without VSCode) do the following:

```
$ workon <your_virtual_env>
$ ./test.sh
```

# Drawing choreographies

At the moment the choreography diagrams are generated using the following online tool:

https://bpt-lab.org/chor-js-demo/
