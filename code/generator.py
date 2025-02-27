import nfa
from contracts import Constructor, Contract, Function, Variable, Constant, Event, SmartContract

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
    
    def __create_structures(self, contract : Contract):
##
##        contract.add_structure("buffItem", """
##    struct buffItem {
##        string precondition;
##        string target;
##        string knowledge;
##    }
##        """)
##

        pass

    def __create_attributes(self, contract : Contract):

        #contract.add_attribute(Variable("states","string[]","",list(map(lambda s: s.id, self.nfa.states))))
        contract.add_attribute(Variable("tmpStates","string[]"))
        contract.add_attribute(Variable("initialState", "string","",'"'+str(self.nfa.initial.id)+'"'))
        contract.add_attribute(Variable("finalStates", "string[]","",list(map(lambda f: f.id, self.nfa.final))))
        contract.add_attribute(Variable("currentStates", "string[]"))
        #contract.add_attribute(Variable("message", "string[]"))
        #contract.add_attribute(Variable("message", "uint[]"))
        #contract.add_attribute(Variable("epsilon","string"))
        contract.add_attribute(Variable("start","bool"))
        contract.add_attribute(Variable("end","bool"))
        #contract.add_attribute(Variable("transitions", "mapping(string => mapping(string => string[]))"))
        contract.add_attribute(Variable("transitions", "mapping(string => mapping(uint => string[]))"))
        #contract.add_attribute(Variable("transitions", "mapping(string => mapping(string => buffItem[]))")) # TODO restart from here
    
    def __create_constructor(self, contract : Contract):
        #constructorBody = ""
        initTransitionsBody = ""
        transitionsDict = {}
        for t in self.nfa.transitions:

            if f"{t.source.id}.{t.label}" not in transitionsDict.keys():
                transitionsDict[f"{t.source.id}.{t.label}"] = [t.target.id]
            else:
                transitionsDict[f"{t.source.id}.{t.label}"].append(str(t.target.id))
        
        for key in transitionsDict:
            #breakpoint()
            key = key.split(".")
            symbol = key[1].replace("!","__S__").replace("?","__R__") if key[1] else "EPSILON"
            #constructorBody += f"transitions['{key[0]}']['{key[1]}'] = {transitionsDict[key[0]+'.'+key[1]]};\n"  
            #constructorBody += f"transitions['{key[0]}'][{symbol}] = {transitionsDict[key[0]+'.'+key[1]]};\n"  
            initTransitionsBody += f"transitions['{key[0]}'][{symbol}] = {transitionsDict[key[0]+'.'+key[1]]};\n"  

#        constructorBody += """
        constructorBody = """
delete tmpStates;
tmpStates.push(initialState);
currentStates = e_closure(tmpStates);
"""

        contract.add_constructor(Constructor([], constructorBody))
        contract.add_function(Function("initTransitions", [], initTransitionsBody, "public")) # TODO if this should be called from the enforcer (public), find a way to force at most one call; if not call all other functions should be "blocked"

    def __create_functions(self, contract : Contract):


##        contract.add_function(Function("arrContains",
##                                [Variable("s","string","memory"),Variable("newStates","string[]","memory")],
##                                """for (uint i = 0; i < newStates.length; i++) {
##    if (strCompare(s, newStates[i])) {
##        return true;
##    }
##}
##return false;""",
##                                "internal pure",
##                                "bool"))
##

##
## THIS IS DEPRECATED : it seems to overload the function contains(string, string); but at the
## same time we have also arrContains that is defined exactly like this function here; solution: stop using contains(string, string[]) and move every such reference to arrContains(string, string[])
##
##        contract.add_function(Function("contains",
##                        [Variable("s","string","memory"), Variable("states","string[]","memory")],
##                        """for (uint i = 0; i < states.length; i++) {
##    if (strCompare(s,states[i])) {
##        return true;
##    }
##}
##return false;""",
##                        "private",
##                        "bool"))

        contract.add_function(Function("checkInitialAndFinalStates",
                        [Variable("newStates", "string[]","memory")],
                        """start = false;
end = false;
for (uint i = 0; i < newStates.length; i++) {
    if (strCompare(newStates[i],initialState)) {
            start = true;
        }
        for (uint k = 0; k < finalStates.length; k++) {
            if (strCompare(newStates[i],finalStates[k])) {
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
    if(!arrContains(arrayB[i], tmpStates)) {
        tmpStates.push(arrayB[i]);
    }
}
return tmpStates;""",
                        "private",
                        "string[] memory"))

