import nfa
from contracts import Constructor, Contract, Function, Variable, Constant, Event, SmartContract, Enum, Struct, Library
import re

def is_memory_type(solidity_type):

    if solidity_type == "string" or solidity_type.endswith("[]"):
        return True

    return False

class Generator:

    def create_events(self, *args, **kwargs):
        pass

    def create_attributes(self, *args, **kwargs):
        pass

    def create_constructor(self, *args, **kwargs):
        pass

    def create_functions(self, *args, **kwargs):
        pass

    def create_enums(self, *args, **kwargs):
        pass

    def __init__(self, contract_name):
        self._contract_name = contract_name

    def createContract(self):
        contract : Contract = Contract(self._contract_name) #"Enforcer")

        self.create_events(contract)
        self.create_enums(contract)
        self.create_attributes(contract)
        self.create_constructor(contract)

        self.create_functions(contract)
    
        return contract


class EncoderContractGenerator(Generator):
 
    def __init__(self, n : nfa.NFA):
        super().__init__("_Encoder")

        assert n is not None, f"Expected not-null nfa to build a contract"
        self._nfa : nfa.NFA = n
        self._DT = {}

    def create_encoding(self, contract, name, plain_type, encoded_type="bytes32", plain_type_attributes=[]):

        # categories to enumerate:
        # - state names 
        # - observed symbols
        # - propositions

        #breakpoint()
        enum_name = f"E_{name}"
        #mapping_name = f"M_{name}"
        lookup_name = f"LU_{name}"

        contract.add_attribute(Variable(lookup_name, f"mapping({encoded_type} => {plain_type})"))

        abi_encode = "abi.encodePacked(plain)"
        if plain_type_attributes:
            abi_encode = "abi.encode(" + ",".join(map(lambda a: f"plain.{a}", plain_type_attributes)) + ")"

        encodeBody = f"{encoded_type} encoded = keccak256({abi_encode}); return encoded;"
        encodeStoreBody = f"{encoded_type} encoded = keccak256({abi_encode}); {lookup_name}[encoded] = plain;"
        storeBody = f"{encoded_type} encoded = keccak256({abi_encode}); {lookup_name}[encoded] = plain;"
        decodeBody = f"return {lookup_name}[encoded];"

        decodeArrayBody = f"""
    {plain_type}[] memory res = new {plain_type}[](items.length);

    for (uint idx=0; idx < items.length; idx++) {{
        res[idx] = decode_{name}(items[idx]);
    }}  
    return res;
        """

        contract.add_function(Function(f"encode_{name}", [ Variable("plain", plain_type, "memory") ], encodeBody, f"public pure returns({encoded_type})")) 
        contract.add_function(Function(f"encode_store_{name}", [ Variable("plain", plain_type, "memory") ], encodeStoreBody, f"public returns({encoded_type})")) 
        contract.add_function(Function(f"store_{name}", [ Variable("plain", plain_type, "memory"), Variable("encoded", encoded_type) ], storeBody, f"public")) 
        contract.add_function(Function(f"decode_{name}", [ Variable("encoded", encoded_type) ], decodeBody, f"public pure returns({plain_type} memory)"))  # FS "pure" was "view"
        contract.add_function(Function(f"decode_array_{name}", [ Variable("items", f"{encoded_type}[] calldata") ], decodeArrayBody, f"public pure returns ({plain_type}[] memory)"))

        contract.add_attribute(Variable(f"empty_{name}", f"{encoded_type} public"))


    def create_constructor(self, contract):

        #self.create_encoding(contract, "STATE", "string", encoded_type="STATES")
        #breakpoint()

        #breakpoint()
        state_names = list(map(lambda s: s.id, self._nfa.states))

        #self.create_encoder(contract, "STATE", "string", values=state_names, encoded_type="STATES")
        self.create_decoder(contract, "STATE", "string", values=sorted(state_names), encoded_type="STATES")

        #self.create_encoder(contract, "AGENT", "string", values=self._nfa.agents, encoded_type="AGENTS")
        self.create_decoder(contract, "AGENT", "string", values=sorted(self._nfa.agents), encoded_type="AGENTS")

        #self.create_encoder(contract, "MESSAGE", "string", values=self._nfa.messages, encoded_type="MESSAGES")
        self.create_decoder(contract, "MESSAGE", "string", values=sorted(self._nfa.messages), encoded_type="MESSAGES")

        #self.create_encoder(contract, "EVENT_ACTION", "bytes1", values={ "send": "!", "recv": "?" }, encoded_type="EVENT_ACTION")
        self.create_decoder(contract, "EVENT_ACTION", "bytes1", values={ "send": "!", "recv": "?" }, encoded_type="EVENT_ACTION")



        #self.create_encoding(contract, "SYMBOL", "Symbol", plain_type_attributes=["agent","action","message"], encoded_type="SYMBOLS")
        #self.create_encoding(contract, "PROPOSITION", "string", encoded_type="PROPOSITIONS")
        #self.create_encoding(contract, "AGENT", "string", encoded_type="AGENTS")
        #self.create_encoding(contract, "MESSAGE","string", encoded_type="MESSAGES")

        constructor_body = """
    //empty_STATE = encode_STATE('');
    //empty_AGENT = encode_AGENT('');
    //empty_SYMBOL = encode_SYMBOL(Symbol(empty_AGENT, EVENT_ACTION.epsilon, MESSAGES.empty_MESSAGE));
    //empty_PROPOSITION = encode_PROPOSITION('');
    //empty_MESSAGE = encode_MESSAGE('');
        """

        contract.add_constructor(Constructor([], constructor_body, "internal"))


class EncoderContractWithCountersGenerator(EncoderContractGenerator):

    def create_encoding(self, contract, name, plain_type, encoded_type="uint16", plain_type_attributes=[]):

        #breakpoint()
        enum_name = f"E_{name}"
        counter_name = f"counter_{name}"
        lookup_name = f"LU_{name}"

        contract.add_attribute(Variable(lookup_name, f"mapping({encoded_type} => {plain_type})"))
        contract.add_attribute(Variable(counter_name, encoded_type))

        if encoded_type.startswith("uint"):        
            encodeBody = f"return {counter_name} + 1;"
            encodeStoreBody = f"{encoded_type} new_value = {counter_name} + 1; {counter_name} = new_value; return new_value;"
        else:
            encodeBody = f"return {encoded_type}.wrap({encoded_type}.unwrap({counter_name}) + 1);"
            encodeStoreBody = f"{encoded_type} new_value = {encoded_type}.wrap({encoded_type}.unwrap({counter_name}) + 1); {counter_name} = new_value; return new_value;"

        #encodeStoreBody = f"return {counter_name}++;"
        #storeBody = f"{lookup_name}[encoded] = plain;";
        storeBody = f"{counter_name} = encoded;"
        decodeBody = f"return {lookup_name}[encoded];"

        decodeArrayBody = f"""
    {plain_type}[] memory res = new {plain_type}[](items.length);

    for (uint idx=0; idx < items.length; idx++) {{
        res[idx] = decode_{name}(items[idx]);
    }}  
    return res;
        """

        contract.add_function(Function(f"encode_{name}", [ Variable("plain", plain_type, "memory") ], encodeBody, f"public view returns({encoded_type})")) 
        contract.add_function(Function(f"encode_store_{name}", [ Variable("plain", plain_type, "memory") ], encodeStoreBody, f"public returns({encoded_type})")) 
        contract.add_function(Function(f"store_{name}", [ Variable("plain", plain_type, "memory"), Variable("encoded", encoded_type) ], storeBody, f"public")) 
        #contract.add_function(Function(f"decode_{name}", [ Variable("encoded", encoded_type) ], decodeBody, f"public view returns({plain_type} memory)")) 
        #contract.add_function(Function(f"decode_array_{name}", [ Variable("items", f"{encoded_type}[] memory") ], decodeArrayBody, f"public view returns ({plain_type}[] memory)"))

        #contract.add_attribute(Variable(f"empty_{name}", f"{encoded_type} public"))


