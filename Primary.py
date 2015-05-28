import threading
from flask import Flask
from flask import request
import requests

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

targets_process = []
process_lock = threading.Lock()

targets_processing = []
processing_lock = threading.Lock()

targets_processed = []
queue = []
processed_lock = threading.Lock()

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
        print node.ip.split(':')
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
    return requests.get('http://' + node.ip + '/target/' + target)

'''
api based methods :: MAIN THREAD
'''

# receive results of a target request, should move target out
# of processind and into processed, should also wake up the
# management thread
@app.route('/result', methods = ['POST', 'GET'])
def receive_result():
    print request.get_data()
    data = eval(request.get_data())
    target = data['target']
    connections = data['connections']

    processing_lock.acquire()
    processed_lock.acquire()

    targets_processing.remove(target)
    targets_processed.append(target)
    queue.extend(connections)

    processed_lock.release()
    processing_lock.release()

    node = find_node_by_ip(request.remote_addr)
    node.status = data['status']
    node.target = None
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
    print 'Initing manager...\n'
    down_nodes = handshake_nodes()
    print 'Down nodes:', len(down_nodes)
    print down_nodes

    print '\nStarting user:', targets_process[0]
    print 'Target user:', goal

    while len(targets_process) > 0:
        if targets_process[0] == None:
            targets_process.pop(0)
            manager_bfs_sema.acquire()
        if process_next_target() == False:
            manager_node_sema.acquire()

'''
BFS stuff :: THREAD 2
'''

parent_nodes = {}

# standard bfs, use processed list as queue, tracks depth with
# sentinel nodes, sleeps when sentinel encountered, woken up by
def bfs():
    return

if __name__ == '__main__':
    targets_process.append('scrub_lord')
    targets_process.append(None)
    goal = 'rolledback'

    with open('replicates.ini', 'r') as in_file:
        config = eval(in_file.read())
        for ip in config['replicate_ips']:
            nodes.append(Replicate(ip))

    manager = threading.Thread(target = init_manager)
    manager.start()
    print 'runnin app'
    app.run(debug = False, host = '0.0.0.0')