##        contract.add_function(Function("e_closure",
##                        [Variable("newStates","string[]","memory")],
##                        """delete tmpStates;
##tmpStates = newStates;
##bool found = (tmpStates.length > 0);
##while (found) {
##    found = false;
##    for (uint i = 0; i < tmpStates.length; i++) {
##        for (uint j = 0; j < transitions[tmpStates[i]][epsilon].length; j++) {
##            if (!arrContains(transitions[tmpStates[i]][epsilon][j], tmpStates)) {
##                tmpStates.push(transitions[tmpStates[i]][epsilon][j]);
##                found = true;
##            }
##        }
##    }
##}
##checkInitialAndFinalStates(tmpStates);
##return tmpStates;""",
##                        "private",
##                        "string[] memory"))

        contract.add_function(Function("e_closure",
                        [Variable("newStates","string[]","memory")],
                        """delete tmpStates;
tmpStates = newStates;
bool found = (tmpStates.length > 0);
while (found) {
    found = false;
    for (uint i = 0; i < tmpStates.length; i++) {
        for (uint j = 0; j < transitions[tmpStates[i]][EPSILON].length; j++) {
            if (!arrContains(transitions[tmpStates[i]][EPSILON][j], tmpStates)) {
                tmpStates.push(transitions[tmpStates[i]][EPSILON][j]);
                found = true;
            }
        }
    }
}
checkInitialAndFinalStates(tmpStates);
return tmpStates;""",
                        "private",
                        "string[] memory"))




##        contract.add_function(Function("getStates",
##                                [],
##                                "return states;",
##                                "public view",
##                                "string[] memory"))
##        
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

        contract.add_function(Function("isEnded",
                                [],
                                "return end;",
                                "public view",
                                "bool"))

#        contract.add_function(Function("isFinal",
#                                [],
#                                "return end;",
#                                "public view",
#                                "bool"))

        contract.add_function(Function("isFinal",
                                [Variable("curr","string","memory")],
                                """return arrContains(curr, finalStates);""", 
                                "public view",
                                "bool"))
 
#        contract.add_function(Function("isInitial",
#                                [],
#                                "return start;",
#                                "public view",
#                                "bool"))

        contract.add_function(Function("isInitial",
                                [Variable("curr","string","memory")],
##                                """return arrContains(curr, currentStates);""", 
                                """return strCompare(curr, initialState);""",
                                "public view",
                                "bool"))


        contract.add_function(Function("isCurrent",
                                [Variable("curr","string","memory")],
                                """return arrContains(curr, currentStates);""", # TODO
                                "public view",
                                "bool"))

## FS ?!? TODO
##        contract.add_function(Function("getMessage",
##                                [],
##                                "return message;",
##                                "public view",
##                                "string[] memory"))

        contract.add_function(Function("transitionFrom",
                                #[Variable("state","string","memory"), Variable("label","string","memory")],
                                [Variable("state","string","memory"), Variable("label","uint")],
                                "return transitions[state][label];",
                                "public view",
                                "string[] memory"))

        contract.add_function(Function("transition",
                                #[Variable("label","string","memory")],
                                [Variable("label","uint")],
                                """delete tmpStates;
for (uint i = 0; i < currentStates.length; i++) {
    string[] memory s = transitionFrom(currentStates[i],label);
    tmpStates = union(tmpStates, s);
}
require(tmpStates.length != 0);
//message.push(label);
currentStates = e_closure(tmpStates);""",
                                "public")) 
        
        contract.add_function(Function("checkEnabledTransitions",
                        [Variable("symbol","string","memory")],
                        """for (uint i = 0; i < currentStates.length; i++) {
    string[] memory s_reached = transitionFrom(currentStates[i], encodeEvent(symbol));
    if (s_reached.length > 0) return true;
    //reached = union(reached, s_reached); 
}
return false;""",
                        "public view",
                        "bool"))
    
    def createContract(self):

        contract : Contract = Contract("NFA")

        self.__create_structures(contract)
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
    

