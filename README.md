# Executing the enforcer

1. create a virtualenv (see the Developing -> Linux/Ubuntu without VSCode)
1. execute the following commands:
```
$ workon <your_virtual_env>
$ django-admin shell
>> solcx.solc_install('0.7.6')
```
3. execute the following commands:
```
$ django-admin cli
```
A prompt appears. At this stage you can execute the following commands (each followed by a return):
```
init
load <diagram_name>
start
```
NOTE: The first time, before the command init, you have to execute the following command, to create the tables in the database:
```
migrate
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

# Test the creation of the smart contract
For testing the creation of the smart contract from a choreography you can launch the test with the command:
```
$ ./test.sh
```
and automatically a folder "contracts" is created. It contains the smart contracts and a file "\<SmartContractName\>_combined.json" with the abi and the runtime of the contract generated.

Now you can manually test the smart contract functionalities using RemixIDE (https://remix.ethereum.org/). Once you've opened the IDE you have to load the contract within your workspace. In this case, you can choose either to use the default workspace or to create a new one (this is recommended). From the menu on the left click on "Deploy & run transactions" and you can choose an environment, for example, Remix VM (Berlin). Finally, click on "Deploy" and the deployed smart contract appears in the bottom section, where you can test the different functionalities of the contract.