class EncoderContractWithEnumsGenerator(EncoderContractGenerator):


    def create_encoder(self, contract, name, plain_type, values, encoded_type, plain_type_attributes=[]):

        encodeBody_lines = []
        if isinstance(values, dict):
            for k,v in sorted(values.items()):
                # k : enum label
                # v : string received as input
                if plain_type == "string":
                    encodeBody_lines.append(f"if (keccak256(bytes(plain)) == keccak256(bytes('{v}'))) {{ return {encoded_type}.{k}; }}")
                elif plain_type == "bytes1":
                    encodeBody_lines.append(f"if (plain == '{v}') {{ return {encoded_type}.{k}; }}")
                else:
                    encodeBody_lines.append(f"if (plain == {v})) {{ return {encoded_type}.{k}; }}")
        else:
            for curr in values: #self._nfa.states:
                if plain_type == "string":
                    encodeBody_lines.append(f"if (keccak256(bytes(plain)) == keccak256(bytes('{curr}'))) {{ return {encoded_type}.{curr}; }}")
                elif plain_type == "bytes1":
                    encodeBody_lines.append(f"if (plain == '{curr}') {{ return {encoded_type}.{curr}; }}")
                else:
                    encodeBody_lines.append(f"if (plain == {curr}) {{ return {encoded_type}.{curr}; }}")

        encodeBody_lines.append(f"revert('Input not recognized');")

        encodeBody = "\n".join(encodeBody_lines)

        plain_type_extra = f"{plain_type} memory" if is_memory_type(plain_type) else plain_type
        encoded_type_extra = f"{encoded_type} memory" if is_memory_type(encoded_type) else encoded_type

        contract.add_function(Function(f"encode_{name}", [ Variable("plain", f"{plain_type_extra}") ], encodeBody, f"public pure returns({encoded_type_extra})")) 
 

    def create_decoder(self, contract, name, plain_type, values, encoded_type, plain_type_attributes=[]):

        decodeBody_lines = []
        if isinstance(values, dict):
            for k,v in sorted(values.items()):
                # k : enum label
                # v : string to be returned
                if plain_type in [ "string", "bytes1" ]:
                    decodeBody_lines.append(f"if (encoded == {encoded_type}.{k}) {{ return '{v}'; }}")
                else:
                    decodeBody_lines.append(f"if (encoded == {encoded_type}.{k}) {{ return {v}; }}")
        else:
            for curr in values: #self._nfa.states:
                if plain_type in [ "string", "bytes1" ]:
                    decodeBody_lines.append(f"if (encoded == {encoded_type}.{curr}) {{ return '{curr}'; }}")
                else:
                    decodeBody_lines.append(f"if (encoded == {encoded_type}.{curr}) {{ return {curr}; }}")

        decodeBody_lines.append(f"revert('Value not recognized');")

        decodeBody = "\n".join(decodeBody_lines)

        plain_type_extra = f"{plain_type} memory" if is_memory_type(plain_type) else plain_type
        encoded_type_extra = f"{encoded_type} memory" if is_memory_type(encoded_type) else encoded_type

        contract.add_function(Function(f"decode_{name}", [ Variable("encoded", encoded_type_extra) ], decodeBody, f"public pure returns({plain_type_extra})")) 
 
        decodeArrayBody = f"""
    {plain_type}[] memory res = new {plain_type}[](items.length);

    for (uint idx=0; idx < items.length; idx++) {{
        res[idx] = decode_{name}(items[idx]);
    }}  
    return res;
        """
      
        contract.add_function(Function(f"decode_array_{name}", [ Variable("items", f"{encoded_type}[] calldata") ], decodeArrayBody, f"public pure returns ({plain_type}[] memory)"))




class NFAContractGenerator(Generator): 
    
    def __init__(self, n : nfa.NFA):

        assert n is not None, f"Expected not-null nfa to build a contract"

        super().__init__("_NFA")
        self._nfa : nfa.NFA = n
        
    @property
    def nfa(self) -> nfa.NFA:
        return self._nfa
    

    def create_attributes(self, contract : Contract):


        contract.add_attribute(Variable("encoder", "_Encoder"))

        #contract.add_attribute(Variable("states","string[]","",list(map(lambda s: s.id, self.nfa.states))))

        #states_encoded = ", ".join([ f"encoder.encode_STATE('{s.id}')" for s in self.nfa.states ])

        #breakpoint()
        #contract.add_attribute(Variable("states", "uint16[]")) #"bytes32[]")) #,"", "[" + states_encoded + "]" )) #list(map(lambda s: s.id, self.nfa.states)))) #,a lambda values: f"bytes32('{v}')"))
        contract.add_attribute(Variable("states", "STATES[]")) #"bytes32[]")) #,"", "[" + states_encoded + "]" )) #list(map(lambda s: s.id, self.nfa.states)))) #,a lambda values: f"bytes32('{v}')"))

        #contract.add_attribute(Variable("tmpStates","string[]"))
        #contract.add_attribute(Variable("tmpStates","bytes32[]")) # FS remove this
        #contract.add_attribute(Variable("initialState", "string","",'"'+str(self.nfa.initial.id)+'"'))
        contract.add_attribute(Variable("initialState", "STATES")) #"bytes32")) #,"",'encoder.encode_STATE("'+str(self.nfa.initial.id)+'")'))
        #contract.add_attribute(Variable("finalStates", "string[]","",list(map(lambda f: f.id, self.nfa.final))))

        #contract.add_attribute(Variable("finalStates", "string[]","",list(map(lambda f: f.id, self.nfa.final))))
        contract.add_attribute(Variable("finalStates", "STATES[]")) #"bytes32[]")) #,"","[" + final_states_encoded + "]"))
        contract.add_attribute(Variable("currentStates", "STATES[]")) #"bytes32[]")) #"string[]"))
        #contract.add_attribute(Variable("message", "string[]"))
        #contract.add_attribute(Variable("message", "uint[]"))
        #contract.add_attribute(Variable("epsilon","string"))
        contract.add_attribute(Variable("start","bool"))
        contract.add_attribute(Variable("end","bool"))
        #contract.add_attribute(Variable("transitions", "mapping(string => mapping(string => string[]))"))
        #contract.add_attribute(Variable("transitions", "mapping(bytes32 => mapping(bytes32 => bytes32[]))"))
        contract.add_attribute(Variable("transitions", "mapping(bytes32 => STATES[])")) #"mapping(bytes32 => bytes32[])"))
        #contract.add_attribute(Variable("transitions", "mapping(string => mapping(string => buffItem[]))")) # TODO restart from here
    
    def create_constructor(self, contract : Contract):

        initTransitionsBody = ""
        for t in self.nfa.transitions:

            #the_symbol = "Symbol('', EVENT_ACTION.epsilon, '')"
            the_action = "epsilon"
            actor = message = ""
            if "!" in t.label:
                actor, message = t.label.split("!")
                #the_symbol = f"Symbol('{actor}', EVENT_ACTION.send, '{message}')"
                the_action = "send"
            elif "?" in t.label:
                actor, message = t.label.split("?")
                #the_symbol = f"Symbol('{actor}', EVENT_ACTION.recv, '{message}')"
                the_action = "recv"
            elif t.label != "":
                raise Exception(f"Symbol not recognized: {t.label}")

            initTransitionsBody += f"addTransition(STATES.{t.source.id}, AGENTS.{solidity_slugify(actor)}, EVENT_ACTION.{solidity_slugify(the_action)}, MESSAGES.{solidity_slugify(message)}, STATES.{t.target.id});\n"

        

#        constructorBody += """
        constructorBody = f"""
encoder = new _Encoder();
initTransitions();
STATES[] memory tmpStates = new STATES[](1);
tmpStates[0] = initialState;
currentStates = tmpStates;
        """

        contract.add_constructor(Constructor([], constructorBody, "internal"))

        #breakpoint()
        states_encoded = "\n            ".join([ f"addState('{s.id}');" for s in self.nfa.states ])

        final_states_encoded = ",\n                ".join([ f"encoder.encode_STATE('{s.id}')" for s in self.nfa.final])

