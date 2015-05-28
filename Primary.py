import threading
from flask import Flask
from flask import request
import requests
from os import _exit

app = Flask(__name__)

class Status:
    AVAILABLE = 0
    BUSY = 1
    DOWN = 2
    UNKNOWN = 3

class Replicate(object):

    def __init__(self, ip='0.0.0.0'):
        self.ip = ip
        self.status = Status.UNKNOWN
        self.target = None

nodes = []
goal = ''
depth = 0

targets_process = []
process_lock = threading.Lock()

targets_processing = []
processing_lock = threading.Lock()

queue = []
queue_lock = threading.Lock()

visited = set()

manager_node_sema = threading.Semaphore(0)
manager_bfs_sema = threading.Semaphore(0)
bfs_sema = threading.Semaphore(0)

'''
Utility methods
'''

code_strs = ['available', 'busy', 'down', 'unknown']

def status_to_str(code):
    return code_strs[code]

def find_node_by_ip(ip):
    for node in nodes:
        if node.ip.split(':')[0] == ip:
            return node
    return None

'''
request based methods :: NO THREAD, JUST CALLED BY THREAD 1
'''

# ping a single node
def ping_node(node):
    return requests.get('http://' + node.ip + '/status')

# confirm connection to and status of all nodes, updates
# node list as needed, returns a list of all nodes who are down
def handshake_nodes():
    print 'Performing handshake.'
    down_node_ips = []

    for node in nodes:
        print 'Contacting node:', node.ip
        result = ping_node(node)
        if result.status_code == 404:
            node.status = Status.DOWN
            node.target = None
        elif result.status_code > 299:
            node.status = Status.UNKNOWN
            node.target = None
        else:
            node.status = result.json()['status']
            node.target = result.json()['target']

        if node.status == Status.DOWN:
            down_node_ips.append(node.ip)

        print 'Status :', status_to_str(node.status)
        print 'Target :', node.target, '\n'

    return down_node_ips

# send username to a node
def send_target(node, target):
    print 'Sending', target, 'to', node.ip
    return requests.get('http://' + node.ip + '/target/' + target)

'''
api based methods :: MAIN THREAD
'''

# receive results of a target request, should move target out
# of processind and into processed, should also wake up the
# management thread
@app.route('/result', methods = ['POST', 'GET'])
def receive_result():
    data = eval(request.get_data())
    target = data['target']
    connections = data['connections']
    print 'Receiving results for', target

    processing_lock.acquire()
    queue_lock.acquire()

    targets_processing.remove(target)
    queue.append(connections)

    queue_lock.release()
    processing_lock.release()

    node = find_node_by_ip(request.remote_addr)
    node.status = data['status']
    node.target = None

    bfs_sema.release()
    manager_node_sema.release()

    return ''

'''
replicate management methods :: THREAD 1, WOKEN/STARTED BY MAIN THREAD
'''

# pull target out of to_process and assign to a node and return true
# or return false
def process_next_target():
    for node in nodes:
        if node.status == Status.AVAILABLE:
            process_lock.acquire()
            processing_lock.acquire()

            to_send = targets_process.pop(0)
            result = send_target(node, to_send)
            node.status = result.json()['status']
            targets_processing.append(to_send)

            processing_lock.release()
            process_lock.release()
            return True

    return False

# init management thread
def init_manager():
    global depth

    print 'Initing manager...\n'
    down_nodes = handshake_nodes()
    print 'Down nodes:', len(down_nodes)
    print down_nodes

    print '\nStarting user:', targets_process[0]
    print 'Target user:', goal

    while True:
        print '\nAttempting target processing.'
        if len(targets_process) == 0:
            print 'Nothing to process. Need to wait for BFS.'
            manager_bfs_sema.acquire()
            print 'Manager waking up because things need to be processed.'
        if process_next_target() == False:
            print 'No nodes left. Waiting for a result to come in.'
            manager_node_sema.acquire()
            print 'Result returned, manager trying to process targets now.'

'''
BFS stuff :: THREAD 2
'''

parent_nodes = {}

# standard bfs, use processed list as queue, tracks depth with
# sentinel nodes, sleeps when sentinel encountered, woken up by
def bfs():
    global goal

    while True:
        print '\nIterating BFS.'
        if len(queue) == 0:
            print 'No connections to iterate over, waiting for a result to return.'
            bfs_sema.acquire()

        queue_lock.acquire()
        connections_list = queue.pop(0)
        queue_lock.release()

        for connection in connections_list:
            user = connection['connection']
            if user == goal:
                _exit(1)
            elif user not in visited:
                process_lock.acquire()
                targets_process.append(user)
                visited.add(user)
                process_lock.release()
                print 'Wake up the manager,', len(targets_process), 'targets need to be processsed.'
                manager_bfs_sema.release()


if __name__ == '__main__':
    targets_process.append('rolledback')
    goal = 'scrub_lord'

    with open('replicates.ini', 'r') as in_file:
        config = eval(in_file.read())
        for ip in config['replicate_ips']:
            nodes.append(Replicate(ip))

    manager = threading.Thread(target = init_manager)
    manager.start()
    print 'manager started'
    path_finder = threading.Thread(target = bfs)
    path_finder.start()
    print 'bfs started, running app'
    app.run(debug = False, host = '0.0.0.0')
