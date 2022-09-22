from web3 import Web3


class EnforcerDeployer:

    def __init__(self, address : str, private_key : str, abi = "", bytecode : str = "", enforcerAddress : str = ""):
        self._w3 : Web3 = Web3(Web3.HTTPProvider("http://127.0.0.1:7545"))
        self._chain_id : int = 1337
        self._address : str = address
        self._private_key : str = private_key
        self._abi = abi
        self._bytecode : str = bytecode
        self._enforcerAddress : str = enforcerAddress

    @property
    def w3(self) -> Web3:
        return self._w3
    
    @property
    def chain_id(self) -> int:
        return self._chain_id

    @property
    def address(self) -> str:
        return self._address

    @property
    def private_key(self) -> str:
        return self._private_key
    
    @property
    def abi(self):
        return self._abi

    @abi.setter
    def abi(self, abi):
        self._abi = abi
    
    @property
    def bytecode(self) -> str:
        return self._bytecode

    @bytecode.setter
    def bytecode(self, bytecode):
        self._bytecode = bytecode

    @property
    def enforcerAddress(self) -> str:
        return self._enforcerAddress
    
    @enforcerAddress.setter
    def enforcerAddress(self, enforcerAddress):
        self._enforcerAddress = enforcerAddress 

    def sendTransaction(self, transaction):
        # Sign the transaction
        sign_transaction = self.w3.eth.account.sign_transaction(transaction, private_key = self.private_key)
        
        # Send the transaction
        transaction_hash = self.w3.eth.send_raw_transaction(sign_transaction.rawTransaction)
        
        # Wait for the transaction to be mined, and get the transaction receipt
        transaction_receipt = self.w3.eth.wait_for_transaction_receipt(transaction_hash)

        return transaction_receipt

    def deployContractNFA(self, abi: str, bytecode: str):

        #create the contract
        contract = self.w3.eth.contract(abi=abi, bytecode=bytecode)

        nonce =  self.w3.eth.getTransactionCount(self.address)

        # build transaction
        transaction = contract.constructor().buildTransaction(
            {
                "chainId": self.chain_id,
                "gasPrice": self.w3.eth.gas_price,
                "from": self.address,
                "nonce": nonce,
            }
        )

        print("Deploying contract associated with the NFA...")
        transaction_receipt = self.sendTransaction(transaction)
        print(f"Done! Contract deployed to {transaction_receipt.contractAddress}")
        
        return transaction_receipt.contractAddress

    def deployContractEnforcer(self, nfa_abi : str, nfa_bytecode : str, enforcer_abi : str, enforcer_bytecode):

        self.abi = enforcer_abi
        self.bytecode = enforcer_bytecode

        nfaAddress = self.deployContractNFA(nfa_abi, nfa_bytecode)

        #create the contract
        contract = self.w3.eth.contract(abi = enforcer_abi, bytecode = enforcer_bytecode)

        nonce = self.w3.eth.getTransactionCount(self.address)

        # build transaction
        transaction = contract.constructor(nfaAddress).buildTransaction(
            {
                "chainId": self.chain_id,
                "gasPrice": self.w3.eth.gas_price,
                "from": self.address,
                "nonce": nonce,
            }
        )
        print("Deploying Enfocer...")
        transaction_receipt = self.sendTransaction(transaction)
        print(f"Done! Enforcer deployed to {transaction_receipt.contractAddress}")

        self.enforcerAddress = transaction_receipt.contractAddress

    def getContract(self):
        contract = self.w3.eth.contract(
                address = self.enforcerAddress,
                abi = self.abi
            )
        return contract

    def process_input(self, msg : str):
        contract = self.getContract()
        nonce = self.w3.eth.getTransactionCount(self.address)
        transaction = contract.functions.process_input(msg).buildTransaction({
                        "chainId": self.chain_id,
                        "from": self.address,
                        "gasPrice": self.w3.eth.gas_price,
                        "nonce": nonce
                    })
        return contract.events.outputEvent().processReceipt(self.sendTransaction(transaction))

    def getCurrentStates(self):
        contract = self.getContract()
        result = contract.functions.getCurrentStates().call()
        return result