##        initStatesBody = f"""
##        {states_encoded} 
##
##        initialState = encoder.encode_STATE("{self.nfa.initial.id}");
##
##        finalStates = [
##            {final_states_encoded}
##        ];
##        """
##
##        addStateBody = """
##    //uint16 h = encoder.encode_STATE(name);
##    //encoder.store_STATE(name, h);
##    //states.push(h);
##    states.push(state)
##        """
##
#        contract.add_function(Function("initStates", [], initStatesBody, "private"))
        contract.add_function(Function("initTransitions", [], initTransitionsBody, "private")) # TODO ensure this cannot be called twice

        #initStatesBody = "\n".join ( map(lambda s: f"states.push(STATES.{s.id});", self.nfa.states) )
        #contract.add_function(Function("initStates", [], initStatesBody, "private"))  # TODO ensure this cannot be called twice

#        contract.add_function(Function("addState", [Variable("name", "string memory")], addStateBody, "private"))
#        contract.add_function(Function("addState", [Variable("state", "STATES")], addStateBody, "private"))

#        addTransitionBody = f"Symbol memory symbol = Symbol(actor, action, message); bytes32 k = keccak256(abi.encode(source, encoder.encode_SYMBOL(symbol))); transitions[k].push(target);"
        addTransitionBody = f"bytes32 k = keccak256(abi.encode(source, actor, action, message)); transitions[k].push(target);"
        contract.add_function(Function("addTransition", [ Variable("source", "STATES"), Variable("actor", "AGENTS"), Variable("action", "EVENT_ACTION"), Variable("message", "MESSAGES"), Variable("target", "STATES")], addTransitionBody, "private")) # TODO if this should be called from the enforcer (public), find a way to force at most one call; if not call all other functions should be "blocked"

    def create_functions(self, contract : Contract):

        contract.add_function(Function("getEncoder",
                        [],
                        "return encoder;",
                        "public view",
                        "_Encoder"))

        contract.add_function(Function("checkInitialAndFinalStates",
                        #[Variable("newStates", "string[]","memory")],
                        #[Variable("newStates", "bytes32[]", "memory")],
                        [Variable("newStates", "STATES[]", "memory")],
                        """start = false;
end = false;
for (uint i = 0; i < newStates.length; i++) {
    if (newStates[i] == initialState) {
            start = true;
        }
        for (uint k = 0; k < finalStates.length; k++) {
            if (newStates[i] == finalStates[k]) {
                end = true;
           }
        }
    }""",
                        "private",))


##        contract.add_function(Function("e_closure",
##                        #[Variable("newStates","string[]","memory")],
##                        [Variable("newStates","bytes32[]","memory")],
##                        """
##		bytes32[] memory tmpStates = new bytes32[](states.length);
##		bool found;
##		uint count = 0;
##
##		for (uint idx=0; idx < newStates.length; idx++) {
##			tmpStates[idx] = newStates[idx];
##			count++;
##		}
##
##		
##		do {
##		    found = false;
##
##		    for (uint i = 0; i < count; i++) {
##		
##		        bytes32[] memory candidates = transitionFrom(tmpStates[i], encoder.encode_SYMBOL(Symbol(encoder.empty_AGENT(), EVENT_ACTION.epsilon, encoder.empty_MESSAGE())));
##		
##				for (uint j = 0; j < candidates.length; j++) {
##					if (! arrContains(candidates[j], tmpStates)) {
##						tmpStates[count++] = candidates[j];
##						found = true;
##					}
##				}
##		    }
##		} while(found);
##		checkInitialAndFinalStates(tmpStates);
##		return shrink(tmpStates, count);
##                        """,
##                        "private",
##                        #"string[] memory"))
##                        "bytes32[] memory"))
##

        isTransitionBody = """
		//uint16 h_source = encoder.encode_STATE(source);
		//uint16 h_target = encoder.encode_STATE(target);
		//uint16 h_actor = encoder.encode_AGENT(actor);
		//uint16 h_message = encoder.encode_MESSAGE(message);

		Symbol memory symbol = Symbol(actor, action, message);
		//uint16 h_symbol = encoder.encode_SYMBOL(symbol);

		bytes32 h = keccak256(abi.encode(source /* h_source */, /* h_symbol */ symbol));

		STATES[] memory candidates = transitions[h];

		if (candidates.length == 0) {
			return false;
		}

		for (uint idx = 0; idx < candidates.length; idx++) {
			if (candidates[idx] == target /* h_target */) {
				return true;
			}
		}

		return false;
        """

        contract.add_function(Function("isTransition",
                                [Variable("source", "STATES"), Variable("actor", "AGENTS"), Variable("action", "EVENT_ACTION"), Variable("message", "MESSAGES"), Variable("target", "STATES") ],
                                isTransitionBody,   
                                "public view",
                                "bool"))


##        contract.add_function(Function("getStates",
##                                [],
##                                "return states;",
##                                "public view",
##                                #"string[] memory"))
##                                #"bytes32[] memory"))
##                                "uint16[] memory"))

        contract.add_function(Function("getStatesAsString",
                                [],
                                "return encoder.decode_array_STATE(states);",
                                "public view",
                                "string[] memory"))
        
        contract.add_function(Function("getCurrentStates",
                                [],
                                "return currentStates;",
                                "public view",
                                #"string[] memory"))
                                #"bytes32[] memory"))
                                "STATES[] memory"))

        contract.add_function(Function("getCurrentStatesAsString",
                                [],
                                "return encoder.decode_array_STATE(currentStates);",
                                "public view",
                                "string[] memory"))

        contract.add_function(Function("getInitialState",
                                [],
                                "return initialState;",
                                "public view",
                                "STATES"))

        contract.add_function(Function("getInitialStateAsString",
                                [],
                                "return encoder.decode_STATE(initialState);",
                                "public view",
                                "string memory"))



        contract.add_function(Function("getFinalStates",
                                [],
                                "return finalStates;",
                                "public view",
                                #"bytes32[] memory"))
                                "STATES[] memory"))

        contract.add_function(Function("getFinalStatesAsString",
                                [],
                                "return encoder.decode_array_STATE(finalStates);",
                                "public view",
                                "string[] memory"))

        contract.add_function(Function("isEnded",
                                [],
                                "return end;",
                                "public view",
                                "bool"))


        contract.add_function(Function("isFinal",
                                #[Variable("curr","bytes32")],
                                [Variable("curr","STATES")],
                                """(bool found, ) = Utils.arrContains(curr, finalStates); return found;""", 
                                "public view",
                                "bool"))
 
        contract.add_function(Function("isInitial",
                                #[Variable("curr","bytes32")],
                                [Variable("curr","STATES")],
                                """return curr == initialState;""",
                                "public view",
                                "bool"))


        contract.add_function(Function("isCurrent",
                                #[Variable("curr","bytes32")],
                                [Variable("curr","STATES")],
                                """(bool found, ) = Utils.arrContains(curr, currentStates); return found;""", # TODO
                                "public view",
                                "bool"))

## FS ?!? TODO
##        contract.add_function(Function("getMessage",
##                                [],
##                                "return message;",
##                                "public view",
##                                "string[] memory"))


