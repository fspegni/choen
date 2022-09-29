from contracts import Constructor, Contract, Function, Variable, Event

class EnforcerGenerator:

    def createEnforcer(self, nfaContract: Contract):
        #c : Contract = Contract(f"Enforcer{nfaContract.name}", "0.7.6")
        c : Contract = Contract("Enforcer")

        #Imports
        #c.add_import(f"./public/contracts/{nfaContract.name}.sol")

        
        #c.add_import("github.com/Arachnid/solidity-stringutils/strings.sol")

        #Enfocer directives
        c.add_directive("using strings for *")

        #Enfocer events
        c.add_event(Event("outputEvent",[Variable("debug","string"), Variable("messageOut","string")]))

        #Enforcer variables
        c.add_attribute(Variable("nfa",nfaContract.name))
        c.add_attribute(Variable("actors","string[]",))
        c.add_attribute(Variable("messages","string[]"))
        c.add_attribute(Variable("tmpStates","string[]"))
        c.add_attribute(Variable("buffer","mapping(string => mapping(string => uint))"))

        #Enforcer constructor
        c.add_constructor(Constructor([Variable("nfaAddress","address")],f"nfa = {nfaContract.name}(nfaAddress);"))

        #Enforcer functions

        #UTILS
        c.add_function(Function("strCompare",
                                [Variable("stringA","string","memory"),Variable("stringB","string","memory")],
                                "return keccak256(abi.encodePacked(stringA)) == keccak256(abi.encodePacked(stringB));",
                                "internal pure",
                                "bool"))

        c.add_function(Function("arrContains",
                                [Variable("states","string[]","memory"),Variable("s","string","memory")],
                                """for (uint i = 0; i < states.length; i++) {
    if (strCompare(s,states[i])) {
        return true;
    }
}
return false;""",
                                "internal pure",
                                "bool"))

        c.add_function(Function("contains",
                                [Variable("what","string","memory"),Variable("where","string","memory")],
                                """strings.slice memory where = where.toSlice();
strings.slice memory what = what.toSlice();
return where.contains(what);""",
                                "internal pure",
                                "bool"))

        c.add_function(Function("split",
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
        
        c.add_function(Function("union",
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

        c.add_function(Function("buffer_add",
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

        c.add_function(Function("buffer_remove",
                                [Variable("actor","string","memory"),Variable("message","string","memory")],
                                """uint counter = buffer[actor][message];
require(counter > 0, string(abi.encodePacked("No message ", message, " to remove for actor ", actor)));
counter -= 1;
buffer[actor][message] = counter;""",
                                "private"))

        
        # CONDITIONS
        c.add_function(Function("condition_receive_now",
                                [Variable("message","string","memory")],
                                """return nfa.checkEnabledTransitions(message);""",
                                "private",
                                "bool"))

        c.add_function(Function("condition_receive_buffered",
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

    
        # RULES
        c.add_function(Function("send",
                                [Variable("message","string","memory")],
                                "return message;",
                                "private",
                                "string memory"))
        
        c.add_function(Function("receive_now",
                                [Variable("message","string","memory")],
                                """nfa.transition(message);
return message;""",
                                "private",
                                "string memory"))

        c.add_function(Function("receive_delayed",
                                [Variable("actor","string","memory"),Variable("message","string","memory")],
                                """buffer_add(actor, message);
return "";""",
                                "private",
                                "string memory"))

        c.add_function(Function("receive_buffered",
                                [Variable("actor","string","memory"),Variable("message","string","memory")],
                                """nfa.transition(string(abi.encodePacked(actor,"?",message)));
buffer_remove(actor, message);
return string(abi.encodePacked(actor,"?",message));""",
                                "private",
                                "string memory"))

        #GETTER
        c.add_function(Function("getActors",
                                [],
                                "return actors;",
                                "public view",
                                "string[] memory"))
        
        c.add_function(Function("getMessages",
                                [],
                                "return messages;",
                                "public view",
                                "string[] memory"))

        c.add_function(Function("get_buffer_item",
                                [Variable("actor", "string", "memory"), Variable("message", "string", "memory")],
                                "return buffer[actor][message];",
                                "public view",
                                "uint"))

        
        # PROCESSORS
        c.add_function(Function("process_input",
                                [Variable("event_input","string","memory")],
                                """string memory out;
string memory debug;
//uint num_states_pre = nfa.getCurrentStates().length;
if (contains("!", event_input)) {
    debug = string(abi.encodePacked("(* Condition rule receive send: ", event_input, " *)"));
    out = send(event_input);
} else if (contains("?", event_input)) {
    string memory actor = split(event_input, "?")[0];
    string memory message = split(event_input, "?")[1];
    if(condition_receive_now(event_input)) {
        debug = string(abi.encodePacked("(* Condition rule receive now: ", event_input, " *)"));
        out = receive_now(event_input);
    } else {
        debug = string(abi.encodePacked("(* Condition rule receive delayed: ", event_input, " *)"));
        out = receive_delayed(actor, message);
    }
} else {
    debug = "No matching condition";
    out = "None";
}
emit outputEvent(debug, out);
return out;""",
                                "public",
                                "string memory"))

        c.add_function(Function("process_check",
                                [],
                                """string memory out = "";
string memory debug;
string memory message = condition_receive_buffered();
if(!strCompare(message,"None")) {
    string memory actor = split(message, "?")[0];
    string memory action = split(message, "?")[1];
    debug = string(abi.encodePacked("(* Condition rule receive buffered: ", message, " *)"));
    out = receive_buffered(actor, action);            
} else {
            out = "None";
            debug = "(* No usable message found in buffer for current states. *)";
        }
emit outputEvent(debug, out);
return out;""",
                                "public",
                                "string memory"))

        return c
    
    """def compileContract(self, c: Contract):
        return c.compile()"""