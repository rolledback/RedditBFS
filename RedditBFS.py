import praw
import pprint
import time
import traceback
import gc

user_agent = 'Test PRAW app by /u/rolledback'
r = praw.Reddit(user_agent = user_agent)
parent_nodes = {}

def print_path(end):
    print end
    while end in parent_nodes:
        print parent_nodes[end]['parent'] + ' via ' + parent_nodes[end]['permalink']
        end = parent_nodes[end]['parent']

def handle(func, *args, **kwargs):
    print(str(func))
    attempts = 5
    start = time.time()
    res = []
    while attempts > 0:
        try:
            res = func(*args, **kwargs)
            break
        except Exception as e:
            print str(attempts) + ' Error, attempting sleeping.'
            attempts = attempts - 1
            print str(e) + '\n'
            time.sleep(2)
    print 'Handle lasted: ' + str(time.time() - start)
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
        start = time.time()
        print start
        print 'Queue length: ' + str(len(queue))

        if queue[0] == None:
            depth = depth + 1
            queue.append(None)
            queue.pop(0)

        user = handle(r.get_redditor, queue.pop(0))
        if user != []:
            print 'Current: ' + user.name + ', at depth: ' + str(depth)
            print 'Users viewed: ' + str(count)
            count = count + 1

            new_nodes = []
            try:
                new_nodes = parse_comments(user) + parse_submissions(user)
                print 'Num connections: ' + str(len(new_nodes))
                print 'Processing time: ' + str(time.time() - start)
            except Exception as e:
                print 'Something broke.'
                print str(e)

            for entry in new_nodes:
                name = entry[0]
                if name not in visited:
                    parent_nodes[name] = entry[1]
                    if name == end:
                        return print_path(end)
                    visited.add(name)
                    queue.append(name)
            print

    print 'No path'
    return

def parse_comments(user):
    authors = []
    print '\n----- parse_comments ------'
    print time.time()
    for comment in handle(user.get_comments):
        print 'comment', time.time()
        if comment.link_id == comment.parent_id and comment.link_author != u'[deleted]':
            if comment.link_author != user.name and comment.link_author != u'None':
                authors.append((comment.link_author, {'parent': user.name, 'permalink': comment.link_url}))
    print '---------------------------'
    return authors

def parse_submissions(user):
    commenters = []
    print '\n---- parse_submissions ----'
    print time.time()
    submissions = handle(user.get_submitted)
    for submission in submissions:
        print 'submission', time.time()
        handle(submission.replace_more_comments, threshold = 0)
        for comment in submission.comments:
            print 'comment', time.time()
            if comment.is_root and comment.author != u'[deleted]':
                if comment.author != user.name and comment.author != u'None':
                    commenters.append((comment.author, {'parent': user.name, 'permalink': submission.permalink}))
    print '--------------------------'
    return commenters

start = time.time()
bfs(u'rolledback', u'scrub_lord')
end = time.time()
interval = end - start;
print str(interval)