#    def __create_directives(self, contract : Contract):
#        contract.add_directive("using strings for *")

    def __create_events(self, contract : Contract):
        contract.add_event(Event("outputEvent",[Variable("debug","string"), Variable("messageOut","string")]))

    def __create_attributes(self, contract : Contract):
        contract.add_attribute(Variable("nfa",self.nfa.name))
        contract.add_attribute(Variable("actors","string[]",))
        contract.add_attribute(Variable("messages","string[]"))
        contract.add_attribute(Variable("tmpStates","string[]"))
        contract.add_attribute(Variable("kb","string[]"))
        contract.add_attribute(Variable("buffer","mapping(string => mapping(string => uint))"))
        contract.add_attribute(Variable("chainStartTime", "uint"))    
        contract.add_attribute(Variable("chainEndTime", "uint"))    

    def __create_constructor(self, contract : Contract):
        contract.add_constructor(Constructor([Variable("nfaAddress","address")],f"""
    nfa = {self.nfa.name}(nfaAddress);
    chainStartTime = block.timestamp;
    chainEndTime = 0;
        """))
    
    def __create_utils(self, contract : Contract):

        contract.add_function(Function("getStartTime", 
                                [],
                                """return chainStartTime;""",
                                "public view",
                                "uint"))

        contract.add_function(Function("getEndTime", 
                                [],
                                """return chainEndTime;""",
                                "public view",
                                "uint"))

        contract.add_function(Function("getKB", 
                                [],
                                """return kb;""",
                                "public view",
                                "string[] memory"))

        contract.add_function(Function("check_sat", 
                                [Variable("precondition", "string", "memory")],
                                """
if (bytes(precondition).length == 0) {
            return true;
        }

        bool res = arrContains(precondition, kb);
        if (bytes(precondition)[0] == "!") {
            // negated proposition
            res = ! res;
        } 
        return res;
""",
                                "public view",
                                "bool"))


