# BRAIN 2023 Tutorial
In this tutorial you can reproduce all the test used to write the paper for BRAIN 2023 workshop.

## Preliminaries
For each test has been used the Ganache blockchain, but you are free to use another blockchain editing the specific parameters in the setting.py file.
Once you have activated the environment, you have to move in the bpmn2solidity folder and you can launch the CLI with the command `django-admin cli`. The following steps you have to run are the following:
1. Execute the command `init` for inizialing the application
2. Execute the command `load coreografia_semplice` to load the choreography used for all the test
3. Execute the command `start` for starting the enforcer and for generating and deploying the smart contract in the blockchain.

The choreography used is the following.
![choreography.jpg](./BRAIN2023/choreography.jpg)

## Correct execution without event buffered
The first test aims to verify a correct execution of the choreography without buffering any events, so the idea is to trigger only the receive now rules. To check what are the allowed transitions you can execute the command `/dump transitions` once the enforcer is initiated. In this case you have to obtain a the following result (except for the id of the state that are causal and change each execution):
```
 * State(epscrmlx) -[SDS?lot_ID,_quality,_ghg,_price]-> State(huhaaktq)
 * State(bzexvtlu) -[]-> State(epscrmlx)
   State(glaoaszy) -[Seller?ack]-> State(mahaqzvp)
   State(huhaaktq) -[]-> State(glaoaszy)
   State(igwepomk) -[Buyer?lot_ID,_quality,_ghg,_lot_price]-> State(xorqfcdq)
   State(mahaqzvp) -[]-> State(igwepomk)
   State(bfasuleu__bwratkop) -[CMS?coolstore_cost_query]-> State(bfasuleu__afperops)
   State(bfasuleu__bwratkop) -[EMS?energy_cost_query]-> State(jbuxtkyu__bwratkop)
   State(bfasuleu__afperops) -[]-> State(bfasuleu__vixpswlc)
   State(bfasuleu__afperops) -[EMS?energy_cost_query]-> State(jbuxtkyu__afperops)
   State(bfasuleu__vixpswlc) -[Buyer?coolstore_cost]-> State(bfasuleu__xnzticdz)
   State(bfasuleu__vixpswlc) -[EMS?energy_cost_query]-> State(jbuxtkyu__vixpswlc)
   State(bfasuleu__xnzticdz) -[EMS?energy_cost_query]-> State(jbuxtkyu__xnzticdz)
   State(jbuxtkyu__bwratkop) -[CMS?coolstore_cost_query]-> State(jbuxtkyu__afperops)
   State(jbuxtkyu__bwratkop) -[]-> State(vduzbvdn__bwratkop)
   State(jbuxtkyu__afperops) -[]-> State(vduzbvdn__afperops)
   State(jbuxtkyu__afperops) -[]-> State(jbuxtkyu__vixpswlc)
   State(jbuxtkyu__vixpswlc) -[Buyer?coolstore_cost]-> State(jbuxtkyu__xnzticdz)
   State(jbuxtkyu__vixpswlc) -[]-> State(vduzbvdn__vixpswlc)
   State(jbuxtkyu__xnzticdz) -[]-> State(vduzbvdn__xnzticdz)
   State(vduzbvdn__bwratkop) -[CMS?coolstore_cost_query]-> State(vduzbvdn__afperops)
   State(vduzbvdn__bwratkop) -[Buyer?energy_cost]-> State(ltdvcyso__bwratkop)
   State(vduzbvdn__afperops) -[]-> State(vduzbvdn__vixpswlc)
   State(vduzbvdn__afperops) -[Buyer?energy_cost]-> State(ltdvcyso__afperops)
   State(vduzbvdn__vixpswlc) -[Buyer?coolstore_cost]-> State(vduzbvdn__xnzticdz)
   State(vduzbvdn__vixpswlc) -[Buyer?energy_cost]-> State(ltdvcyso__vixpswlc)
   State(vduzbvdn__xnzticdz) -[Buyer?energy_cost]-> State(ltdvcyso__xnzticdz)
   State(ltdvcyso__bwratkop) -[CMS?coolstore_cost_query]-> State(ltdvcyso__afperops)
   State(ltdvcyso__afperops) -[]-> State(ltdvcyso__vixpswlc)
   State(ltdvcyso__vixpswlc) -[Buyer?coolstore_cost]-> State(ltdvcyso__xnzticdz)
   State(xorqfcdq) -[]-> State(bfasuleu__bwratkop)
   State(bpxdsqlg) -[BDSS?lot_price,_energy_cost,_coolstore_cost]-> State(pznutvwx)
   State(ltdvcyso__xnzticdz) -[]-> State(bpxdsqlg)
   State(qzehqjoy) -[SDS?acceptance]-> State(zncymiff)
   State(ozrmadio) -[Seller?acceptance]-> State(sydmtkhy)
   State(zncymiff) -[]-> State(ozrmadio)
   State(rihiocnj) -[]-> State(dszlzkkm)
   State(rihiocnj) -[]-> State(qzehqjoy)
   State(dszlzkkm) -[SDS?decline]-> State(solosftn)
   State(hzuupmql) -[Seller?decline]-> State(omubcauv)
   State(solosftn) -[]-> State(hzuupmql)
   State(pznutvwx) -[]-> State(rihiocnj)
   State(omubcauv) -[]-> State(oizxtrjv)
   State(sydmtkhy) -[]-> State(oizxtrjv)
```
So based on the previous transitions, a possibile stream of events to achieve our goal is the following:
```
SDS?lot_ID,_quality,_ghg,_price Seller?ack Buyer?lot_ID,_quality,_ghg,_lot_price EMS?energy_cost_query Buyer?energy_cost CMS?coolstore_cost_query Buyer?coolstore_cost BDSS?lot_price,_energy_cost,_coolstore_cost SDS?acceptance Seller?acceptance
```
Copying the stream of events in the CLI, the expected output is the following:
```
** Process input: SDS?lot_ID,_quality,_ghg,_price ... **
(* Condition rule receive now: SDS?lot_ID,_quality,_ghg,_price *)

Output message: SDS?lot_ID,_quality,_ghg,_price

** Process completed. **


** Checking for usable messages in buffer ...
(* No usable message found in buffer for current states. *)
** Checking completed. **


** Process input: Seller?ack ... **
(* Condition rule receive now: Seller?ack *)

Output message: Seller?ack

** Process completed. **


** Checking for usable messages in buffer ...
(* No usable message found in buffer for current states. *)
** Checking completed. **


** Process input: Buyer?lot_ID,_quality,_ghg,_lot_price ... **
(* Condition rule receive now: Buyer?lot_ID,_quality,_ghg,_lot_price *)

Output message: Buyer?lot_ID,_quality,_ghg,_lot_price

** Process completed. **


** Process input: EMS?energy_cost_query ... **
(* Condition rule receive now: EMS?energy_cost_query *)

Output message: EMS?energy_cost_query

** Process completed. **


** Checking for usable messages in buffer ...
(* No usable message found in buffer for current states. *)
** Checking completed. **


** Process input: Buyer?energy_cost ... **
(* Condition rule receive now: Buyer?energy_cost *)

Output message: Buyer?energy_cost

** Process completed. **


** Checking for usable messages in buffer ...
(* No usable message found in buffer for current states. *)
** Checking completed. **


** Process input: CMS?coolstore_cost_query ... **
(* Condition rule receive now: CMS?coolstore_cost_query *)

Output message: CMS?coolstore_cost_query

** Process completed. **


** Checking for usable messages in buffer ...
(* No usable message found in buffer for current states. *)
** Checking completed. **


** Process input: Buyer?coolstore_cost ... **
(* Condition rule receive now: Buyer?coolstore_cost *)

Output message: Buyer?coolstore_cost

** Process completed. **


** Checking for usable messages in buffer ...
(* No usable message found in buffer for current states. *)
** Checking completed. **


** Process input: BDSS?lot_price,_energy_cost,_coolstore_cost ... **
(* Condition rule receive now: BDSS?lot_price,_energy_cost,_coolstore_cost *)

Output message: BDSS?lot_price,_energy_cost,_coolstore_cost

** Process completed. **


** Checking for usable messages in buffer ...
(* No usable message found in buffer for current states. *)
** Checking completed. **


** Process input: SDS?acceptance ... **
(* Condition rule receive now: SDS?acceptance *)

Output message: SDS?acceptance

** Process completed. **


** Checking for usable messages in buffer ...
(* No usable message found in buffer for current states. *)
** Checking completed. **


** Process input: Seller?acceptance ... **
(* Condition rule receive now: Seller?acceptance *)

Output message: Seller?acceptance

** Process completed. **


** Checking for usable messages in buffer ...
(* No usable message found in buffer for current states. *)
** Checking completed. **

(* Ended *)
```
As said in the beginning none event is added to the enforcer buffer, but the rule receive_now is triggered every time and so the choreography moves for each event in its next state.
## Correct execution with event buffered
