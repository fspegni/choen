
pragma solidity >= 0.7.6;
pragma abicoder v2;

contract DiagramGatewaysNFA {

	string[] states = ['oqatcupc', 'ipxfwwej', 'plxgmgty', 'witjcuwa', 'ngqltbgx', 'uozsxwqj', 'pjtotlpx', 'geeeasmo', 'rmspibnm', 'wnxpqggv', 'ufwshdhy'];
	string[] tmpStates;
	string initialState = "oqatcupc";
	string[] finalStates = ['ufwshdhy'];
	string[] currentStates;
	string[] message;
	string epsilon;
	bool start;
	bool end;
	mapping(string => mapping(string => string[])) transitions;

	constructor() public {
		transitions["ipxfwwej"]["order pizza"]=["plxgmgty"];
		transitions["oqatcupc"][""]=["ipxfwwej"];
		transitions["ngqltbgx"]["New Activity"]=["uozsxwqj"];
		transitions["witjcuwa"][""]=["ngqltbgx"];
		transitions["witjcuwa"][""]=["pjtotlpx"];
		transitions["pjtotlpx"]["hand over pizza"]=["geeeasmo"];
		transitions["rmspibnm"]["deliver pizza"]=["wnxpqggv"];
		transitions["geeeasmo"][""]=["rmspibnm"];
		transitions["plxgmgty"][""]=["witjcuwa"];
		transitions["uozsxwqj"][""]=["ufwshdhy"];
		transitions["wnxpqggv"][""]=["ufwshdhy"];
		
		delete tmpStates;
		tmpStates.push(initialState);
		currentStates = e_closure(tmpStates);
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
	
	
	function transitionFrom(string memory state, string memory label) private returns (string[] memory){
		return transitions[state][label];
	}
	
	
	function stateAlreadyExists(string memory s, string[] memory states) private returns (bool){
		for (uint i = 0; i < states.length; i++) {
		    if (keccak256(abi.encodePacked(s)) == keccak256(abi.encodePacked(states[i]))) {
		        return true;
		    }
		}
		return false;
	}
	
	
	function checkInitialAndFinalStates(string[] memory states) private {
		start = false;
		end = false;
		for (uint i = 0; i < states.length; i++) {
		    if (keccak256(abi.encodePacked(states[i])) == keccak256(abi.encodePacked(initialState))) {
		            start = true;
		        }
		        for (uint k = 0; k < finalStates.length; k++) {
		            if (keccak256(abi.encodePacked(states[i])) == keccak256(abi.encodePacked(finalStates[k]))) {
		                end = true;
		           }
		        }
		    }
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
	
	
	function transition(string memory label) public {
		delete tmpStates;
		for (uint i = 0; i < currentStates.length; i++) {
		    string[] memory s = transitionFrom(currentStates[i],label);
		    for(uint j=0; j< s.length; j++) {
		        tmpStates.push(s[j]);
		        }
		}
		require(tmpStates.length != 0);
		message.push(label);
		currentStates = e_closure(tmpStates);
	}
	
	
}  
