import nfa
from contracts import Constructor, Contract, Function, Variable, Event, SmartContract

class Generator:

    def createContract(self):
        raise Exception("This is an abstract method, you should implement it")

class NFAContractGenerator(Generator): 
    
    def __init__(self, n : nfa.NFA):
        assert n is not None, f"Expected not-null nfa to build a contract"
        self._nfa : nfa.NFA = n
        
    @property
    def nfa(self) -> nfa.NFA:
        return self._nfa
    
    def __create_attributes(self, contract : Contract):
        contract.add_attribute(Variable("states","string[]","",list(map(lambda s: s.id, self.nfa.states))))
        contract.add_attribute(Variable("tmpStates","string[]"))
        contract.add_attribute(Variable("initialState", "string","",'"'+str(self.nfa.initial.id)+'"'))
        contract.add_attribute(Variable("finalStates", "string[]","",list(map(lambda f: f.id, self.nfa.final))))
        contract.add_attribute(Variable("currentStates", "string[]"))
        contract.add_attribute(Variable("message", "string[]"))
        contract.add_attribute(Variable("epsilon","string"))
        contract.add_attribute(Variable("start","bool"))
        contract.add_attribute(Variable("end","bool"))
        contract.add_attribute(Variable("transitions", "mapping(string => mapping(string => string[]))"))
    
    def __create_constructor(self, contract : Contract):
        constructorBody = ""
        transitionsDict = {}
        for t in self.nfa.transitions:
            if f"{t.source.id}.{t.label}" not in transitionsDict.keys():
                transitionsDict[f"{t.source.id}.{t.label}"] = [t.target.id]
            else:
                transitionsDict[f"{t.source.id}.{t.label}"].append(str(t.target.id))
        
        for key in transitionsDict:
            key = key.split(".")
            constructorBody += f"transitions['{key[0]}']['{key[1]}'] = {transitionsDict[key[0]+'.'+key[1]]};\n"  
        constructorBody += """
delete tmpStates;
tmpStates.push(initialState);
currentStates = e_closure(tmpStates);"""

        contract.add_constructor(Constructor([], constructorBody))

    def __create_functions(self, contract : Contract):
        contract.add_function(Function("strCompare",
                                [Variable("stringA", "string", "memory"), Variable("stringB", "string", "memory")],
                                "return keccak256(abi.encodePacked(stringA)) == keccak256(abi.encodePacked(stringB));",
                                "private",
                                "bool"))

        contract.add_function(Function("contains",
                        [Variable("s","string","memory"), Variable("states","string[]","memory")],
                        """for (uint i = 0; i < states.length; i++) {
    if (strCompare(s,states[i])) {
        return true;
    }
}
return false;""",
                        "private",
                        "bool"))

        contract.add_function(Function("checkInitialAndFinalStates",
                        [Variable("states", "string[]","memory")],
                        """start = false;
end = false;
for (uint i = 0; i < states.length; i++) {
    if (strCompare(states[i],initialState)) {
            start = true;
        }
        for (uint k = 0; k < finalStates.length; k++) {
            if (strCompare(states[i],finalStates[k])) {
                end = true;
           }
        }
    }""",
                        "private",))

        contract.add_function(Function("union",
                        [Variable("arrayA","string[]","memory"),Variable("arrayB","string[]","memory")],
                        """delete tmpStates;
tmpStates = arrayA;
for (uint i = 0; i < arrayB.length; i++) {
    if(!contains(arrayB[i], tmpStates)) {
        tmpStates.push(arrayB[i]);
    }
}
return tmpStates;""",
                        "private",
                        "string[] memory"))

        contract.add_function(Function("e_closure",
                        [Variable("states","string[]","memory")],
                        """delete tmpStates;
tmpStates = states;
bool found = (tmpStates.length > 0);
while (found) {
    found = false;
    for (uint i = 0; i < tmpStates.length; i++) {
        for (uint j = 0; j < transitions[tmpStates[i]][epsilon].length; j++) {
            if (!contains(transitions[tmpStates[i]][epsilon][j], tmpStates)) {
                tmpStates.push(transitions[tmpStates[i]][epsilon][j]);
                found = true;
            }
        }
    }
}
checkInitialAndFinalStates(tmpStates);
return tmpStates;""",
                        "private",
                        "string[] memory"))

        contract.add_function(Function("getStates",
                                [],
                                "return states;",
                                "public view",
                                "string[] memory"))
        
        contract.add_function(Function("getCurrentStates",
                                [],
                                "return currentStates;",
                                "public view",
                                "string[] memory"))
        
        contract.add_function(Function("getFinalStates",
                                [],
                                "return finalStates;",
                                "public view",
                                "string[] memory"))

        contract.add_function(Function("isFinal",
                                [],
                                "return end;",
                                "public view",
                                "bool"))

        contract.add_function(Function("isInitial",
                                [],
                                "return start;",
                                "public view",
                                "bool"))

        contract.add_function(Function("getMessage",
                                [],
                                "return message;",
                                "public view",
                                "string[] memory"))

        contract.add_function(Function("transitionFrom",
                                [Variable("state","string","memory"), Variable("label","string","memory")],
                                "return transitions[state][label];",
                                "public",
                                "string[] memory"))

        contract.add_function(Function("transition",
                                [Variable("label","string","memory")],
                                """delete tmpStates;
for (uint i = 0; i < currentStates.length; i++) {
    string[] memory s = transitionFrom(currentStates[i],label);
    tmpStates = union(tmpStates, s);
}
require(tmpStates.length != 0);
message.push(label);
currentStates = e_closure(tmpStates);""",
                                "public"))
        
        contract.add_function(Function("checkEnabledTransitions",
                        [Variable("symbol","string","memory")],
                        """for (uint i = 0; i < currentStates.length; i++) {
    string[] memory s_reached = transitionFrom(currentStates[i], symbol);
    if (s_reached.length > 0) return true;
    //reached = union(reached, s_reached); 
}
return false;""",
                        "public",
                        "bool"))
    
    def createContract(self):

        contract : Contract = Contract("NFA")

        self.__create_attributes(contract)
        
        self.__create_constructor(contract)
        
        self.__create_functions(contract)
        
        return contract
    

