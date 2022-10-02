This repository contains a blockchain-based application for the runtime enforcement of a BPMN choreography.

# Preliminaries

## Linux/Ubuntu without VSCode

In order to test the current status of the project, follow a guide for creating a virtualenv (e.g. [see this](https://www.freecodecamp.org/news/virtualenv-with-virtualenvwrapper-on-ubuntu-18-04/)). Next, do the following:

1. export DJANGO_SETTINGS_MODULE=bpmn2solidity.settings
1. export PYTHONPATH=/home/<USER>/git/bpmn2solidity/code:$PYTHONPATH
1. <!-- django-admin test bpmn_parser -->

## Windows or Linux with VSCode

1. follow this guide: https://code.visualstudio.com/docs/python

# Running the automated tests

If you want to use the terminal, after having configured your virtualenv (see Developing -> Linux/Ubuntu without VSCode) do the following:

```
$ workon <your_virtual_env>
$ django-admin test bpmn_parser
```

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
A prompt appears and the commands you can use are listed in the following table.

| Command | Description |
| ---------- | ----------- |
| `help` | Return the list of available commands |
| `init` | Initialize  the application loading the BPMN choreographies. |
| `init -clean` | Initialize  the application by first deleting the BPMN choreographies and then loading them again. This command is useful when a BPMN choreography diagram is updated and loaded again in the directory of the application. |
| `load <diagram_name>` | Load the BPMN choreography diagram using the <diagram_name> specified in input |
| `start` | Start the enforcer. Before running this command check the type of Engine you have chosen. It's crucial for the rest of the application. |
| `dump status` | Retrieve the status of the NFA associated to the BPMN choreography |
| `dump curr_states` | Retrieve the current status of the NFA associated to the BPMN choreography |
| `dump transitions` | Retrieve the transitions of the NFA associated to the BPMn choreography |
| `dump buffer` | Retrieve the events in the enforcer buffer |
| `stats` | Return a table with the transaction statistics |
| `history` | Return the list of all transactions with the states of the NFA and of the buffer after each of them |


At this stage you can execute the following commands (each followed by a return)[^bignote]:
```
>> init
>> load <diagram_name>
>> start
```
[^bignote]: NOTE: The first time, before the command init, you have to execute the following command, to create the tables in the database:
    ```
    migrate
    ```

Next you can provide your input to the enforcer and see how it reacts[^1]. To send a stream of events (every event must be separated with a space) you can write it in the CLI, such as the rest of the commands, but without the character "/" as prefix. Every event must have the following sintax:

\<actor\>[!,?]\<message\>

where [!,?] means respectively a send and a receive event.
Once you've send the event, you can see the output directly in the CLI.
[^1]: When the enforcer is started, every CLI commands must have the prefix "/".







<!-- # Test the creation of the smart contract
For testing the creation of the smart contract from a choreography you can launch the test with the command:
```
$ ./test.sh
```
and automatically a folder "contracts" is created. It contains the smart contracts and a file "\<SmartContractName\>_combined.json" with the abi and the runtime of the contract generated.

Now you can manually test the smart contract functionalities using RemixIDE (https://remix.ethereum.org/). Once you've opened the IDE you have to load the contract within your workspace. In this case, you can choose either to use the default workspace or to create a new one (this is recommended). From the menu on the left click on "Deploy & run transactions" and you can choose an environment, for example, Remix VM (Berlin). Finally, click on "Deploy" and the deployed smart contract appears in the bottom section, where you can test the different functionalities of the contract. -->

# 







