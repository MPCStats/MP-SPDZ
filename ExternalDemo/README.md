## First draft of DevCon Demo

This Folder is used for validating ideas/necessary properties for our application for DevCon, mainly on save & load private shares.

The computation function in this demo is the same as bankers_bonus aka determine the highest bonus value

**Current Property that this demo supports**

- Client can log in to just provide input and log out
- Same client can log in and update their value (does this make sense?)
- Anyone can log in to get output (some predetermined supported function)
- Server can store file of inputs as secret shared among them. and can read from those files.
- Our info (secret shared) of prev inputs are sustained. client_values = [45, 50, 60, …. , ]
  - If new computation are required, just run a new computation function, while downloading the saved shared

**Limitation/Constraints/ Design to consider**

- Now we set up for each client certificate beforehand —> we need to implement following feature for our edge application (browser or application?)
  - To index their client_ID properly, not skipping the order into the server (like server won’t receive input from client#3 before client#2. This assumption is required for determine_winner function (not loop MAX client since that’ll be too expensive)
  - Make sure there won’t be duplicate client_id across different devices
- Need to limit max client.. —> array size predetermined… [, , , , , , ]
- Still 1 way demo aka
  - Initiate the server, then take some inputs from multiple parties until a certain client (In example is client#0) tells us to save the private inputs across computation servers
  - Then, we can initiate the server again to download prev saved inputs, and continue
  - Now, we can’t reboot it again, because that requires us to delete the previous saved one to overwrite it
    - we cannot just extend the result, since we can update the previous value —> or we can just keep remembering the location of newest patch and keep extending
    - Or we need to be able to delete the previous saved one, to just write a completely new one
  - Note that we decide to write_to_file as Array instead of sint, due to easier management, but things can change if deemed appropriate.
- Can we save at other location?, now write_to_file & read_from_file only looks at one location. For now, we can solve this issue by remembering the location of each data. Since it just keeps appending and such anyway.
- What if updating the computation all the time—> leak every update —> use update modulo, maybe update every 10 number of clients?
- We never have connected clients that can always just broadcast —> I think this design makes sense.
- So need to have interval that the edge ping for output (maybe modulo thingy mentioned earlier
- Now in demo-client-from-file, we hardcode number_clients as 2 —> in reality, just read from some place since it’s public anyway.

Note: Data structure that support read_from_file, write_to_file stuffs, aka saving and reading for computation server

Array, Matrix, multiArray, sfix, sint, Compiler.ml.FixAveragePool2d, Compiler.ml.FixConv2d

**Main Files Involved**

- ExternalDemo/demo-client.py for client providing input
- ExternalDemo/demo-client-output.py for client requesting output
- Programs/Source/demo-client.mpc for running mpc & save by secret shared the private inputs
- Programs/Source/demo-client-from-file.mpc for re-running mpc & read from secret shared file

**Test Flow**

1. Initiate the server for the first time

   ```
   make -j8 <protocol>-party.x
   Scripts/setup-ssl.sh <nparties>
   Scripts/setup-clients.sh <nclients>
   ./compile.py demo-client
   PLAYERS=<nparties> Scripts/<protocol>.sh demo-client
   ```

2. Let clients interact

   2.1 For those wanting to provide input (with key 1), Note that my our assumption, client must provide input value ordered by client_id aka client#0 should provide input before client#1

   ```
   python3 ExternalDemo/demo-client.py <client_id> <nparties> 1 <value>
   ```

   2.2 For those wanting to request output (with key 0), note that anyone can come in to request output at anytime. You can alternate things like client#0 provides input, then someone requests output, then client#1 provides input, then client#0 update input, then someone requests output, and so on, you get the idea.

   ```
   python3 ExternalDemo/demo-client-output.py <client_id> <nparties> 0
   ```

   2.3 For admin (client#0) to tell this mpc running servers to save the secret-shared of those inputs they have and crash. (client#0 and key 99)

   ```
   python3 ExternalDemo/demo-client-output.py 0 <nparties> 99
   ```

3. Re-start the mpc servers, retrieve previously saved secret-shared inputs, and keep running.

   3.1 Restart the mpc servers

   ```
   ./compile.py demo-client-from-file
   PLAYERS=<nparties> Scripts/<protocol>.sh demo-client-from-file
   ```

   3.2 Now the clients can interact as 2.1 and 2.2 (Yet no way to save and crash this running, due to the reason mentioned above in Limitation/constraints section)