class EnforcerContractGenerator(Generator):

    def __init__(self, nfa : Contract):
        assert nfa is not None, f"Expected not-null nfa contract to build an enforcer"
        self._nfa : Contract = nfa

    @property
    def nfa(self) -> Contract:
        return self._nfa
    

    def __create_directives(self, contract : Contract):
        contract.add_directive("using strings for *")

    def __create_events(self, contract : Contract):
        contract.add_event(Event("outputEvent",[Variable("debug","string"), Variable("messageOut","string")]))

    def __create_attributes(self, contract : Contract):
        contract.add_attribute(Variable("nfa",self.nfa.name))
        contract.add_attribute(Variable("actors","string[]",))
        contract.add_attribute(Variable("messages","string[]"))
        contract.add_attribute(Variable("tmpStates","string[]"))
        contract.add_attribute(Variable("buffer","mapping(string => mapping(string => uint))"))

    def __create_constructor(self, contract : Contract):
        contract.add_constructor(Constructor([Variable("nfaAddress","address")],f"nfa = {self.nfa.name}(nfaAddress);"))
    
    def __create_utils(self, contract : Contract):
        contract.add_function(Function("strCompare",
                                [Variable("stringA","string","memory"),Variable("stringB","string","memory")],
                                "return keccak256(abi.encodePacked(stringA)) == keccak256(abi.encodePacked(stringB));",
                                "internal pure",
                                "bool"))

        contract.add_function(Function("arrContains",
                                [Variable("states","string[]","memory"),Variable("s","string","memory")],
                                """for (uint i = 0; i < states.length; i++) {
    if (strCompare(s,states[i])) {
        return true;
    }
}
return false;""",
                                "internal pure",
                                "bool"))

        contract.add_function(Function("contains",
                                [Variable("what","string","memory"),Variable("where","string","memory")],
                                """strings.slice memory where = where.toSlice();
strings.slice memory what = what.toSlice();
return where.contains(what);""",
                                "internal pure",
                                "bool"))

        contract.add_function(Function("split",
                                [Variable("sequence","string","memory"),Variable("del","string","memory")],
                                """strings.slice memory s = sequence.toSlice();
strings.slice memory delim = del.toSlice();
string[] memory parts = new string[](s.count(delim) + 1);
for(uint i = 0; i < parts.length; i++) {
    parts[i] = s.split(delim).toString();
}
return parts;""",
                                "private",
                                "string[] memory"))
        
        contract.add_function(Function("union",
                                [Variable("arrayA","string[]","memory"),Variable("arrayB","string[]","memory")],
                                """delete tmpStates;
for (uint i = 0; i < arrayB.length; i++) {
    tmpStates.push(arrayB[i]);
}
for (uint i = 0; i < arrayA.length; i++) {
    if(!arrContains(tmpStates, arrayA[i])) {
        tmpStates.push(arrayA[i]);
    }
}
return tmpStates;""",
                                "private",
                                "string[] memory"))

        contract.add_function(Function("buffer_add",
                                [Variable("actor","string","memory"),Variable("message","string","memory")],
                                """uint counter = buffer[actor][message];
counter += 1;
if (!arrContains(actors,actor)) {
    actors.push(actor);
}
if(!arrContains(messages,message)) {
    messages.push(message);
}
buffer[actor][message] = counter;""",
                                "private"))

        contract.add_function(Function("buffer_remove",
                                [Variable("actor","string","memory"),Variable("message","string","memory")],
                                """uint counter = buffer[actor][message];
require(counter > 0, string(abi.encodePacked("No message ", message, " to remove for actor ", actor)));
counter -= 1;
buffer[actor][message] = counter;""",
                                "private"))

    def __create_conditions(self, contract : Contract):
        contract.add_function(Function("condition_rule_send",
                                [Variable("message","string","memory")],
                                """return contains("!", message);""",
                                "private",
                                "bool"))
                
        contract.add_function(Function("condition_rule_receive_now",
                                [Variable("message","string","memory")],
                                """return contains("?", message) && nfa.checkEnabledTransitions(message);""",
                                "private",
                                "bool"))

        contract.add_function(Function("condition_rule_receive_delayed",
                                [Variable("message","string","memory")],
                                """return contains("?", message);""",
                                "private",
                                "bool"))

        contract.add_function(Function("condition_rule_receive_buffered",
                                [],
                                """delete tmpStates;
for (uint i = 0; i < actors.length; i++) {
    for (uint j = 0; j < messages.length; j++) {
        if (buffer[actors[i]][messages[j]] > 0) {
            string memory message = string(abi.encodePacked(actors[i],"?",messages[j]));
            string[] memory currentStates = nfa.getCurrentStates();
            for (uint s = 0; s < currentStates.length; s++) {
                tmpStates = nfa.transitionFrom(currentStates[s], message);
                if (tmpStates.length > 0) {
                    return message;
                }
            }
        }
    }
}
return "None";""",
                                "private",
                                "string memory"))

    def __create_rules(self, contract : Contract):
        contract.add_function(Function("rule_send",
                                [Variable("message","string","memory")],
                                "return message;",
                                "private",
                                "string memory"))
        
        contract.add_function(Function("rule_receive_now",
                                [Variable("message","string","memory")],
                                """nfa.transition(message);
return message;""",
                                "private",
                                "string memory"))

        contract.add_function(Function("rule_receive_delayed",
                                [Variable("actor","string","memory"),Variable("message","string","memory")],
                                """buffer_add(actor, message);
return "";""",
                                "private",
                                "string memory"))

        contract.add_function(Function("rule_receive_buffered",
                                [Variable("actor","string","memory"),Variable("message","string","memory")],
                                """nfa.transition(string(abi.encodePacked(actor,"?",message)));
buffer_remove(actor, message);
return string(abi.encodePacked(actor,"?",message));""",
                                "private",
                                "string memory"))
        
    def __create_getters(self, contract : Contract):
        contract.add_function(Function("getActors",
                                [],
                                "return actors;",
                                "public view",
                                "string[] memory"))
        
        contract.add_function(Function("getMessages",
                                [],
                                "return messages;",
                                "public view",
                                "string[] memory"))

        contract.add_function(Function("get_buffer_item",
                                [Variable("actor", "string", "memory"), Variable("message", "string", "memory")],
                                "return buffer[actor][message];",
                                "public view",
                                "uint"))

    def __create_processors(self, contract : Contract):
        contract.add_function(Function("process_input",
                                [Variable("event_input","string","memory")],
                                """string memory out;
string memory debug;
if (condition_rule_send(event_input)) {
    debug = string(abi.encodePacked("(* Condition rule receive send: ", event_input, " *)"));
    out = rule_send(event_input);
} else if (condition_rule_receive_now(event_input)) {
    string memory actor = split(event_input, "?")[0];
    string memory message = split(event_input, "?")[1];
    debug = string(abi.encodePacked("(* Condition rule receive now: ", event_input, " *)"));
    out = rule_receive_now(event_input);
    } else if (condition_rule_receive_delayed(event_input)) {
        string memory actor = split(event_input, "?")[0];
        string memory message = split(event_input, "?")[1];
        debug = string(abi.encodePacked("(* Condition rule receive delayed: ", event_input, " *)"));
        out = rule_receive_delayed(actor, message);
    } else {
        debug = "No matching condition";
        out = "None";
    }
emit outputEvent(debug, out);
return out;""",
                                "public",
                                "string memory"))

        contract.add_function(Function("process_check",
                                [],
                                """string memory out = "";
string memory debug;
string memory message = condition_rule_receive_buffered();
if(!strCompare(message,"None")) {
    string memory actor = split(message, "?")[0];
    string memory action = split(message, "?")[1];
    debug = string(abi.encodePacked("(* Condition rule receive buffered: ", message, " *)"));
    out = rule_receive_buffered(actor, action);            
} else {
            out = "None";
            debug = "(* No usable message found in buffer for current states. *)";
        }
emit outputEvent(debug, out);
return out;""",
                                "public",
                                "string memory"))



    def createContract(self):
        contract : Contract = Contract("Enforcer")

        self.__create_directives(contract)
        self.__create_events(contract)
        self.__create_attributes(contract)
        self.__create_constructor(contract)

        #Functions
        self.__create_utils(contract)
        self.__create_conditions(contract)
        self.__create_rules(contract)
        self.__create_getters(contract)
        self.__create_processors(contract)

        return contract
    
class SmartContractGenerator:
    
    def __init__(self, nfa : nfa.NFA):
        assert nfa is not None, f"Expected not-null nfa to build a contract"
        self._nfa = nfa
        self._contract : SmartContract = SmartContract("0.7.6")

    @property
    def nfa(self):
        return self._nfa

    @property
    def contract(self):
        return self._contract

    def createSmartContract(self):
        
        #Library
        #strings: String & slice utility library for Solidity contracts.
        self.contract.add_library("strings", "https://raw.githubusercontent.com/Arachnid/solidity-stringutils/master/src/strings.sol")

        #Contracts    
        nfaContract = NFAContractGenerator(self.nfa).createContract()
        
        self.contract.add_contract(nfaContract)
        self.contract.add_contract(EnforcerContractGenerator(nfaContract).createContract())
        return self.contract