##        transitionFromBody = """
##		bytes32[] memory tmp = transitions[encoder.encode_STATE(state)][encoder.encode_SYMBOL(label)];
##        string[] memory res = new string[](tmp.length);
##
##        for (uint idx=0; idx < tmp.length; idx++) {
##            res[idx] = encoder.decode_STATE(tmp[idx]);
##        }
##        return res;
##"""
        contract.add_function(Function("transitionFrom",
                                #[Variable("state","string","memory"), Variable("label","string","memory")],
                                #[Variable("state","bytes32"), Variable("label","bytes32")],
                                #[Variable("state","STATES"), Variable("label","uint16")],
                                [Variable("source","STATES"), Variable("actor","AGENTS"), Variable("action", "EVENT_ACTION"), Variable("message", "MESSAGES")],
                                #transitionFromBody,
                                #"bytes32 k = keccak256(abi.encode(state, label)); return transitions[k];",
                                "bytes32 k = keccak256(abi.encode(source, actor, action, message)); return transitions[k];",
                                "public view",
                                #"bytes32[] memory"))
                                "STATES[] memory"))

        contract.add_function(Function("transition",
                                #[Variable("label","string","memory")],
                                #[Variable("label","SYMBOLS")],
                                #[Variable("label","bytes32")],
                                #[Variable("label","uint16")],
                                [Variable("label", "Symbol", "memory")],
"""
        STATES[] memory tmp;
		for (uint i = 0; i < currentStates.length; i++) {
		    STATES[] memory s = transitionFrom(currentStates[i], label.agent, label.action, label.message);
		    tmp = Utils.union(tmp, s);
		}
		require(tmp.length != 0);
		//message.push(label);
		//currentStates = e_closure(tmp);
        currentStates = tmp;
""",
##                                """delete tmpStates;
##for (uint i = 0; i < currentStates.length; i++) {
##    string[] memory s = transitionFrom(currentStates[i],label);
##    tmpStates = union(tmpStates, s);
##}
##require(tmpStates.length != 0);
##//message.push(label);
##currentStates = e_closure(tmpStates);""",
                                "public")) 
        
        contract.add_function(Function("checkEnabledTransitions",
                        #[Variable("symbol","Symbol","memory"), Variable("symbol_enc", "bytes32")],
                        [Variable("symbol","Symbol","memory")], #Variable("symbol_enc", "uint16")],
                        """
for (uint i = 0; i < currentStates.length; i++) {
    STATES[] memory s_reached = transitionFrom(currentStates[i], symbol.agent, symbol.action, symbol.message /* symbol_enc */);
    if (s_reached.length > 0) return true;
    //reached = union(reached, s_reached); 
}
return false;
                        """,
                        "public view",
                        "bool"))
##    
##    def createContract(self):
##
##        contract : Contract = Contract("NFA")
##
##        self.__create_structures(contract)
##        self.__create_attributes(contract)
##        
##        self.__create_constructor(contract)
##        
##        self.__create_functions(contract)
##        
##        return contract
    

class EnforcerContractGenerator(Generator):

    def __init__(self, nfa : Contract):
        assert nfa is not None, f"Expected not-null nfa contract to build an enforcer"

        super().__init__("Enforcer")
        self._nfa : Contract = nfa

    @property
    def nfa(self) -> Contract:
        return self._nfa
    

    def create_events(self, contract : Contract):
        contract.add_event(Event("outputEvent",[Variable("debug","string"), Variable("messageOut", "Symbol") ]))

    def create_attributes(self, contract : Contract):
        contract.add_attribute(Variable("encoder", "_Encoder"))
        contract.add_attribute(Variable("nfa", "_NFA")) #self.nfa.name))
        contract.add_attribute(Variable("actors","string[]",))
        contract.add_attribute(Variable("buffer","BufferItem[]"))
        #contract.add_attribute(Variable("tmpStates","bytes32[]"))
        contract.add_attribute(Variable("kb","PROPOSITIONS[]")) # ,"bytes32[]"))
        #contract.add_attribute(Variable("buffer","mapping(string => mapping(string => uint))"))
        contract.add_attribute(Variable("chainStartTime", "uint"))    
        contract.add_attribute(Variable("chainEndTime", "uint"))    

    def create_constructor(self, contract : Contract):
        contract.add_constructor(Constructor([Variable("nfaAddress", "address")],
    f"""
    nfa = _NFA(nfaAddress);
    encoder = nfa.getEncoder();
    chainStartTime = block.timestamp;
    chainEndTime = 0;
        """))
    
    def __create_utils(self, contract : Contract):

        # some getters
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
                                #"bytes32[] memory"))
                                "PROPOSITIONS[] memory"))


        contract.add_function(Function("update_kb",
                                [ Variable("knowledge", "Prop[]", "memory") ],
                                """
		for (uint idx = 0; idx<knowledge.length; idx++) {
			Prop memory curr = knowledge[idx];
			(bool found, uint pos) = Utils.arrContains(curr.identifier, kb);
			if ( ! curr.neg && ! found) {
				kb.push(); //(curr.identifier);
				kb[kb.length-1] = curr.identifier;
			} else if (curr.neg && found) {
				kb[pos] = kb[kb.length-1];
				kb.pop();
			}
		}
                                """,
                                "public"
        ))

        contract.add_function(Function("check_sat", 
                                [Variable("precondition", "Prop[]", "memory")],
                                """
		if (precondition.length == 0) {
            return true;
        }

        for (uint idx = 0; idx < precondition.length; idx++) {
            Prop memory curr = precondition[idx];
            (bool found, ) = Utils.arrContains(curr.identifier, kb);
            if ((! curr.neg && found) || (curr.neg && ! found))
            {
                return false;
            }
        }
        return true;

""",
                                "public view",
                                "bool"))


        contract.add_function(Function("buffer_add",
                                [ Variable("precondition", "Prop[]", "memory"), Variable("symbol", "Symbol", "memory"), Variable("knowledge", "Prop[]", "memory") ],
                                """
		BufferItem storage newItem = buffer.push();
		newItem.symbol = symbol;

		// Manually copy precondition array
		for (uint i = 0; i < precondition.length; i++) {
			newItem.precondition.push(precondition[i]);
		}

		// Manually copy knowledge array
		for (uint i = 0; i < knowledge.length; i++) {
			newItem.knowledge.push(knowledge[i]);
		}

                                """,
                                "private"))



#        splitInput_body = """
#    bytes memory data = bytes(input);
#
#    for (uint i = 0; i < data.length; i++) {
#        
#        if (data[i] == "!" || data[i] == "?") {
#            agent = encoder.encode_AGENT(substring(data, 0, i));
#            action = encoder.encode_EVENT_ACTION(data[i]);
#            message = encoder.encode_MESSAGE(substring(data, i+1, data.length));
#            return (agent, action, message);
#        }
#    }
#
#    revert("Unexpected input");
#        """
#
#        contract.add_function(Function("splitInput",
#                                [ Variable("input", "string memory") ],
#                                splitInput_body,
#                                "private view",
#                                "AGENTS agent, EVENT_ACTION action, MESSAGES message"))
#


    def __create_conditions(self, contract : Contract):
        contract.add_function(Function("condition_rule_send_now",
                                [ Variable("precondition", "Prop[]", "memory"), Variable("symbol","Symbol","memory") ], #Variable("symbol_enc", "uint16") ], #"bytes32") ],
                                """return check_sat(precondition) && symbol.action == EVENT_ACTION.send && nfa.checkEnabledTransitions(symbol /* , symbol_enc */);""",
                                "private view",
                                "bool"))
                
        contract.add_function(Function("condition_rule_receive_now",
                                [ Variable("precondition", "Prop[]", "memory"), Variable("symbol","Symbol","memory") ], #Variable("symbol_enc", "uint16") ], #"bytes32") ],
                                """return check_sat(precondition) && symbol.action == EVENT_ACTION.recv && nfa.checkEnabledTransitions(symbol /*, symbol_enc */);""",
                                "private view",
                                "bool"))

        contract.add_function(Function("condition_rule_receive_delayed",
                                [ Variable("precondition", "Prop[]", "memory"), Variable("symbol","Symbol","memory") ], #Variable("symbol_enc", "uint16") ], #"bytes32") ],
                                """return symbol.action == EVENT_ACTION.recv;""",
                                "private pure",
                                "bool"))

        contract.add_function(Function("condition_rule_send_delayed",
                                [ Variable("precondition", "Prop[]", "memory"), Variable("symbol","Symbol","memory") ], #Variable("symbol_enc", "uint16") ], #"bytes32") ],
                                """return symbol.action == EVENT_ACTION.send;""",
                                "private pure",
                                "bool"))


    def __create_rules(self, contract : Contract):
        contract.add_function(Function("rule_send_now",
                                [ Variable("precondition", "Prop[]", "memory"), Variable("symbol","Symbol","memory"), Variable("knowledge", "Prop[]", "memory") ], # Variable("symbol_enc", "uint16")], #"bytes32")],
                                #"nfa.transition(message); return message;",
                                #"nfa.transition(symbol_enc); return symbol;",
                                "nfa.transition(symbol); update_kb(knowledge); return symbol;",
                                "private",
                                "Symbol memory"))
        
        contract.add_function(Function("rule_receive_now",
                                [ Variable("precondition", "Prop[]", "memory"), Variable("symbol","Symbol","memory"), Variable("knowledge", "Prop[]", "memory") ],  #Variable("symbol_enc", "uint16")], #"bytes32")],
                                #"nfa.transition(message); return message;",
                                #"nfa.transition(symbol_enc); return symbol;",
                                "nfa.transition(symbol); update_kb(knowledge); return symbol;",
                                "private",
                                "Symbol memory"))

        contract.add_function(Function("rule_receive_delayed",
                                [ Variable("precondition", "Prop[]", "memory"), Variable("symbol","Symbol","memory"), Variable("knowledge", "Prop[]", "memory") ], #Variable("symbol_enc", "uint16")], #"bytes32")],
                                """
    buffer_add(precondition, symbol, knowledge);
    return Symbol(AGENTS.empty_AGENT, EVENT_ACTION.epsilon, MESSAGES.empty_MESSAGE);
                                """,
                                "private",
                                "Symbol memory"))


        contract.add_function(Function("rule_send_delayed",
                                [ Variable("precondition", "Prop[]", "memory"), Variable("symbol", "Symbol", "memory"), Variable("knowledge", "Prop[]", "memory") ], # Variable("symbol_enc", "uint16")], #"bytes32")],
                                """
    buffer_add(precondition, symbol, knowledge);
    return Symbol(AGENTS.empty_AGENT, EVENT_ACTION.epsilon, MESSAGES.empty_MESSAGE);
                                """,
                                "private",
                                "Symbol memory"))

      
    def __create_getters(self, contract : Contract):
