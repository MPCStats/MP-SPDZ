## Benchmarking stats operations with client interface

This folder is for comparing & contrast the calculation of statistics function with and without client interface where client does nothing but getting the output. See more about client-interface[here](https://mp-spdz.readthedocs.io/en/latest/client-interface.html#client-interface)

### How to run

**Setup**

We Input private data to computing servers (server parties that perform MPC calculation) in Player-Data. For example, if we consider using 2 servers, we can put 0 1 2 3 170 160 152 180 in Player-Data/Input-P0-0, and 3 0 4 5 50 60 70 100 in Player-Data/Input-P1-0

**Case 1 : 2 Computing Servers (without any client)**

Run the following commands (as shown in main README of the repo )

```
./compile.py stats-noclient
Scripts/../semi-party.x 0 stats-noclient -pn 17090 -h localhost -N 2 -OF .
Scripts/../semi-party.x 1 stats-noclient -pn 17090 -h localhost -N 2 -OF .
```

Note that here, we only delivers output to the 2nd client by modifying stats-noclient.mpc a bit as seen in comment, to make its behavior close to client interface

**Case 2 : 3 Computing Servers (without any client)**

Run the following commands (as shown in main README of the repo )

```
./compile.py stats-noclient
Scripts/../semi-party.x 0 stats-noclient -pn 17090 -h localhost -N 3 -OF .
Scripts/../semi-party.x 1 stats-noclient -pn 17090 -h localhost -N 3 -OF .
Scripts/../semi-party.x 2 stats-noclient -pn 17090 -h localhost -N 3 -OF .
```

Note that here, we only delivers output to the 2nd client by modifying stats-noclient.mpc a bit as seen in comment, to make its behavior close to client interface

**Case 3: 2 Computing Servers + 1 Client**

Run the following commands

```
make stats-client.x
./compile.py stats-client
Scripts/setup-ssl.sh 2
Scripts/setup-clients.sh 1
PLAYERS=2 Scripts/semi.sh stats-client
./stats-client.x 0 2 1
```

Commands above do the following

- make stats-client.x : Run Makefile to handle stats-client.cpp in folder ExternalStats
- ./compile.py stats-client: Compile stats-client.mpc file in Programs/Source
- Scripts/setup-ssl.sh 2: Create triple shares for each party (spdz engine). 2 indicates 2 computing servers
- Scripts/setup-clients.sh 1: Create SSL keys and certificates for clients. 1 indicates 1 client
- PLAYERS=2 Scripts/semi.sh stats-client: Run server engines
- ./stats-client.x 0 2 1: Run client. 0 indicates client index 0, 2 indicates the number of party, 1 indicates finish (dont need to wait for more clients)

### BenchMark

**Case 1 : 2 Computing Servers (without any client)**

- Data sent = 3.28973 MB in ~154 rounds (party 0 only; use '-v' for more details)
  Global data sent = 6.59176 MB (all parties)

**Case 2 : 3 Computing Servers (without any client)**

- Data sent = 25.6026 MB in ~305 rounds (party 2 only; use '-v' for more details)
  Global data sent = 76.9298 MB (all parties)

**Case 3 : 2 Computing Servers + 1 Client**

- Data sent = 3.28978 MB in ~158 rounds (party 0 only; use '-v' for more details)
  Global data sent = 6.59185 MB (all parties)

Comparing case 1 with case 3, we can see that the overhead is very small, which makes sense since the trust assumption of client-interface only depends on the computing servers

Now considering case 2, we can see that introducing another computating server for the sake of just getting output costs so so much. This trade-off comes from the fact that we get more secure trusted assumption, since we can always trust ourselves.

### Some weird behavior

- When we run without client version with main.py, the amount of data skyrocket to - Data sent = 4.77346 MB in ~214 rounds (party 0 only; use '-v' for more details)
  Global data sent = 9.55921 MB (all parties)
  This is likely due to

  ```
  compiler = Compiler()
  compiler.register_function(PROGRAM_NAME)(computation)
  compiler.compile_func()
  ```

  inside main.py

## Notes

- We use sfix instead of sint in our program because stats operation likely results in floating number, hence the result the client receives is already multiplied by the scale. For example, if the result is 55., the client will receive 55\*2^16 ~ 3604480
- Anyway, by default, sfix is also faster than sint: https://github.com/data61/MP-SPDZ/issues/1400#issuecomment-2107550939
