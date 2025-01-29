Note that we're working with 256-bit integer, resulting in 320-bit prime number, which is greater than 256 bit. Hence need to write MOD = -DGFP_MOD_SZ=5 into CONFIG.mine

**Test Flow**

1. Initiate the server for the first time

   ```
   make -j8 <protocol>-party.x
   Scripts/setup-ssl.sh <nparties>
   Scripts/setup-clients.sh <nclients>
   ./compile.py demo_core_initiate -F 256
   PLAYERS=<nparties> Scripts/<protocol>.sh demo_core_initiate
   ```

2. Interaction during receiving private input
   2.1 On Computation server side, run as follows to keep listening to the private input the client's going to provide. Note that these servers, individually, already hardcode into .mpc file, the corresponding delta & zero encoding values from the tlsn proof of the client who is providing input.

   ```
   ./compile.py demo_core_save -F 256
   PLAYERS=<nparties> Scripts/<protocol>.sh demo_core_save
   ```

   2.2 On Client side who's gonna provide private input, run following file to provide both the private input and the private nonce. Once he provides the input and the computation servers compute and store his commitment successfully, the client who provides input will receive the commitment back, which they can check with their own commitment in tlsn proof. (TODO: Need to figure out what if it doesn't match.)

   ```
   python3 DevConDemo/demo-client-input.py <client_id> <nparties> input_value
   ```

3. Interaction during querying computation
   2.1 On Computation server side, run as follows to keep listening to the client asking for computation by the computation index (which is public)

   ```
   ./compile.py demo_core_query -F 256
   PLAYERS=<nparties> Scripts/<protocol>.sh demo_core_query
   ```

   2.2 On Client side who's gonna query computation, run following file to receive the result of the computation and the corresponding commitments of all private inputs. (TODO: Figure out if this step is necessary and how to make it make more sense)

   ```
   python3 DevConDemo/demo-client-output.py <client_id> <nparties> computation_index
   ```