##        contract.add_function(Function("getActors",
##                                [],
##                                "return actors;",
##                                "public view",
##                                "bytes32[] memory"))
##        
        contract.add_function(Function("getBuffer",
                                [],
                                "return buffer;",
                                "public view",
                                "BufferItem[] memory"))



##        contract.add_function(Function("get_buffer_item",
##                                [Variable("actor", "string", "memory"), Variable("message", "string", "memory")],
##                                "return buffer[actor][message];",
##                                "public view",
##                                "uint"))
##

    def __create_processors(self, contract : Contract):
        contract.add_function(Function("process_input",
                                [ Variable("precondition", "Prop[]", "memory"), Variable("agent", "AGENTS"), Variable("action", "EVENT_ACTION"), Variable("message","MESSAGES"), Variable("knowledge", "Prop[]", "memory") ],
#                                [ Variable("the_input", "string memory") ],
                                """

//AGENTS agent;
//EVENT_ACTION action;
//MESSAGES message;
//
//( agent, action, message ) = splitInput(the_input);

Symbol memory symbol = Symbol(agent, action, message);
//Prop[] memory precondition;
Symbol memory out;
string memory debug;

//uint16 symbol_enc = encoder.encode_SYMBOL(symbol);
//bytes32 agent_enc = encoder.encode_AGENT(symbol.agent);
//bytes32 message_enc = encoder.encode_MESSAGE(symbol.message);

if (condition_rule_send_now(precondition, symbol /*, symbol_enc */)) {
    debug = "(* Condition rule send now *)";
    out = rule_send_now(precondition, symbol, knowledge /*, symbol_enc */);
}  else if (condition_rule_send_delayed(precondition, symbol /* , symbol_enc */)) {
    debug = "(* Condition rule send delayed *)";
    out = rule_send_delayed(precondition, symbol, knowledge /* , symbol_enc */);
} else if (condition_rule_receive_now(precondition, symbol /*, symbol_enc */)) {
    debug = "(* Condition rule receive now *)";
    out = rule_receive_now(precondition, symbol, knowledge /*, symbol_enc */);
} else if (condition_rule_receive_delayed(precondition, symbol /*, symbol_enc */)) {
    debug = "(* Condition rule receive delayed *)";
    out = rule_receive_delayed(precondition, symbol, knowledge /*, symbol_enc */);
} else {
    debug = "No matching condition";
    out = Symbol(AGENTS.empty_AGENT, EVENT_ACTION.epsilon, MESSAGES.empty_MESSAGE); //"None";
}
emit outputEvent(debug, out);

process_check();

return out;
                                """,
                                "public",
                                "Symbol memory"))

        contract.add_function(Function("process_check",
                                [],
                                """
		
				Symbol memory out = Symbol(AGENTS.empty_AGENT, EVENT_ACTION.epsilon, MESSAGES.empty_MESSAGE);
		
				bool dirty = true;
		
				while (dirty) {
					dirty = false;
		
					for (uint i=0; i<buffer.length; i++) {
						BufferItem memory bi = buffer[i];
						Prop[] memory precondition = bi.precondition;
						Symbol memory currSymbol = bi.symbol;
                        Prop[] memory knowledge = bi.knowledge;
		
						if (currSymbol.action == EVENT_ACTION.send && condition_rule_send_now(precondition, currSymbol)) {
							rule_send_now(precondition, currSymbol, knowledge);
							buffer[i] = buffer[buffer.length-1];
							buffer.pop();
							dirty = true;
						} else if (currSymbol.action == EVENT_ACTION.recv && condition_rule_receive_now(precondition, currSymbol)) {
							rule_receive_now(precondition, currSymbol, knowledge);
							buffer[i] = buffer[buffer.length-1];
							buffer.pop();
							dirty = true;
						}
					}
				}
		
				return out; // TODO fix this, in theory a sequence may be emitted
		
                                """,
                                "public",
                                "Symbol memory"))

        contract.add_function(Function("getNFA",
                                [],
                                "return nfa;",
                                "public view",
                                "_NFA"))

##        contract.add_function(Function("getNFAStates",
##                                [],
##                                "return nfa.getStatesAsString();",
##                                "public view",
##                                "STATES[] memory"))

        contract.add_function(Function("getNFACurrentStates",
                                [],
                                "return nfa.getCurrentStatesAsString();",
                                "public view",
                                "string[] memory"))

        contract.add_function(Function("getNFAStates",
                                [],
                                "return nfa.getStatesAsString();",
                                "public view",
                                "string[] memory"))


        contract.add_function(Function("getNFAInitialState",
                                [],
                                "return nfa.getInitialStateAsString();",
                                "public view",
                                "string memory"))


        contract.add_function(Function("getNFAFinalStates",
                                [],
                                "return nfa.getFinalStatesAsString();",
                                "public view",
                                "string[] memory"))

##
##    def createContract(self):
##        contract : Contract = Contract("Enforcer")
##
###        self.__create_directives(contract)
##        self.__create_events(contract)
##        self.__create_attributes(contract)
##        self.__create_constructor(contract)
## .. and other code now in create_function

    def create_functions(self, contract):

        self.__create_utils(contract)
        self.__create_conditions(contract)
        self.__create_rules(contract)
        self.__create_getters(contract)
        self.__create_processors(contract)

def solidity_slugify(text):
    return re.sub(r"[^a-zA-Z0-9]","_", text)
    
