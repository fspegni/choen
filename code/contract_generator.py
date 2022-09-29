from bpmn_parser.models import Choreography
from contracts import Contract, Variable, Function, Constructor
import rei
import nfa
import os
from django.conf import settings


class ContractGenerator:
    
    def setUp(self):

        choreographies = [
            ("diagram", "diagram.bpmn", ),
            ("diagram_minimal", "diagram_minimal.bpmn"),
            ("diagram_basic", "diagram_basic.bpmn"),
            ("diagram_gateways", "diagram_gateways.bpmn", ),
            ("diagram_gateways_mismatch", "diagram_gateways_mismatch.bpmn", ),
            ("diagram_gateways_dangling", "diagram_gateways_dangling.bpmn", ),
            ("diagram_gateways_nested", "diagram_gateways_nested.bpmn", ),
            ("diagram_gateways_nested_intermediate", "diagram_gateways_nested_with_intermediate_task.bpmn", ),
            ("diagram_gateways_nested_inclusive", "diagram_gateways_nested_inclusive.bpmn", ),
            ("diagram_gateways_nested_dangling", "diagram_gateways_nested_dangling.bpmn", ),

        ]

        for name, filename in choreographies:
            c:Choreography = Choreography()
            c.name = name
            c.resource = os.path.join(settings.MEDIA_ROOT, filename)
            c.save()
            
    def createContract(self, n : nfa.NFA):
        assert n is not None, f"Expected not-null nfa to build a contract"
        #nfa : NFA
        
        #if (choreographyName == None and n == None):
        #    raise Exception("A choreography name or a NFA must be specified.")
        #elif (choreographyName != None):
        #    choreography:Choreography = Choreography.objects.get(name=choreographyName)
        #    r, match = rei.ChoToRei(choreography)
        #    self.nfa = NFA.ReiToNFA(r)
        #else:
        #    nfa = n

        #c : Contract = Contract(f"""{''.join(elem.capitalize() for elem in n.__name__.split("_"))}NFA""","0.7.6")
        #c : Contract = Contract(f"{n.name}","0.7.6")
        c : Contract = Contract("NFA")
        
        #Smart contract variables
        c.add_attribute(Variable("states","string[]","",list(map(lambda s: s.id, n.states))))
        c.add_attribute(Variable("tmpStates","string[]"))
        c.add_attribute(Variable("initialState", "string","",'"'+str(n.initial.id)+'"'))
        c.add_attribute(Variable("finalStates", "string[]","",list(map(lambda f: f.id, n.final))))
        c.add_attribute(Variable("currentStates", "string[]"))
        c.add_attribute(Variable("message", "string[]"))
        c.add_attribute(Variable("epsilon","string"))
        c.add_attribute(Variable("start","bool"))
        c.add_attribute(Variable("end","bool"))
        c.add_attribute(Variable("transitions", "mapping(string => mapping(string => string[]))"))

        #Smart contract constructor
        constructorBody = ""
        transitionsDict = {}
        for t in n.transitions:
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

        c.add_constructor(Constructor([], constructorBody))

        #Smart contract functions
        c.add_function(Function("strCompare",
                                [Variable("stringA", "string", "memory"), Variable("stringB", "string", "memory")],
                                "return keccak256(abi.encodePacked(stringA)) == keccak256(abi.encodePacked(stringB));",
                                "private",
                                "bool"))

        c.add_function(Function("contains",
                        [Variable("s","string","memory"), Variable("states","string[]","memory")],
                        """for (uint i = 0; i < states.length; i++) {
    if (strCompare(s,states[i])) {
        return true;
    }
}
return false;""",
                        "private",
                        "bool"))

        c.add_function(Function("checkInitialAndFinalStates",
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

        c.add_function(Function("union",
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

        c.add_function(Function("e_closure",
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

        c.add_function(Function("getStates",
                                [],
                                "return states;",
                                "public view",
                                "string[] memory"))
        
        c.add_function(Function("getCurrentStates",
                                [],
                                "return currentStates;",
                                "public view",
                                "string[] memory"))
        
        c.add_function(Function("getFinalStates",
                                [],
                                "return finalStates;",
                                "public view",
                                "string[] memory"))

        c.add_function(Function("isFinal",
                                [],
                                "return end;",
                                "public view",
                                "bool"))

        c.add_function(Function("isInitial",
                                [],
                                "return start;",
                                "public view",
                                "bool"))

        c.add_function(Function("getMessage",
                                [],
                                "return message;",
                                "public view",
                                "string[] memory"))

        c.add_function(Function("transitionFrom",
                                [Variable("state","string","memory"), Variable("label","string","memory")],
                                "return transitions[state][label];",
                                "public",
                                "string[] memory"))

        c.add_function(Function("transition",
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
        
        c.add_function(Function("checkEnabledTransitions",
                        [Variable("symbol","string","memory")],
                        """for (uint i = 0; i < currentStates.length; i++) {
    string[] memory s_reached = transitionFrom(currentStates[i], symbol);
    if (s_reached.length > 0) return true;
    //reached = union(reached, s_reached); 
}
return false;""",
                        "public",
                        "bool"))
        
        return c
    
    """def compileContract(self, contract: Contract):
        return contract.compile()"""

    
