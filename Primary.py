import threading
from flask import Flask
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
target = ''

targets_process = []
process_lock = threading.Lock()

targets_processing = []
processing_lock = threading.Lock()

targets_processed = []
queue = []
processed_lock = threading.Lock()

manager_sema = threading.Semaphore(0)
bfs_sema = threading.Semaphore(0)

'''
Utility methods
'''

def status_to_str(code):
    if code == 0:
        return 'available'
    elif code == 1:
        return 'busy'
    elif code == 2:
        return 'down'
    return 'unknown'

def find_node_by_ip(ip):
    for node in nodes:
        if node.ip == ip:
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
            Node.target = None
        else:
            node.status = result['status']
            node.target = result['target']

        if node.status == Status.DOWN:
            down_node_ips.append(node.ip)

        print 'Status :', status_to_str(node.status)
        print 'Target :', node.target, '\n'

    return down_node_ips

# send username to a node
def send_target(node, target):
    payload = {'target': target}
    return requests.post('http://' + node.ip + '/target', data=payload).json()

'''
api based methods :: MAIN THREAD
'''

# receive results of a target request, should move target out
# of processind and into processed, should also wake up the
# management thread
@app.route('/result', methods = ['GET'])
def receive_result():
    request = request.json()
    target = request['name']
    connections = request['connections']

    processing_lock.acquire()
    processed_lock.acquire()

    targets_processing.remove(target)
    targets_processed.append(target)
    queue.extend(connections)

    processed_lock.release()
    processing_lock.release()

    node = find_node_by_ip(request.remote_addr)
    node.status = request['status']
    node.target = None

    manager_sema.release()

    return 200

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
            send_target(node, to_send)
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
    print 'Target user:', target

    while len(targets_process) > 0:
        if process_next_target() == False:
            print 'wait for a result...'
            manager_sema.acquire()
            print 'result! try again'

'''
BFS stuff :: THREAD 2, STARTED BY MAIN THREAD, WOKEN BY THREAD 1
'''

parent_nodes = {}

# standard bfs, use processed list as queue, tracks depth with
# sentinel nodes, sleeps when sentinel encountered, woken up by
def bfs():
    return

if __name__ == '__main__':
    print 'main'
    targets_process.append('rolledback')
    target = 'scrub_lord'
    with open('replicates.ini', 'r') as in_file:
        config = eval(in_file.read())
        for ip in config['replicate_ips']:
            nodes.append(Replicate(ip))
            print ip

    manager = threading.Thread(target = init_manager)
    manager.start()
    app.run(debug = False, host = '0.0.0.0')