class SmartContractGenerator:
    
    def __init__(self, nfa : nfa.NFA):
        assert nfa is not None, f"Expected not-null nfa to build a contract"
        self._nfa = nfa
        self._contract : SmartContract = SmartContract("0.7.6")

    @property
    def nfa(self):
        return self._nfa

    @property
    def contract(self) -> SmartContract:
        return self._contract

    def create_libraries(self):

        # a collector for several utils

        utils = Library("Utils")

        # same body for several versions of the function
        arrContains_body = """
for (uint i = 0; i < collection.length; i++) {
    if (item == collection[i]) {
        return (true, i);
    }
}
return (false, 0);
        """



        utils.add_function(Function("arrContains",
                                #[Variable("s","string","memory"),Variable("states","string[]","memory")],
                                #[Variable("s","bytes32"),Variable("states","bytes32[]","memory")],
                                [Variable("item","uint16"),Variable("collection","uint16[]","memory")],
                                arrContains_body,
                                "public pure", #"internal pure",
                                "bool, uint"))

        utils.add_function(Function("arrContains",
                                #[Variable("s","string","memory"),Variable("states","string[]","memory")],
                                #[Variable("s","bytes32"),Variable("states","bytes32[]","memory")],
                                [ Variable("item", "STATES"), Variable("collection", "STATES[]", "memory") ],
                                arrContains_body,
                                "public pure", #"internal pure",
                                "bool, uint"))

        utils.add_function(Function("arrContains",
                                #[Variable("s","string","memory"),Variable("states","string[]","memory")],
                                #[Variable("s","bytes32"),Variable("states","bytes32[]","memory")],
                                [ Variable("item", "PROPOSITIONS"), Variable("collection", "PROPOSITIONS[]", "memory") ],
                                arrContains_body,
                                "public pure", #"internal pure",
                                "bool, uint"))
        
        utils.add_function(Function("shrink",
                        #[Variable("source", "bytes32[]", "memory"), Variable("newSize", "uint")],
                        [Variable("source", "STATES[]", "memory"), Variable("newSize", "uint")],
"""
        require(newSize <= source.length);

        if (source.length == newSize) {
            return source;
        } else {
            STATES[] memory res = new STATES[](newSize);
            for (uint idx = 0; idx < newSize; idx++) {
                res[idx] = source[idx];
            } 
            return res;
        }
""",
                        "public pure",
                        #"bytes32[] memory")
                        "STATES[] memory")
        )

        utils.add_function(Function("indexOf",
                        #[Variable("arrayA","string[]","memory"),Variable("arrayB","string[]","memory")],
                        #[Variable("array","bytes32[]","memory"),Variable("item","bytes32")],
                        [Variable("array","STATES[]","memory"),Variable("item","STATES")],
                        """
        for (uint idx = 0; idx < array.length; idx++) {
            if (array[idx] == item) {
                return int256(idx);
            }
        }

        return -1;
                        """,
                        "public pure",
                        "int"))
        
        utils.add_function(Function("union",
                        #[Variable("arrayA","string[]","memory"),Variable("arrayB","string[]","memory")],
                        #[Variable("arrayA","bytes32[]","memory"),Variable("arrayB","bytes32[]","memory")],
                        [Variable("arrayA","STATES[]","memory"),Variable("arrayB","STATES[]","memory")],
                        """
	
        STATES[] memory tmp = new STATES[](arrayA.length + arrayB.length);
        uint countA = 0;
        uint countB = 0;

        for (uint idx = 0; idx < arrayA.length; idx++) {
            STATES curr = arrayA[idx];
            if (indexOf(tmp, curr) < 0) {
                tmp[countA++] = curr;
            }
        }

        for (uint idx = 0; idx < arrayB.length; idx++) {
            STATES curr = arrayB[idx];

            if (indexOf(tmp, curr) < 0) {
                tmp[countA + countB++] = curr;
            }
            
        }

        return shrink(tmp, countA + countB);
	                    """,
                        "public pure", # was "private"
                        #"string[] memory"))
                        #"bytes32[] memory"))
                        "STATES[] memory"))



        self._contract.add_library("Utils", utils)



    def create_structs(self):

        #self._contract.add_type("PROPOSITIONS", "uint16")
        #self._contract.add_type("AGENTS", "uint16")
        #self._contract.add_type("MESSAGES", "uint16")
        #self._contract.add_struct(Struct("Symbol", [ ("agent", "bytes32"), ("action", "EVENT_ACTION"), ("message", "bytes32") ]))
        self._contract.add_struct(Struct("Symbol", [ ("agent", "AGENTS"), ("action", "EVENT_ACTION"), ("message", "MESSAGES") ]))
        self._contract.add_struct(Struct("Prop", [ ("neg", "bool"), ("identifier", "PROPOSITIONS") ])) #("identifier", "bytes32") ]))
        self._contract.add_struct(Struct("BufferItem", [ ("precondition", "Prop[]", "memory"), ("symbol", "Symbol"), ("knowledge", "Prop[]", "memory") ]))


    def create_enums(self):

        self._contract.add_enum(Enum("EVENT_ACTION", [ "epsilon", "send", "recv" ]))

        self._contract.add_enum(Enum("STATES", sorted([ s.id for s in self._nfa.states ]))) 
        self._contract.add_enum(Enum("AGENTS", [ "empty_AGENT", ] + sorted([ solidity_slugify(a) for a in self._nfa.agents ]))) 
        self._contract.add_enum(Enum("MESSAGES", [ "empty_MESSAGE", ] + sorted([m for m in self._nfa.messages ])))
        propositions = [ m for m in self._nfa.propositions ] or [ "foo" ] # at least one member is required for ENUM's
        self._contract.add_enum(Enum("PROPOSITIONS", propositions))


    def createSmartContract(self) -> SmartContract:
    

        self.create_libraries()
        self.create_enums()
        self.create_structs()




##        substring_body = """
##    bytes memory result = new bytes(end - start);
##    for (uint i = start; i < end; i++) {
##        result[i - start] = data[i];
##    }
##    return string(result);
##        """
##
##        self._contract.add_function(Function("substring",
##                                [ Variable("data", "bytes memory"), Variable("start", "uint"), Variable("end", "uint") ],
##                                substring_body,
##                                "pure",
##                                "string memory"))
##
        #Contracts    
        #encoderContract = EncoderContractGenerator(self.nfa).createContract()
        encoderContract = EncoderContractWithEnumsGenerator(self.nfa).createContract()
        nfaContract = NFAContractGenerator(self.nfa).createContract()
        enforcerContract = EnforcerContractGenerator(nfaContract).createContract()

        self._contract.add_contract(encoderContract)
        self._contract.add_contract(nfaContract)
        self._contract.add_contract(enforcerContract)

        return self._contract

    def decode_state(self, value):
        return self._encoderContract.decode_state(value)


