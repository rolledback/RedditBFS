import praw
import pprint
import time
import traceback
import gc

user_agent = 'Test PRAW app by /u/rolledback'
r = praw.Reddit(user_agent = user_agent)
parent_nodes = {}

def verify_name(name, check_name = ''):
    return name != None and name != u'None' and name != u'[deleted]' and name != check_name

def print_path(end):
    print end
    while end in parent_nodes:
        print parent_nodes[end]['parent'] + ' via ' + parent_nodes[end]['permalink']
        end = parent_nodes[end]['parent']

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

def bfs(start, end):
    depth = 0
    count = 0
    visited = set()
    visited.add(start)
    queue = []
    queue.append(start)
    queue.append(None)

    while(len(queue) > 0):
        print 'Queue length:', len(queue)

        if queue[0] == None:
            depth = depth + 1
            queue.append(None)
            queue.pop(0)

        user = handle(r.get_redditor, queue.pop(0))
        if user != []:
            print 'Current: ' + user.name + ', at depth:', depth
            print 'Users viewed:', count
            count = count + 1

            new_nodes = []
            try:
                start = time.time()
                print start
                new_nodes = process_user(user)
                end = time.time()
                print 'Num connections:', len(new_nodes)
                print 'Processing time:', (end - start)
            except Exception as e:
                print 'Something broke.'
                print str(e)
                print traceback.format_exc()

            for entry in new_nodes:
                name = entry[0]
                if name not in visited:
                    parent_nodes[name] = entry[1]
                    if name == end:
                        return print_path(end)
                    visited.add(name)
                    queue.append(name)
            print '\n'

    print 'No path'
    return

def process_user(user):
    connections = []
    result = None
    for entry in handle(user.get_overview, limit = None):
        if isinstance(entry, praw.objects.Comment):
            result = parse_comment(user.name, entry)
        elif entry.num_comments > 0:
            result = parse_submission(user.name, entry)
        if result != None:
            connections.append(result)
    return connections

def parse_comment(name, comment):
    if comment.is_root and verify_name(comment.link_author):
        return (comment.link_author, {'parent': name, 'permalink': comment.link_url})
    return None

def parse_submission(name, submission):
    handle(submission.replace_more_comments, limit = None)
    for comment in submission.comments:
        if comment.author != None and verify_name(comment.author.name, name):
            return (comment.author.name, {'parent': name, 'permalink': submission.permalink})
    return None

start = time.time()
bfs(u'rolledback', u'scrub_lord')
end = time.time()
interval = end - start;
print interval

