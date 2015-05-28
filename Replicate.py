from json import dumps
from Primary import Status
from flask import Flask
from flask import json
from flask import request
from flask import Response
import threading
import requests
import praw
import time

app = Flask(__name__)

user_agent = 'Test PRAW app by /u/rolledback'
r = praw.Reddit(user_agent = user_agent)
limit = None

status = Status.AVAILABLE
target = None

def verify_name(name, check_name = ''):
    return name != None and name != u'None' and name != u'[deleted]' and name != check_name

def handle(func, *args, **kwargs):
    attempts = 5
    start = time.time()
    res = []
    print str(func)
    while attempts > 0:
        try:
            res = func(*args, **kwargs)
            break
        except Exception as e:
            print str(attempts) + ' Error, attempting sleeping.'
            attempts = attempts - 1
            print str(e)
            time.sleep(2)
    print 'Handle runtime: ' + str(time.time() - start)
    return res

def process_user(username, address):
    global status, target
    user = handle(r.get_redditor, username)
    connections = []

    for entry in handle(user.get_overview, limit = limit):
        if isinstance(entry, praw.objects.Comment):
            result = parse_comment(user.name, entry)
        elif entry.num_comments > 0:
            result = parse_submission(user.name, entry)
        if result != None:
            connections.append(result)

    status = Status.AVAILABLE
    target = None

    data = {'connections': connections, 'target': username, 'status': Status.AVAILABLE}
    req = requests.post('http://' + address + ':5000/result', data = dumps(data))

def parse_comment(name, comment):
    if comment.is_root and verify_name(comment.link_author):
        return {'connection': comment.link_author, 'parent': name, 'permalink': comment.link_url}
    return None

def parse_submission(name, submission):
    handle(submission.replace_more_comments, limit = limit)
    for comment in submission.comments:
        if comment.author != None and verify_name(comment.author.name, name):
            return {'connection': comment.author.name, 'parent': name, 'permalink': submission.permalink}
    return None

@app.route('/status')
def get_status():
    return json.jsonify({'status': status, 'target': target})

@app.route('/target/<name>', methods = ['GET'])
def rec_target(name):
    global status, target
    if status != Status.BUSY and target == None:
        status = Status.BUSY
        target = name
        threading.Thread(target = process_user, args = (name, request.remote_addr)).start()
        return json.jsonify({'status': status})
    else:
        return Response(status = 503)

if __name__ == '__main__':
    with open('config.ini', 'r') as in_file:
       config = eval(in_file.read())
       limit = config['limit']
    app.run(debug = False, host = '0.0.0.0', port = 5001)