class MPSTLocalTypeContractGenerator(Generator):

    def __init__(self, contract_name : str, local_type):
    
        #breakpoint()
        self._local_type = local_type
        super().__init__(contract_name)

    def create_attributes(self, contract):

        contract.add_attribute(Variable("states", "STATES[]"))
        contract.add_attribute(Variable("pr", "PruneRelation"))
        contract.add_attribute(Variable("input", "Task[]"))
        contract.add_attribute(Variable("output", "Task[]"))
        contract.add_attribute(Variable("buffer", "Task[]"))

    def create_constructor(self, contract):
        initial_state = str(self._local_type.initial)
        constructor_body = f"states.push(STATES.{initial_state});\ncheck_no_input();"
        contract.add_constructor(Constructor([], constructor_body))

    def create_functions(self, contract):

        from mpst.models import MsgSend, MsgRecv

        check_no_input_body = """
int256 pos1;
int256 pos2;

bool dirty = false;

do {
    dirty = false;
        """

        for t in self._local_type.transforms:
            if t.is_fork:
                check_no_input_body = f"{check_no_input_body}\n\n    // fork: {t} \n    pos1 = states_arr_find(states, STATES.{t.lhs}); if (pos1 >= 0) {{ apply_fork(states, pr, uint256(pos1), STATES.{t.rhs.arguments[0]}, STATES.{t.rhs.arguments[1]}); dirty = true; }}"

            elif t.is_join:

                check_no_input_body = f"{check_no_input_body}\n\n    // join: {t} \n    pos1 = states_arr_find(states, STATES.{t.lhs.arguments[0]}); if (pos1 >= 0) {{ pos2 = states_arr_find(states, STATES.{t.lhs.arguments[1]}); if (pos2 >= 0) {{ apply_join(states, pr, uint256(pos1), uint256(pos2), STATES.{t.rhs}); dirty = true; }} }}"


            elif t.is_merge:

                check_no_input_body = f"{check_no_input_body}\n\n    // merge : {t} \n    pos1 = states_arr_find(states, STATES.{t.lhs.arguments[0]}); if (pos1 >= 0) {{ apply_passthrough(states, pr, uint256(pos1), STATES.{t.rhs}); dirty = true; }} else {{ pos2 = states_arr_find(states, STATES.{t.lhs.arguments[1]}); if (pos2 >= 0) {{ apply_passthrough(states, pr, uint256(pos2), STATES.{t.rhs}); dirty = true; }} }}"

            elif t.is_passthrough:
                check_no_input_body = f"{check_no_input_body}\n\n    // passthrough : {t} \n    pos1 = states_arr_find(states, STATES.{t.lhs}); if (pos1 >=0) {{ apply_passthrough(states, pr, uint256(pos1)); dirty = true; }}"

            elif t.is_end:
                check_no_input_body = f"{check_no_input_body}\n\n    // end : {t} \n    pos1 = states_arr_find(states, STATES.{t.lhs}); if (pos1 >= 0) {{ apply_end(states, pr, uint256(pos1)); dirty = true; }}"

            elif t.is_internal_choice or t.is_external_choice:
                #breakpoint()
                check_no_input_body = f"{check_no_input_body}\n\n    // internal/external choice: {t} \n    pos1 = states_arr_find(states, STATES.{t.lhs}); if (pos1 >= 0) {{ apply_choice(states, pr, uint256(pos1), STATES.{t.rhs.arguments[0]}, STATES.{t.rhs.arguments[1]}); dirty = true; }} "


        check_no_input_body = f"{check_no_input_body}\n}} while (dirty); "


        contract.add_function(Function("check_no_input", [], check_no_input_body, "public"))


        check_task_body = """
int256 pos;

input.push(task);

        """

        for t in self._local_type.transforms:
            if t.is_concat:

                assert len(t.rhs.arguments) == 2, "Unexpected number of arguments for Concat"

                next_var = t.rhs.arguments[-1]
                action = "" # "none"
                #breakpoint()
                if isinstance(t.rhs.arguments[0], MsgSend):
                    action = "Send" 
                    #field = "target"
                    initiator = t.rhs.arguments[0].sender
                    target = t.rhs.arguments[0].receiver


                elif isinstance(t.rhs.arguments[0], MsgRecv):
                    action = "Receive"
                    #field = "initiator"
                    initiator = t.rhs.arguments[0].receiver
                    target = t.rhs.arguments[0].sender

                else:
                    raise Exception("Action not supported")


                check_task_body = f"{check_task_body}\n\n// {action} : {t} \npos = states_arr_find(states, STATES.{t.lhs}); if (pos >= 0) {{ if (task.action == ACTIONS.{ action } && task.initiator == PARTICIPANTS.{ initiator } && task.target == PARTICIPANTS.{ target }) {{ apply_send_receive(states, pr, uint256(pos), STATES.{t.rhs.arguments[-1]}); output.push(task); check_no_input(); return; }} else if (task.action == ACTIONS.Wt{ action } && task.initiator == PARTICIPANTS.{ initiator } && task.target == PARTICIPANTS.{ target }) {{ apply_passthrough(states, pr, uint256(pos), STATES.{t.lhs}); output.push(task); check_no_input(); return; }} }} "


    

        check_task_body = f"{check_task_body}\n\ncheck_no_input();\n\n// otherwise, add to buffer\n\nbuffer.push(task);"

        contract.add_function(Function("check_task", [Variable("task", "Task", "calldata")], check_task_body, "public"))


        contract.add_function(Function("getStates", [], "return states;", "public view returns(STATES[] memory)"))
        contract.add_function(Function("getInput", [], "return input;", "public view returns(Task[] memory)"))
        contract.add_function(Function("getOutput", [], "return output;", "public view returns(Task[] memory)"))
        contract.add_function(Function("getBuffer", [], "return buffer;", "public view returns(Task[] memory)"))

        contract.add_function(Function("getPruneRelationKeys", [], "return pr.keys;", "public view returns(STATES[] memory)"))
        contract.add_function(Function("getPruneRelation", [Variable("s","STATES")], "return pr.to_prune[s];", "public view returns(STATES[] memory)"))

        
        contract.add_function(Function("getInputAsString", [], "return task_arr_to_string(input);", "public view returns(string[] memory)"))
        contract.add_function(Function("getOutputAsString", [], "return task_arr_to_string(output);", "public view returns(string[] memory)"))
        contract.add_function(Function("getBufferAsString", [], "return task_arr_to_string(buffer);", "public view returns(string[] memory)"))
 
