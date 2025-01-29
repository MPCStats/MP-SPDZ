#!/usr/bin/python3

import sys

sys.path.append('.')

from client import *
from domains import *

client_id = int(sys.argv[1])
n_parties = int(sys.argv[2])
computationIndex = int(sys.argv[3])
MAX_NUM_CLIENTS = 10


client = Client(['localhost'] * n_parties, 14000, client_id)

for socket in client.sockets:
    os = octetStream()
    # computationIndex is public, not need to be secret shared.
    os.store(computationIndex)
    os.Send(socket)
    
def reverse_bytes(integer):
    # Convert integer to bytes, assuming it is a 32-bit integer (4 bytes)
    byte_length = (integer.bit_length() + 7) // 8 or 1
    byte_representation = integer.to_bytes(byte_length, byteorder='big')
    
    # Reverse the byte order
    reversed_bytes = byte_representation[::-1]
    
    # Convert the reversed bytes back to an integer
    reversed_integer = int.from_bytes(reversed_bytes, byteorder='big')
    
    return reversed_integer

def run():
    output_list = client.receive_outputs(1+MAX_NUM_CLIENTS)
    print('Computation index',computationIndex, "is", output_list[0])
    for i in range(MAX_NUM_CLIENTS):
        print('commitment: ',i, 'is', hex(reverse_bytes(output_list[i+1])))

# running two rounds
# first for sint, then for sfix
run()
# run(bonus * 2 ** 16)
