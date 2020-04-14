import argparse, socket, pathlib
import pickle
import sys
import time
from itertools import islice
import collections
import math
import os.path
import copy
import threading

#Global variables defined to maintain information about the router.

# Maximum bytes received by UDP
MAX_BYTES = 65535
# Flag to see if router is updated with  correct commandline arguments
router_update_flag = False
router_name = ''
port_details = dict()
# link_cost maintains the information about the routers neighbours
link_cost = dict()
# The routing table which gets forwarded to the neighbours
vector_table = dict()
# Keeps track of the next hop
hop_table = dict()
dat_file = ''
host = '127.0.0.1'
udp_port = 0
# This is a duplicate copy to compare if there have been link cost changes
updated_link_cost = dict()


# This table calculates the values in the routing table depending upon the Bellman Ford equation
def vector_routing(data, port):
    global vector_table
    global hop_table
    global updated_link_cost
    global link_cost
    # Check for input data neighbours and add to your own routing table with inf value
    missing = set(data.keys()) - set(vector_table.keys())
    if missing:
        for key in missing:
            vector_table[key] = float(math.inf)
            hop_table[key] = key
    try:
        vector_name = [key for key in port_details if (port_details[key] == port)][0]
        updated_link_cost = read_dat_file()
        # Check if there has been any changes in the input .dat file
        if link_cost == updated_link_cost:
            for key in vector_table:
                if vector_table[vector_name] >= link_cost[vector_name]:
                    temp = [vector_table[key], (link_cost[vector_name] + data[key])]
                else:
                    temp = [vector_table[key], (vector_table[vector_name] + data[key])]
                new_val = min(temp)
                old_val = vector_table[key]
                if new_val < old_val:
                    hop_table[key] = vector_name
                    vector_table[key] = new_val

        # If changes, initialize vector table with initial link costs and forward it to neighbours for recalculation
        else:
            link_cost = copy.deepcopy(updated_link_cost)
            initialize_routing()
    except:
        return


# Print output in desired format
def print_output():
    count = 1
    while True:
        print(f"OUTPUT #{count}")
        try:
            for key in vector_table:
                if key != router_name:
                    print(f"Shortest path {router_name}-{key}: next hop {hop_table[key]}  cost {vector_table[key]}")
            count = count + 1
            time.sleep(15)
        except:
            continue


# Initialize routing table before sending to the neighbours.
def initialize_routing():
    global vector_table
    vector_table = copy.deepcopy(link_cost)
    global hop_table
    for key in link_cost:
        hop_table[key] = key


# Sender function serializes routing table and sends it to the neighbours
def sender(sock, n_ports):
    initialize_routing()
    while True:
        data_string = pickle.dumps(vector_table, -1)
        sock.sendto(data_string, (host, n_ports))
        time.sleep(15)


# Receiver function receives serialized data and deserializes it to send to the vector_routing function to recalculate the vector table
def receiver(sock, port):
    initialize_routing()
    while True:
        try:
            # GET ROUTING TABLE FROM NEIGHBOURS
            data, address = sock.recvfrom(MAX_BYTES)
            # send data to vector routing function
            vector = pickle.loads(data)
            vector_routing(vector,address[1])
        except:
            continue


# Validate the commandline parameters and add port and router details to the port_info.pickle file.
def get_router_details():
    global router_update_flag
    global router_name
    if not os.path.isfile(dat_file):
        print("This .dat file is not present in the current directory.")
        return
    else:
        router_name = dat_file.split('.')[0]
        router_port = dict()
        router_port[router_name] = udp_port
        try:
            new_dict = pickle.load(open("port_info.pickle", "rb"))
            if router_name in new_dict:
                print("Router is already running on port: ", new_dict[router_name])
                return
            else:
                if udp_port in new_dict.values():
                    print("Port number already in use.")
                    return
            router_update_flag = True
            new_dict.update(router_port)
            pickle.dump(new_dict, open("port_info.pickle", "wb"))
        except:
            router_update_flag = True
            pickle.dump(router_port, open("port_info.pickle", "wb"))
        return


# Get the port information of the routers currently in the network
def get_port_details():
    global port_details
    try:
        port_details = pickle.load(open("port_info.pickle", "rb"))
    except:
        return


# This function reads the .dat file and updates the initial link cost table as and when called
def read_dat_file():
    neighbours = dict()
    with open(dat_file, 'r') as f:
        first_line = f.readline()
        for line in islice(f, 0, None):
            neighbours[line.rstrip().split()[0]] = float(line.rstrip().split()[1])
        neighbours[router_name] = 0
    return neighbours


def main():
    global udp_port
    global dat_file
    global link_cost
    if len(sys.argv) != 3:
        print("Either UDP port number or .dat file is missing.")
        return
    udp_port = int(sys.argv[1])
    dat_file = sys.argv[2]
    try:
        get_router_details()
        if not router_update_flag:
            sys.exit(0)
    except:
        return
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((host, udp_port))
    threading.Thread(target=receiver, args=(sock, udp_port)).start()
    started =[]
    print_flag = True
    while True:
        # Check if the neighbouring router has entered the network
        get_port_details() #To check if all hosts have joined the network
        link_cost = read_dat_file() #To see what neighbours this router has so that threads of working neighbours can be initiated
        neighbours_only = list(link_cost.keys())
        neighbours_only.remove(router_name)
        if print_flag:
            threading.Thread(target=print_output).start()
            print_flag = False
        for router in neighbours_only:
            if router in port_details and router not in started:
                port_to_send = port_details[router]
                threading.Thread(target=sender, args=(sock, port_to_send)).start()
                started.append(router)
        if collections.Counter(started) == collections.Counter(neighbours_only):
            break

main()