class MPSTSmartContractGenerator:
    
    from mpst.models import GlobalType

    def __init__(self, gt : GlobalType):
        assert gt is not None, f"Expected not-null MPST global type to build a contract"
        self._gt = gt
        self._contract : SmartContract = SmartContract("0.7.6")

        self._participants = gt.participants
        if not self._participants or len(self._participants) < 2:
            raise Exception("Expected global type with at least two participants")

        self._local_types = {}
        self._local_types_contracts = {}

        self._actions = { "Send" : "!", "Receive": "?", "WtSend": "!*", "WtReceive": "?*" }

        for p in self._participants:
            #breakpoint()
            lt = gt.project(p)
            self._local_types[p] = lt
            lt_sc = MPSTLocalTypeContractGenerator(p, lt).createContract()
            self._local_types_contracts[p] = lt_sc


    @property
    def gt(self):
        return self._gt

    @property
    def participants(self):
        return self._participants

    @property
    def contract(self):
        return self._contract

    @property
    def local_types(self):
        return self._local_types

    @property
    def local_types_contracts(self):
        return self._local_types_contracts

 
    def createSmartContract(self):

        self.create_enums()
        self.create_structs()
        self.create_contracts()

        self.create_aux_functions()

        return self.contract

    def create_aux_functions(self):

        states_arr_remove_body = """
	for (uint256 i = 0; i < states.length; i++) {
		if (states[i] == state) {
			states[i] = states[states.length - 1];
			states.pop();
		}
	}
        """
        self.contract.add_function(Function("states_arr_remove", [Variable("states", "STATES[] storage"), Variable("state", "STATES")], states_arr_remove_body, ""))

        states_arr_find_body = """
    for (uint256 i = 0; i < states.length; i++) {
        if (states[i] == state) {
            return int256(i);
        }
    }

    return -1;
        """
        self.contract.add_function(Function("states_arr_find", [Variable("states", "STATES[] memory"), Variable("state", "STATES")], states_arr_find_body, "pure returns(int256)"))

        states_arr_of1_body = """
    STATES[] memory temp = new STATES[](1);
	temp[0] = a;
	return temp;
        """
        self.contract.add_function(Function("states_arr_of", [Variable("a", "STATES")], states_arr_of1_body, "pure returns(STATES[] memory)"))

        states_arr_of2_body = """
    STATES[] memory temp = new STATES[](2);
	temp[0] = a;
	temp[1] = b;
	return temp;
        """
        self.contract.add_function(Function("states_arr_of", [Variable("a", "STATES"), Variable("b", "STATES")], states_arr_of2_body, "pure returns(STATES[] memory)"))


        states_arr_join = """
	STATES[] memory temp = new STATES[](a.length + b.length);
	uint idx=0;
	for (idx=0; idx<a.length; idx++) {
		temp[idx] = a[idx];
	}
	for (uint jdx=0; jdx<b.length; jdx++) {
		temp[jdx+idx] = b[jdx];
	}
	return temp;
        """
        self.contract.add_function(Function("states_arr_join", [Variable("a", "STATES[] memory"), Variable("b", "STATES[] memory")], states_arr_join, "pure returns(STATES[] memory)"))


        pr_add_body = """
	// check1 : the state should not exist in the mapping
	require(pr.to_prune[source].length == 0); 

	// check 2 : the state should not exist in the keys
	for (uint idx=0; idx<pr.keys.length; idx++) {
		if (pr.keys[idx] == source) {
			revert("Unexpected error: state should not be in prune relation");
		}
	}

	pr.keys.push(source);

	pr.to_prune[source] = to_prune;
        """
        self.contract.add_function(Function("pr_add", [Variable("pr", "PruneRelation storage"), Variable("source", "STATES"), Variable("to_prune", "STATES[] memory")], pr_add_body, ""))

        pr_remove_body = """
	for (uint idx=0; idx<pr.keys.length; idx++) {
		STATES source1 = pr.keys[idx];

		if (source1 == source) {
			// remove source's alternative states
			pr.keys[idx] = pr.keys[pr.keys.length-1];
			pr.keys.pop();

			delete pr.to_prune[source];
		} else {
			
			// source1 != source => remove source from source1's alternative states (if present)
			for (uint jdx=0; jdx<pr.to_prune[source1].length; jdx++) {
				if (pr.to_prune[source1][jdx] == source) {
					pr.to_prune[source1][jdx] = pr.to_prune[source1][ pr.to_prune[source1].length - 1];
					pr.to_prune[source1].pop();
				}
			}
		}
	}
        """
        self.contract.add_function(Function("pr_remove", [Variable("pr", "PruneRelation storage"), Variable("source", "STATES")], pr_remove_body, ""))

        pr_update_body = """
    require(targets.length > 0, "Empty targets");

    for (uint idx=0; idx<pr.keys.length; idx++) {
    
        int found = states_arr_find(pr.to_prune[pr.keys[idx]], source);
        if (found >= 0) {
            STATES[] storage old_targets = pr.to_prune[pr.keys[idx]];
            old_targets[uint(found)] = targets[0];

            for (uint j=1; j<targets.length; j++) {
                old_targets.push(targets[j]);
            }
            pr.to_prune[source] = old_targets;

            break;        
        }
    }
        """
        self.contract.add_function(Function("pr_update", [Variable("pr", "PruneRelation storage"), Variable("source", "STATES"), Variable("targets", "STATES[] memory")], pr_update_body, ""))

        apply_fork_body = """
    STATES source = states[lhs];
    states[lhs] = rhs1;
    states.push(rhs2);
    pr_update(pr, source, states_arr_of(rhs1, rhs2));
        """
        self.contract.add_function(Function("apply_fork", [Variable("states", "STATES[] storage"), Variable("pr", "PruneRelation storage"), Variable("lhs","uint256"), Variable("rhs1", "STATES"), Variable("rhs2", "STATES")], apply_fork_body, ""))

    
        apply_join_body = """
    STATES source1 = states[lhs1];
    STATES source2 = states[lhs2];
    states[lhs1] = rhs;
    states[lhs2] = states[states.length - 1];
    states.pop();
    pr_update(pr, source1, states_arr_of(rhs));
    pr_update(pr, source2, states_arr_of(rhs));
        """
        self.contract.add_function(Function("apply_join", [Variable("states", "STATES[] storage"), Variable("pr", "PruneRelation storage"), Variable("lhs1","uint256"), Variable("lhs2", "uint256"), Variable("rhs", "STATES")], apply_join_body, ""))


        apply_choice_body = """

	STATES source = states[lhs];
	STATES[] memory to_prune = pr.to_prune[source];

	states[lhs] = rhs1;
	states.push(rhs2);

	pr_update(pr, source, states_arr_of(rhs1, rhs2));

	pr_add(pr, rhs1, states_arr_join(to_prune, states_arr_of(rhs2)));
	pr_add(pr, rhs2, states_arr_join(to_prune, states_arr_of(rhs1)));
        """
    
        self.contract.add_function(Function("apply_choice", [Variable("states", "STATES[] storage"), Variable("pr", "PruneRelation storage"), Variable("lhs","uint256"), Variable("rhs1", "STATES"), Variable("rhs2", "STATES")], apply_choice_body, ""))


##        apply_merge_body = """
##    STATES source = states[lhs];
##    states[lhs] = rhs;
##    pr_update(pr, source, states_arr_of(rhs));
##        """
##        self.contract.add_function(Function("apply_merge", [Variable("states", "STATES[] storage"), Variable("pr", "PruneRelation storage"), Variable("lhs","uint256"), Variable("rhs", "STATES")], apply_merge_body, ""))
##

        apply_passthrough_body = """
    STATES source = states[lhs];
    states[lhs] = rhs;
    if (source != rhs) { pr_update(pr, source, states_arr_of(rhs)); }
        """
        self.contract.add_function(Function("apply_passthrough", [Variable("states", "STATES[] storage"), Variable("pr", "PruneRelation storage"), Variable("lhs","uint256"), Variable("rhs", "STATES")], apply_passthrough_body, ""))

        apply_end_body = """
    STATES source = states[lhs];
    states[lhs] = states[states.length - 1];
    states.pop();

	pr_remove(pr, source);
        """
        self.contract.add_function(Function("apply_end", [Variable("states", "STATES[] storage"), Variable("pr", "PruneRelation storage"), Variable("lhs","uint256") ], apply_end_body, ""))

 
        apply_send_receive_body = """
    STATES source = states[lhs];

    states[lhs] = rhs;

	// remove all the alternatives from the prune relation
	STATES[] memory to_prune = pr.to_prune[source];	        
	for (uint idx=0; idx<to_prune.length; idx++) {
		pr_remove(pr, to_prune[idx]);
		states_arr_remove(states, to_prune[idx]);
	}
	// remove also the source state from the prune relation
	pr_remove(pr, source);
        """
        self.contract.add_function(Function("apply_send_receive", [Variable("states", "STATES[] storage"), Variable("pr", "PruneRelation storage"), Variable("lhs","uint256"), Variable("rhs", "STATES")], apply_send_receive_body, ""))


        a_to_s_parts = [ f"if (a == ACTIONS.{ k }) {{ return '{v}'; }}" for k,v in self._actions.items() ]
        action_to_string_body = " else ".join(a_to_s_parts) + " else return '??';"

        self.contract.add_function(Function("action_to_string", [Variable("a","ACTIONS")], action_to_string_body, "pure returns (string memory)"))

        p_to_s_parts = [ f"if (p == PARTICIPANTS.{ p }) {{ return '{p}'; }}" for p in self._participants ] 
        participant_to_string_body = " else ".join(p_to_s_parts) + " else return '??';"
        self.contract.add_function(Function("participant_to_string", [Variable("p","PARTICIPANTS")], participant_to_string_body, "pure returns (string memory)"))

        
        task_to_string_body = f"""
            string memory initiator = participant_to_string(t.initiator);
            string memory action = action_to_string(t.action);
            string memory target = participant_to_string(t.target);

            return string(abi.encodePacked(initiator, action, target));

        """
        self.contract.add_function(Function("task_to_string", [Variable("t", "Task memory")], task_to_string_body, "pure returns (string memory)"))

        task_arr_to_string_body = """
    string[] memory result = new string[](ar.length);
    for (uint idx=0; idx<ar.length; idx++) {
        Task memory t = ar[idx];
        
        //if (idx > 0) {
        //    result = string(abi.encodePacked(result, ", "));
        //}

        //result = string(abi.encodePacked(result, task_to_string(t)));
        result[idx] = task_to_string(t);
    }

    return result;
        """
        self.contract.add_function(Function("task_arr_to_string", [Variable("ar", "Task[] memory")], task_arr_to_string_body, "pure returns (string[] memory)"))



    def create_contracts(self):

        for p, sc in self._local_types_contracts.items():
            self.contract.add_contract(sc)

        return self.contract   


    def create_structs(self):

        self.contract.add_struct(Struct("Task", [ ("initiator", "PARTICIPANTS"), ("action", "ACTIONS"), ("target", "PARTICIPANTS")  ]))
        self.contract.add_struct(Struct("PruneRelation", [ ("keys", "STATES[]"), ("to_prune", "mapping(STATES => STATES[])")  ]))


    def create_enums(self):

        #breakpoint()
        states = sorted(map(str, self._gt.state_vars)) # [ "a", "b", "c" ]
        self.contract.add_enum(Enum("STATES", states, ", "))

        self.contract.add_enum(Enum("ACTIONS", self._actions.keys()))
        self.contract.add_enum(Enum("PARTICIPANTS", sorted(self._participants)))


