from web3 import Web3


class EnforcerDeployer:

    def __init__(self):
        self._w3 : Web3 = Web3(Web3.HTTPProvider("http://127.0.0.1:7545", request_kwargs={'timeout': 300}))
        self._chain_id : int = 1337
        
        self._address : str = "0x49571ac86ED47e096D3Dc0771b5c1914698FB963"
        self._private_key : str = "0x0eb579c6ab0e30aa88830490d3e9c07a8e127e7f2671b551a2123cd87bd09f1c"

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
    
     

    def __sendTransaction(self, transaction):
        # Sign the transaction
        sign_transaction = self.w3.eth.account.sign_transaction(transaction, private_key = self.private_key)
        
        # Send the transaction
        transaction_hash = self.w3.eth.send_raw_transaction(sign_transaction.rawTransaction)
        
        # Wait for the transaction to be mined, and get the transaction receipt
        transaction_receipt = self.w3.eth.wait_for_transaction_receipt(transaction_hash)

        return transaction_receipt

    def __deployContract(self, abi, bytecode, address = None):
        #compiled_c = c.compile()

        #create the contract
        contract = self.w3.eth.contract(abi=abi, bytecode=bytecode)

        nonce =  self.w3.eth.get_transaction_count(self.address)

        # build transaction
        if (address == None):
            transaction = contract.constructor().buildTransaction(
            {
                "chainId": self.chain_id,
                "gasPrice": self.w3.eth.gas_price,
                "from": self.address,
                "nonce": nonce,
            }
        )
        else:
            transaction = contract.constructor(address).buildTransaction(
            {
                "chainId": self.chain_id,
                "gasPrice": self.w3.eth.gas_price,
                "from": self.address,
                "nonce": nonce,
            }
        )

        print("Deploying contract ...")
        transaction_receipt = self.__sendTransaction(transaction)
        print(f"Done! Contract deployed to {transaction_receipt.contractAddress}")

        return transaction_receipt.contractAddress


    def deployContractNFA(self, abi, bytecode):
        return self.__deployContract(abi, bytecode)
    
    def deployContractEnforcer(self, abi, bytecode, nfa_address : str):
        return self.__deployContract(abi, bytecode, nfa_address)

    """def process_input(self, msg : str):
        contract = self.getContract()
        nonce = self.w3.eth.get_transaction_count(self.address)
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
        return result"""
