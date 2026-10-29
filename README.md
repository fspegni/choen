[![DOI](https://zenodo.org/badge/1439013234.svg)](https://doi.org/10.5281/zenodo.23784785)

This repository contains a blockchain-based Choreography Enforcer. The application takes as input a multiparty session type or a BPMN 2.0 choreography diagram, and synthesize a Solidity smart contract that act as an enforcer of actors trying to implement the choreography in their production processes.

The tool is still a prototype. The current stable version is based on a comand-line interface (CLI) where the user inputs the simulated events and observes whether the enforcer allows such events or not (perhaps they will be delayed, or postponed indefinitely). A REST API interface allows to integrate ChoEn with third party apps.

# Overview

The current release of ChoEn is defined as a micro-service architecture. The main services at the moment are:
- backend
- ganache

The _backend_ implements the CLI as well as the REST API. The backend also hosts the web GUI static files generated using [another project](https://gitlab.com/fspegni/choen-frontend). The _ganache_ service provides a local simulated blockchain, for tests before using a public network such as Sepolia.

# Requirements
* Ubuntu >= 24.04.5 LTS
* Docker >= 28.3.3
* GNU Make >= 4.3

# Quick Start

## Setup

The following commands download/build the images and import some initial data (fixtures) needed to run tests. *NB:* no process in the hosting machine should be listening on port 8000.

```
$ make up
$ make init
```

To test the environment is correctly working, use your browser to access address [http://localhost:8000](http://localhost:8000); a BPMN editor is presented. By visiting [http://localhost:8000/admin](http://localhost:8000/admin) you can visit the control panel of ChoEn, using the following default credentials:
* username : _admin_
* password : _admin_



## Run experiments

```
$ make cli
>> /list_choreographies
>> /load_mpst <name>
>> /load_config <bc_config>
>> /start
+> /random <N>
```

Where:

* `/list_choreographies` : return the list of all MPSTs loaded from the previous `make init` command
* `/load_mpst <name>` : loads a specific MPST; <name> is the name of the test MPST, e.g. 
    * lottery
    * alternating_bit
    * patient_doctor
    * incident_mangement
    * railway_maintenance
    * coffee_machine
* `/load_config <bc_config>` : loads a blockchain configuration; <bc_config> at the moment can be _"ganache"_ (no quotes) because it is the one pre-loaded by the previous `make init` command and uses well-known test addresses and private keys; later it is explained how to connect to Sepolia using your personal (test) credentials
* `/start` : actually synthesizes the smart contracts and deploys them in the chosen blockchain node
* `/random <N>` : executes _N_ random steps among the allowed ones; by default 80% of the times it picks a symbol that is expected at the current state, while 20% of the times picks a MPST action that is not expected at the current state; 


## Configuring Sepolia

In order to configure Sepolia we suggest to follow these steps using online tutorials:
- configure an account on MetaMask
- add Sepolia testnests on MetaMask
- use a Sepolia-faucet to load some Sepolia-ETH and start deploying/transactiong (e.g. [here](https://cloud.google.com/application/web3/faucet/ethereum/sepolia), [here](https://sepolia-faucet.pk910.de/))

# Some details

## Linux/Ubuntu without VSCode

In order to test the current status of the project, follow a guide for creating a virtualenv. In the following we assume that you use the scripts known as `mkvirtualenv` (e.g. [see this](https://www.freecodecamp.org/news/virtualenv-with-virtualenvwrapper-on-ubuntu-18-04/)). Next you have to setup the environment variables 

```
export DJANGO_SETTINGS_MODULE=bpmn2solidity.settings
export PYTHONPATH=${HOME}/git/choen/src:$PYTHONPATH
```

## Windows or Linux with VSCode

You can follow this guide: https://code.visualstudio.com/docs/python . Remember to export the environment variables as described above.

# Using the enforcer

The tool has two prompts:
- `>>` is the **outer** prompt
- `+>` is the **inner** prompt

The *outer* prompt is used to setup the enforcer with operations such as selecting the BPMN choreography to be enforced, synthesize and compile the enforcing smart contract, setup the blockchain parameters and start the enforcer. 

The *inner* prompt is used to input the (simulated) events and observe whether the enforcer returns them immediately (thus allowing their immediate execution) or delays them. A delayed output means that an event is acceptable provided that previous events are observed. An output may even been postponed indefinitely, because the preconditions (i.e. other events) are never observed. Note that since the enforcer is generated from a BPMN choreography, when we speak of events we mean an exchange of messages among the actors of the choreography itself.

The tool starts executing with the outer prompt. The `start` command (see below) switches from the outer prompt to the inner one. When executing in the inner prompt, the `/stop` command (see the `stop`) brings back the tool to the outer command. 

The tool is launched with the following command:
```
(your_venv) $ django-admin cli
```

## Using the outer prompt

Below is the list of commands interpreted by the outer prompt.

| Command | Description |
| ---------- | ----------- |
| `help` | Return the list of available commands |
| `exit` | Exits the tool |
| `quit` | Exits the tool |
| `init` | Initialize  the application loading the BPMN choreographies. |
| `init -clean` | Initialize  the application by first deleting the BPMN choreographies and then loading them again. This command is useful when a BPMN choreography diagram is updated and loaded again in the directory of the application. |
| `clear` | Remove all the BPMN choreographies from the database. |
| `list` | List the BPMN choreographies previously imported in the database. |
| `load <diagram_name|path_of_diagram.bpmn>` | If a diagram with the given name is found in the database, it is loaded by the enforcer. Otherwise, a file at the given path is imported into the database and then loaded by the enforcer |
| `load_instance <id>` | Load the running instance with the provided identifier `<id>` (if it exists) and then switches the tool from the outer prompt to the inner prompt |
| `start` | Start the enforcer. It creates a new running instance and then switches the tool from the outer prompt to the inner one |
| `stop` | Stop the enforcer, preserving the current state that can be queried (using the `dump ...` commands) or saved (using the `save ...` commands). It switches the tool from the inner prompt to the outer prompt |
| `env` | Print a list of "variables" used by the tool internally |
| `env <var>` | Print the value associated to the specified variable |
| `env <var> <value>` | Set a value to the specified variable in the tool environment |
| `dump status` | Retrieve the status of the NFA associated to the BPMN choreography |
| `dump curr_states` | Retrieve the current status of the NFA associated to the BPMN choreography |
| `dump transitions` | Retrieve the transitions of the NFA associated to the BPMn choreography |
| `dump buffer` | Retrieve the events in the enforcer buffer |
| `stats` | Return a table with the transaction statistics |
| `history` | Return the list of all transactions with the states of the NFA and of the buffer after each of them |
| `save nfa <dir> <name> <format>` | Save the NFA used by the enforcer in the file `<name>.<format>`, provided the format is known to the `dot` utility for drawing graphs; the specified directory `<dir>` is used to store temporary files |

The outer prompt saves a history file for remembering the sequence of commands input by the user. The file can be found at the following path: `${HOME}/.choen_cli`.

## Using the inner prompt

The inner prompt accepts a sequence of events as input from the user. An event is the label of a message as defined in the BPMN diagram used to setup the enforcer itself.

If the input starts with the `/` symbol, the rest of the line is interpreted as a command for the outer prompt. In this way, the user can -at any time during the execution of the inner prompt- execute any command of the outer prompt. For instance, in order to stop the enforcer, the user can input `/stop`. In order to dump the transitions allowed by the enforcer, the user can input `/dump transitions`. And so on.

The inner prompt saves a history file for remembering the sequence of commands input by the user. The file can be found at the following path: `${HOME}/.choen_enforcer`.

## On-chain vs Off-chain Enforcer engine

The enforcer can be used either plugging the **off-chain** engine or plugging the **on-chain** engine.

The off-chain engine is a straightforward Python implementation of the enforcer rules. It does not require any special configuration, and can be used in order to test the logic of the enforcer.

The on-chain engine generates two Solidity smart contracts implementing the enforcer rules and a non-deterministic finite automaton at the core of the enforcer on-chain itself. The on-chain engine is also responsible for deploying the smart contracts, provided that the users configured the required parameters of the enforcer. To this aim, the following command displays the enforcer parameters:
```
>> env
ONCHAIN_URL = None
ONCHAIN_CHAIN_ID = None
ONCHAIN_ADDRESS = None
ONCHAIN_PRIVATE_KEY = None
```
If you use a public test (e.g. Sepolia) for testing the on-chain engine, you should configure the enforcer as follows:
```
>> env ONCHAIN_URL <your_blockchain_url>
>> env ONCHAIN_CHAIN_ID <your_chain_id>
>> env ONCHAIN_ADDRESS <your_wallet_address>
>> env ONCHAIN_PRIVATE_KEY <your_private_key>
```
Remember that the commands above (thus your address and private key) are stored in the outer prompt history file (`${HOME}/.choen_cli`).

# Example of use
Starting from the terminal, you can execute the following commands:
```
(your_venv) $ django-admin cli
>> init
>> load <diagram_name>
```

At this stage, if you want to use the on-chain engine, execute the `env ...` commands for configuring the blockchain parameters (see [above](#on-chain-vs-off-chain-enforcer-engine)). 

The next step (for both cases: the on-chain engine, as well as the off-chain engine) is to start the enforcer:
```
>> start
```

Next you can provide your input to the enforcer and see how it reacts. To send a stream of events (every event must be separated with a space) you can write it in the CLI, such as the rest of the commands, but without the character "/" as prefix. Every event must have the following sintax:

- sending a message: `<actor_id>!<message_id>`
- receiving a message: `<actor_id>?<message_id>`

The sequence of events returned by the enforcer represents the sequence in which such events can be executed. Each actor in the choreography is expected to input the event it is ready to execute. If the event is returned back from the enforcer, it means it is allowed to execute it in compliance with the choreography. Otherwise, the actor has to wait if and when the enforcer emits such event back, before actually executing it.

# The WEB GUI

The WEB GUI is available at address [http://localhost:8000](http://localhost:8000) . Through it, it is possible to draw new BPMN choreography diagrams or access the API and Control panel.

# The REST API

The automatically generated documentation of the REST API is available at the following URL: [http://localhost:8000/api](http://localhost:8000/api)`. 

Finally, you can program your application to use the endpoints published by the API (navigate the documentation in order to discover them). 

