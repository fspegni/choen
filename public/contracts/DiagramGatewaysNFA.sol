
pragma solidity >= 0.7.6;
pragma abicoder v2;




contract DiagramGatewaysNFA {




	string[] states = ['pewyrmlg', 'enudxeag', 'gfuwnisl', 'edtbcqoa', 'dwjulywl', 'kbglflll', 'bkucnlof', 'aouyhtfr', 'imkgyzpp', 'wbsgkunm', 'sqahuohj'];
	string[] tmpStates;
	string initialState = "pewyrmlg";
	string[] finalStates = ['sqahuohj'];
	string[] currentStates;
	string[] message;
	string epsilon;
	bool start;
	bool end;
	mapping(string => mapping(string => string[])) transitions;

	constructor() public {
		transitions['enudxeag']['order pizza'] = ['gfuwnisl'];
		transitions['pewyrmlg'][''] = ['enudxeag'];
		transitions['dwjulywl']['New Activity'] = ['kbglflll'];
		transitions['edtbcqoa'][''] = ['bkucnlof', 'dwjulywl'];
		transitions['bkucnlof']['hand over pizza'] = ['aouyhtfr'];
		transitions['imkgyzpp']['deliver pizza'] = ['wbsgkunm'];
		transitions['aouyhtfr'][''] = ['imkgyzpp'];
		transitions['gfuwnisl'][''] = ['edtbcqoa'];
		transitions['kbglflll'][''] = ['sqahuohj'];
		transitions['wbsgkunm'][''] = ['sqahuohj'];
		
		delete tmpStates;
		tmpStates.push(initialState);
		currentStates = e_closure(tmpStates);
	}
	
	

	function strCompare(string memory stringA, string memory stringB) private returns (bool){
		return keccak256(abi.encodePacked(stringA)) == keccak256(abi.encodePacked(stringB));
	}
	
	
	function transitionFrom(string memory state, string memory label) public returns (string[] memory){
		return transitions[state][label];
	}
	
	
	function stateAlreadyExists(string memory s, string[] memory states) private returns (bool){
		for (uint i = 0; i < states.length; i++) {
		    if (strCompare(s,states[i])) {
		        return true;
		    }
		}
		return false;
	}
	
	
	function checkInitialAndFinalStates(string[] memory states) private {
		start = false;
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
		    }
	}
	
	
	function union(string[] memory arrayA, string[] memory arrayB) private returns (string[] memory){
		delete tmpStates;
		tmpStates = arrayA;
		for (uint i = 0; i < arrayB.length; i++) {
		    if(!stateAlreadyExists(arrayB[i], tmpStates)) {
		        tmpStates.push(arrayB[i]);
		    }
		}
		return tmpStates;
	}
	
	
	function e_closure(string[] memory states) private returns (string[] memory){
		delete tmpStates;
		tmpStates = states;
		bool found = (tmpStates.length > 0);
		while (found) {
		    found = false;
		    for (uint i = 0; i < tmpStates.length; i++) {
		        for (uint j = 0; j < transitions[tmpStates[i]][epsilon].length; j++) {
		            if (!stateAlreadyExists(transitions[tmpStates[i]][epsilon][j], tmpStates)) {
		                tmpStates.push(transitions[tmpStates[i]][epsilon][j]);
		                found = true;
		            }
		        }
		    }
		}
		checkInitialAndFinalStates(tmpStates);
		return tmpStates;
	}
	
	
	function getStates() public view returns (string[] memory){
		return states;
	}
	
	
	function getCurrentStates() public view returns (string[] memory){
		return currentStates;
	}
	
	
	function isFinal() public view returns (bool){
		return end;
	}
	
	
	function isInitial() public view returns (bool){
		return start;
	}
	
	
	function getMessage() public view returns (string[] memory){
		return message;
	}
	
	
	function transition(string memory label) public {
		delete tmpStates;
		for (uint i = 0; i < currentStates.length; i++) {
		    string[] memory s = transitionFrom(currentStates[i],label);
		    tmpStates = union(tmpStates, s);
		}
		require(tmpStates.length != 0);
		message.push(label);
		currentStates = e_closure(tmpStates);
	}
	
	
	function checkEnabledTransitions(string memory symbol) public returns (bool){
		for (uint i = 0; i < currentStates.length; i++) {
		    string[] memory s_reached = transitionFrom(currentStates[i], symbol);
		    if (s_reached.length > 0) return true;
		    //reached = union(reached, s_reached); 
		}
		return false;
	}
	
	
}  
