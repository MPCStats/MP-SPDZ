/*
 * Demonstrate external client inputing and receiving outputs from a SPDZ process, 
 * following the protocol described in https://eprint.iacr.org/2015/1006.pdf.
 *
 * Provides a client to get output from statistics operation resulted from multi-party computation
 among private data owners. (No input from clients) Up to 8 clients can connect to the SPDZ engines 
 * 
 *
 * Each connecting client:
 * - sends an increasing id to identify the client, starting with 0
 * - sends an integer (0 meaining more players will join this round or 1 meaning stop the round and calc the result).
 *
 * The result is returned authenticated with a share of a random value:
 * - share of statistics result id [y]
 * - share of random value [r]
 * - share of statistics result * random value [w]
 *   statistics result is valid if ∑ [y] * ∑ [r] = ∑ [w]
 *
 * To run with 2 parties / SPDZ engines: See in README.md in this ExternalStats folder
 */

#include "Math/gfp.h"
#include "Math/gf2n.h"
#include "Networking/sockets.h"
#include "Networking/ssl_sockets.h"
#include "Tools/int.h"
#include "Math/Setup.h"
#include "Protocols/fake-stuff.h"

#include "Math/gfp.hpp"
#include "Client.hpp"

#include <sodium.h>
#include <iostream>
#include <sstream>
#include <fstream>

template<class T, class U>
void one_run( Client& client)
{
    // Run the computation
    // client.send_private_inputs<T>({salary_value});
    // cout << "Not Sent private inputs to each SPDZ engine, waiting for result..." << endl;

    // Get the result back (client_id of winning client)
    U result = client.receive_outputs<T>(1)[0];

    cout << "Satistics Result sum is : " << result << endl;
}

template<class T, class U>
void run( Client& client)
{
    one_run<T, U>( client);
}

int main(int argc, char** argv)
{
    int my_client_id;
    int nparties;
    // double salary_value;
    size_t finish;
    int port_base = 14000;

    if (argc < 4) {
        cout << "Usage is stats calculation <client identifier> <number of spdz parties> "
           << " <finish (0 false, 1 true)> <optional host names..., default localhost> "
           << "<optional spdz party port base number, default 14000>" << endl;
        exit(0);
    }

    my_client_id = atoi(argv[1]);
    nparties = atoi(argv[2]);
    finish = atoi(argv[3]);
    vector<string> hostnames(nparties, "localhost");

    if (argc > 4)
    {
        if (argc < 4 + nparties)
        {
            cerr << "Not enough hostnames specified";
            exit(1);
        }

        for (int i = 0; i < nparties; i++)
            hostnames[i] = argv[4 + i];
    }

    if (argc > 4 + nparties)
        port_base = atoi(argv[4 + nparties]);

    bigint::init_thread();

    // Setup connections from this client to each party socket
    Client client(hostnames, port_base, my_client_id);
    auto& specification = client.specification;
    auto& sockets = client.sockets;
    for (int i = 0; i < nparties; i++)
    {
        octetStream os;
        os.store(finish);
        os.Send(sockets[i]);
    }
    cout << "Finish setup socket connections to SPDZ engines." << endl;

    int type = specification.get<int>();
    switch (type)
    {
    case 'p':
    {
        gfp::init_field(specification.get<bigint>());
        cerr << "using prime " << gfp::pr() << endl;
        run<gfp, gfp>( client);
        break;
    }
    case 'R':
    {
        int R = specification.get<int>();
        int R2 = specification.get<int>();
        if (R2 != 64)
        {
            cerr << R2 << "-bit ring not implemented" << endl;
        }

        switch (R)
        {
        case 64:
            run<Z2<64>, Z2<64>>(client);
            break;
        case 104:
            run<Z2<104>, Z2<64>>(client);
            break;
        case 128:
            run<Z2<128>, Z2<64>>(client);
            break;
        default:
            cerr << R << "-bit ring not implemented";
            exit(1);
        }
        break;
    }
    default:
        cerr << "Type " << type << " not implemented";
        exit(1);
    }

    return 0;
}