##        contract.add_function(Function("strCompare",
##                                [Variable("stringA","string","memory"),Variable("stringB","string","memory")],
##                                "return keccak256(abi.encodePacked(stringA)) == keccak256(abi.encodePacked(stringB));",
##                                "internal pure",
##                                "bool"))
##
##
##        contract.add_function(Function("contains",
##                                [Variable("what","string","memory"),Variable("where","string","memory")],
##                                """strings.slice memory whereSliced = where.toSlice();
##strings.slice memory whatSliced = what.toSlice();
##return whereSliced.contains(whatSliced);""",
##                                "internal pure",
##                                "bool"))
##
##        contract.add_function(Function("split",
##                                [Variable("sequence","string","memory"),Variable("del","string","memory")],
##                                """strings.slice memory s = sequence.toSlice();
##strings.slice memory delim = del.toSlice();
##string[] memory parts = new string[](s.count(delim) + 1);
##for(uint i = 0; i < parts.length; i++) {
##    parts[i] = s.split(delim).toString();
##}
##return parts;""",
##                                "private pure",
##                                "string[] memory"))
        
        contract.add_function(Function("buffer_add",
                                [Variable("actor","string","memory"),Variable("message","string","memory")],
                                """uint counter = buffer[actor][message];
counter += 1;
if (!arrContains(actor,actors)) {
    actors.push(actor);
}
if(!arrContains(message,messages)) {
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
        contract.add_function(Function("condition_rule_send_now",
                                [Variable("precondition", "string", "memory"), Variable("message","string","memory")],
                                """return check_sat(precondition) && contains("!", message) && nfa.checkEnabledTransitions(message);""",
                                "private view",
                                "bool"))
                
        contract.add_function(Function("condition_rule_receive_now",
                                [Variable("precondition", "string", "memory"), Variable("message","string","memory")],
                                """return check_sat(precondition) && contains("?", message) && nfa.checkEnabledTransitions(message);""",
                                "private view",
                                "bool"))

        contract.add_function(Function("condition_rule_receive_delayed",
                                [Variable("precondition", "string", "memory"), Variable("message","string","memory")],
                                """return contains("?", message);""",
                                "private view",
                                "bool"))

        contract.add_function(Function("condition_rule_send_delayed",
                                [Variable("precondition", "string", "memory"), Variable("message","string","memory")],
                                """return contains("!", message);""",
                                "private view",
                                "bool"))


        contract.add_function(Function("condition_rule_buffered",
                                [],
                                """delete tmpStates;
for (uint i = 0; i < actors.length; i++) {
    for (uint j = 0; j < messages.length; j++) {
        string memory send_message = string(abi.encodePacked("!", messages[j]));
        string memory receive_message = string(abi.encodePacked("?", messages[j]));

        if (buffer[actors[i]][receive_message] > 0) {
            string memory message = string(abi.encodePacked(actors[i],"?",messages[j]));
            string[] memory currentStates = nfa.getCurrentStates();
            for (uint s = 0; s < currentStates.length; s++) {
                tmpStates = nfa.transitionFrom(currentStates[s], encodeEvent(message));
                if (tmpStates.length > 0) {
                    return split(string(abi.encodePacked(actors[i], ":?:", message)), ":");
                }
            }
        } else if (buffer[actors[i]][send_message] > 0) {
            string memory message = string(abi.encodePacked(actors[i],"!",messages[j]));
            string[] memory currentStates = nfa.getCurrentStates();
            for (uint s = 0; s < currentStates.length; s++) {
                tmpStates = nfa.transitionFrom(currentStates[s], encodeEvent(message));
                if (tmpStates.length > 0) {
                    return split(string(abi.encodePacked(actors[i], ":!:", message)), ":");
                }
            }
        } 
    }
}
return split("","");""",
                                "private",
                                "string[] memory"))

    def __create_rules(self, contract : Contract):
        contract.add_function(Function("rule_send_now",
                                [Variable("message","string","memory")],
                                #"nfa.transition(message); return message;",
                                "nfa.transition(encodeEvent(message)); return message;",
                                "private",
                                "string memory"))
        
        contract.add_function(Function("rule_receive_now",
                                [Variable("message","string","memory")],
                                #"nfa.transition(message); return message;",
                                "nfa.transition(encodeEvent(message)); return message;",
                                "private",
                                "string memory"))

        contract.add_function(Function("rule_receive_delayed",
                                [Variable("actor","string","memory"),Variable("message","string","memory")],
                                """buffer_add(actor, string(abi.encodePacked("?", message)));
return "";""",
                                "private",
                                "string memory"))


        contract.add_function(Function("rule_send_delayed",
                                [Variable("actor","string","memory"),Variable("message","string","memory")],
                                """buffer_add(actor, string(abi.encodePacked("!", message)));
return "";""",
                                "private",
                                "string memory"))

        contract.add_function(Function("rule_receive_buffered",
                                [Variable("actor","string","memory"),Variable("message","string","memory")],
                                """nfa.transition(encodeEvent(string(abi.encodePacked(actor,"?",message))));
buffer_remove(actor, string(abi.encodePacked("?", message)));
return string(abi.encodePacked(actor,"?",message));""",
                                "private",
                                "string memory"))
 
        contract.add_function(Function("rule_send_buffered",
                                [Variable("actor","string","memory"),Variable("message","string","memory")],
                                """nfa.transition(encodeEvent(string(abi.encodePacked(actor,"!",message))));
buffer_remove(actor, string(abi.encodePacked("!", message)));
return string(abi.encodePacked(actor,"!",message));""",
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
#                                [Variable("the_input","string","memory")],
                                [Variable("precondition","string","memory"), Variable("event_input","string","memory"), Variable("knowledge", "string[]", "memory")],
                                """string memory out;
string memory debug;

/*
string memory precondition;
string memory event_input;
string[] memory input_parts = split(the_input, ":");

if (input_parts.length == 2) {
    precondition = input_parts[0];
    event_input = input_parts[1];
} else {
    event_input = input_parts[0];
}
*/
if (condition_rule_send_now(precondition, event_input)) {
    debug = string(abi.encodePacked("(* Condition rule receive send: ", precondition, " => ", event_input, " *)"));
    out = rule_send_now(event_input);
}  else if (condition_rule_send_delayed(precondition, event_input)) {
    string memory actor = split(event_input, "!")[0];
    string memory message = split(event_input, "!")[1];
    debug = string(abi.encodePacked("(* Condition rule receive send delayed: ", precondition, " => ", event_input, " *)"));
    out = rule_send_delayed(actor, message);
} else if (condition_rule_receive_now(precondition, event_input)) {
    //string memory actor = split(event_input, "?")[0];
    //string memory message = split(event_input, "?")[1];
    debug = string(abi.encodePacked("(* Condition rule receive now: ", precondition, " => ", event_input, " *)"));
    out = rule_receive_now(event_input);
} else if (condition_rule_receive_delayed(precondition, event_input)) {
    string memory actor = split(event_input, "?")[0];
    string memory message = split(event_input, "?")[1];
    debug = string(abi.encodePacked("(* Condition rule receive delayed: ", precondition, " => ", event_input, " *)"));
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
string[]  memory parts = condition_rule_buffered();

if (parts.length == 0) {
    out = "None";
    debug = "(* No usable message found in buffer for current states. *)";
} else {
    string memory actor = parts[0];
    string memory action = parts[1];
    string memory message = parts[2];

    if (strCompare(action, "?")) {
        debug = string(abi.encodePacked("(* Condition rule receive buffered: ", message, " *)"));
        out = rule_receive_buffered(actor, action);            
    } else {
        debug = string(abi.encodePacked("(* Condition rule send buffered: ", message, " *)"));
        out = rule_send_buffered(actor, action);            
    }
}

emit outputEvent(debug, out);
return out;""",
                                "public",
                                "string memory"))

        contract.add_function(Function("getNfaAddress",
                                [],
                                """return address(nfa);""",
                                "public view",
                                "address"))

    def createContract(self):
        contract : Contract = Contract("Enforcer")

#        self.__create_directives(contract)
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
    
        # create constants for transition symbols
        transitions_labels = set([])

        #init_constants = [ "uint constant EPSILON = 0;" ]
        init_encode = [ ("","EPSILON") ]

        self.contract.add_constant(Constant("EPSILON", "uint", "0"))

        constant_value = 1
        for t in self.nfa.transitions:
            if t.label and t.label not in transitions_labels:
                #breakpoint()
                transitions_labels.add(t.label)
                constant_name = t.label.replace("!","__S__").replace("?","__R__")
                self.contract.add_constant(Constant(constant_name, "uint", constant_value))
                #init_constants.append(f"uint constant {constant_name} = {constant_value};")
                init_encode.append((t.label, constant_name))
                constant_value = constant_value + 1

        self.contract.add_function(Function("indexOf",
                            [Variable("mainStr", "string", "memory"), Variable("subStr", "string", "memory")],
                            """
        bytes memory mainBytes = bytes(mainStr);
        bytes memory subBytes = bytes(subStr);
        
        if (subBytes.length == 0 || subBytes.length > mainBytes.length) {
            return -1; // Return -1 if substring is empty or longer than the main string
        }

        for (uint i = 0; i <= mainBytes.length - subBytes.length; i++) {
            bool matchFound = true;
            
            for (uint j = 0; j < subBytes.length; j++) {
                if (mainBytes[i + j] != subBytes[j]) {
                    matchFound = false;
                    break;
                }
            }
            
            if (matchFound) {
                return int(i); // Return the starting index of the substring
            }
        }
        
        return -1; // Not found
                            """,
                            "pure",
                            "int"))


        self.contract.add_function(Function("arrContains",
                                [Variable("s","string","memory"),Variable("states","string[]","memory")],
                                """for (uint i = 0; i < states.length; i++) {
    if (strCompare(s,states[i])) {
        return true;
    }
}
return false;""",
                                "pure", #"internal pure",
                                "bool"))


        self.contract.add_function(Function("contains",
                            [Variable("what", "string", "memory"),Variable("where", "string", "memory")],
                            """
		return indexOf(where, what) >= 0;
                            """,
                            "pure",
                            "bool"))

        self.contract.add_function(Function("split",
                            [Variable("str", "string", "memory"),Variable("delimiter", "string", "memory")],
                            """
        bytes memory strBytes = bytes(str);
        bytes memory delimiterBytes = bytes(delimiter);
        
        uint count = 1; // At least one element
        for (uint i = 0; i < strBytes.length - delimiterBytes.length + 1; i++) {
            bool matchFound = true;
            for (uint j = 0; j < delimiterBytes.length; j++) {
                if (strBytes[i + j] != delimiterBytes[j]) {
                    matchFound = false;
                    break;
                }
            }
            if (matchFound) {
                count++;
                i += delimiterBytes.length - 1;
            }
        }

        string[] memory parts = new string[](count);
        uint index = 0;
        uint lastIndex = 0;

        for (uint i = 0; i < strBytes.length - delimiterBytes.length + 1; i++) {
            bool matchFound = true;
            for (uint j = 0; j < delimiterBytes.length; j++) {
                if (strBytes[i + j] != delimiterBytes[j]) {
                    matchFound = false;
                    break;
                }
            }
            if (matchFound) {
                parts[index] = substring(str, lastIndex, i);
                index++;
                lastIndex = i + delimiterBytes.length;
                i += delimiterBytes.length - 1;
            }
        }
        parts[index] = substring(str, lastIndex, strBytes.length); // Last part
        return parts;
                            """,
                            "pure", 
                            "string[] memory"))

        self.contract.add_function(Function("substring",
                            [Variable("str","string","memory"),Variable("startIndex", "uint"),Variable("endIndex", "uint")],
                            """
        bytes memory strBytes = bytes(str);
        bytes memory result = new bytes(endIndex - startIndex);
        for (uint i = startIndex; i < endIndex; i++) {
            result[i - startIndex] = strBytes[i];
        }
        return string(result);
                            """,
                            "pure",
                            "string memory"))

        self.contract.add_function(Function("strCompare",
                            [Variable("stringA", "string", "memory"), Variable("stringB", "string", "memory")],
                            "return keccak256(abi.encodePacked(stringA)) == keccak256(abi.encodePacked(stringB));",
                            "pure", 
                            "bool"))
    
        breakpoint()
        self.contract.add_function(Function("encodeEvent",
                            [Variable("symbol", "string", "memory")],

                            "\n".join([ f"if (strCompare(symbol, '{symbol}')) {{ return {constant}; }}" for symbol,constant in init_encode ]),
                            "view", 
                            "uint"))

###    
###        verbatim = """
###library Symbols {
###    """ + '\n    '.join(init_constants) + """
###
###    function encodeEvent(string memory symbol) public view returns (uint) { return 0;
###        """ + "\n".join([ f"if (strCompare(symbol, '{symbol}')) {{ return {constant}; }}" for symbol,constant in init_encode ][:1]) + """
###    }
###}
###        """
###
###        self.contract.add_verbatim(verbatim)
###

        #Library
        #strings: String & slice utility library for Solidity contracts.
        #self.contract.add_library("strings", "https://raw.githubusercontent.com/Arachnid/solidity-stringutils/master/src/strings.sol")

        #Contracts    
        nfaContract = NFAContractGenerator(self.nfa).createContract()
        enforcerContract = EnforcerContractGenerator(nfaContract).createContract()

        self.contract.add_contract(nfaContract)
        self.contract.add_contract(enforcerContract)

        return self.contract
