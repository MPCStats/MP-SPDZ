#!/usr/bin/python3

import sys

sys.path.append('.')

from client import *
from domains import *

client_id = int(sys.argv[1])
n_parties = int(sys.argv[2])
input_value = int(sys.argv[3])

client = Client(['localhost'] * n_parties, 14000, client_id)

for socket in client.sockets:
    os = octetStream()
    os.store(0)
    os.Send(socket)

def hex_to_int(hex):
    return int(hex, 16)
def reverse_bytes(integer):
    # Convert integer to bytes, assuming it is a 32-bit integer (4 bytes)
    byte_length = (integer.bit_length() + 7) // 8 or 1
    byte_representation = integer.to_bytes(byte_length, byteorder='big')
    
    # Reverse the byte order
    reversed_bytes = byte_representation[::-1]
    
    # Convert the reversed bytes back to an integer
    reversed_integer = int.from_bytes(reversed_bytes, byteorder='big')
    
    return reversed_integer

def run(x):
    nonce = "2a0ffcbec6f9338b582694ed46504445e59f3159ad6b7cb035325450ccb31213"
    client.send_private_inputs([x, reverse_bytes(hex_to_int(nonce))])
    print("finish sending private inputs")
    output = client.receive_outputs(1)[0]
    print("commitment: ", hex(reverse_bytes(output)))
# running two rounds
# first for sint, then for sfix
run(input_value)
# run(bonus * 2 ** 16)
