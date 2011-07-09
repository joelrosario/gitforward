import sys
import os
import re
import subprocess

GIT_REPO = sys.argv[1]
command = sys.argv[2] if len(sys.argv) > 2 else None
GIT_LOG_DATA = os.path.basename(GIT_REPO) + ".gitwalkcommits"
GIT_LOG_CURRENT = os.path.basename(GIT_REPO) + ".gitwalkcurrent"
GIT_LOG_DATA = os.path.basename(GIT_REPO) + ".gitfwd"

def to_blob(data):
	'''
	>>> to_blob({'type': 'blob', 'name': 'stuff', 'data': '123'})
	"(dp0\\nS'data'\\np1\\nS'123'\\np2\\nsS'type'\\np3\\nS'blob'\\np4\\nsS'name'\\np5\\nS'stuff'\\np6\\ns."
	'''
	import pickle
	import StringIO
	
	f = StringIO.StringIO()
	pickle.dump(data, f)
	f.seek(0)
	return f.read()

def from_blob(data):
	'''
	>>> from_blob("(dp0\\nS'data'\\np1\\nS'123'\\np2\\nsS'type'\\np3\\nS'blob'\\np4\\nsS'name'\\np5\\nS'stuff'\\np6\\ns.")
	{'type': 'blob', 'data': '123', 'name': 'stuff'}
	'''
	import pickle
	import StringIO
	
	f = StringIO.StringIO(data)
	return pickle.load(f)

def read_db():
	if not os.path.exists(GIT_LOG_DATA):
		return {}

	with open(GIT_LOG_DATA) as f:
		return from_blob(f.read())

def write_db(data):
	with open(GIT_LOG_DATA, 'w+') as f:
		return f.write(to_blob(data))

def write_db_data(key, value):
	db = read_db()
	db[key] = value
	write_db(db)

def read_db_data(key, default=None):
	db = read_db()
	if key in db:
		return db[key]

	return default

def del_db_data(key):
	db = read_db()
	if key in db: del db
	write_db(db)
	
def get_commits_from_repo():
	commits = []
	lines = []

	rawlogs = [l.strip() for l in subprocess.Popen(['git', 'log'], stdout=subprocess.PIPE, cwd=GIT_REPO).stdout.readlines()]

	for line in rawlogs:
		if re.match(r'^commit', line):
			if len(lines) > 0: commits.append(lines)
			lines = []
		lines.append(line)

	if len(lines) > 0: commits.append(lines)

	return [{'name': commit[0].split(' ')[1], 'comment': commit[commit.index("") + 1].strip() } for commit in commits][::-1]

def write_commits_to_index(commits):
	commits = get_commits_from_repo()
	commit_data = str.join('\n', [commit['name'] + ' ' + commit['comment'] + '\n' for commit in commits])
	write_db_data('commitdata', commit_data)

def get_commits_from_index():
	no_zero_length_lines = lambda l: len(l.strip()) > 0
	lines = filter(no_zero_length_lines, read_db_data('commitdata', '').split('\n'))
	return [{'name': line[0], 'comment': line[1].strip()} for line in [line.split(' ', 1) for line in lines] ]

def get_current_index(default):
	return int(read_db_data('current', default))

def write_current_index(index):
	write_db_data('current', str(index))

def unless_no_commits(fn):
	'''
	>>> commits = [{'comment': 'testcomment', 'name': 'testname'}, {'comment': 'testcomment2', 'name': 'testname2'}]
	>>> unless_no_commits(lambda x: x)([])
	{'message': 'No commit found.', 'type': 'error'}
	>>> unless_no_commits(lambda x: x)(commits)
	[{'comment': 'testcomment', 'name': 'testname'}, {'comment': 'testcomment2', 'name': 'testname2'}]
	'''
	def _(commits):
		if len(commits) == 0: return {'type': 'error', 'message': 'No commit found.'}
		return fn(commits)
	
	return _

def to_commit_index(index):
	'''
	>>> to_commit_index(10)
	{'index': '10', 'type': 'commitindex'}
	'''
	return {'type': 'commitindex', 'index': str(index)}

def error_msg(message):
	return {'type': 'error', 'message': 'Error: ' + message}

def within_bounds(commits, index):
	'''
	>>> commits = [{'comment': 'testcomment', 'name': 'testname'}, {'comment': 'testcomment2', 'name': 'testname2'}]
	>>> within_bounds(commits, 0)
	{'index': '0', 'type': 'commitindex'}
	>>> within_bounds(commits, 10)
	{'message': 'Error: Index 10 is greater than the largest commit index.', 'type': 'error'}
	>>> within_bounds(commits, -1)
	{'message': 'Error: Index -1 is less than 0.', 'type': 'error'}
	'''
	if index < 0:
		return error_msg('Index %(index)s is less than 0.' % {'index': index})
	if index > len(commits) - 1:
		return error_msg('Index %(index)s is greater than the largest commit index.' % {'index': index})
	return to_commit_index(index)

def checkout(treeish):
	try:
		proc = subprocess.Popen(['git', 'checkout', treeish], cwd=GIT_REPO, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		proc.wait()
		if proc.returncode != 0:
			print "Error running command 'git checkout " + treeish + "'"
			print "Return code: " + str(proc.returncode)
			print "Standard error:"
			print proc.stderr.read()
			sys.exit(0)
	except OSError, e:
		print "Execution failed: " + str(e)

def to_treeish(val):
	'''
	>>> commits = [{'comment': 'testcomment', 'name': 'testname'}, {'comment': 'testcomment2', 'name': 'testname2'}]
	>>> def get_current_index(default): return default
	>>> def to_treeish_test(command): return to_treeish(command)(commits)
	>>> to_treeish_test('start')
	{'index': '0', 'type': 'commitindex'}
	>>> to_treeish_test('end')
	{'index': '1', 'type': 'commitindex'}
	>>> to_treeish_test('next')
	{'index': '0', 'type': 'commitindex'}
	>>> to_treeish_test('prev')
	{'index': '0', 'type': 'commitindex'}
	'''

	def valid_commit_index(index):
		return unless_no_commits(lambda commits: within_bounds(commits, int(index)))

	commit_indices = {
		'start': valid_commit_index(0),
		'end': unless_no_commits(lambda commits: within_bounds(commits, len(commits) - 1)),
		'next': valid_commit_index(get_current_index(-1) + 1),
		'prev': valid_commit_index(get_current_index(1) - 1)
	}

	if val in commit_indices:
		return commit_indices[val]

	def defaultaction(commits):
		try:
			if len(commits) > 0: return valid_commit_index(str(int(str(val))))(commits)
			return error_msg('No commit found.')
		except ValueError:
			return {'type': 'branch', 'name': val}

	return defaultaction

def format_commit(commits, index, prefix='  '):
	'''
	>>> format_commit([{'comment': 'testcomment', 'name': 'testname'}], 0)
	'  0: testcomment'
	'''
	index_str_length = len(str(len(commits) - 1))
	format = "%(num)" + str(index_str_length) + "s"
	line = prefix + format % {'num': str(index) } + ": " + commits[index]['comment']
	return line

def format_current_commit(commits, index):
	'''
	>>> format_current_commit([{'comment': 'testcomment', 'name': 'testname'}], 0)
	'> 0: testcomment'
	'''
	return format_commit(commits, index, '> ')

def point_to_commit(commits, commit_index):
	commit_index = int(commit_index)
	commit = commits[commit_index]
	print format_current_commit(commits, commit_index)
	checkout(commit['name'])
	write_current_index(commit_index)

if __name__ == '__main__' and sys.argv[1] == '--run-tests':
	import doctest
	doctest.testmod()
elif __name__ == '__main__':
	if not os.path.exists(GIT_REPO):
		print "Directory " + GIT_REPO + " does not exist."
		sys.exit(0)
	elif not os.path.exists(GIT_REPO + "/.git"):
		print "Directory " + GIT_REPO + "/.git is not a git repository."

	if not os.path.exists(GIT_LOG_DATA) or command == 'reset':
		write_commits_to_index(get_commits_from_repo())

	commits = get_commits_from_index()
	if command == None:
		current_index = get_current_index(None)
		
		for i in range(len(commits)):
			print (format_current_commit if i == current_index else format_commit)(commits, i)
	elif command == 'reset':
		del_db_data('current')
	else:
		treeish = to_treeish(command)(commits)

		if treeish['type'] == 'commitindex':
			point_to_commit(commits, treeish['index'])
		elif treeish['type'] == 'branch':
			print "Checking out branch " + treeish['name']
			checkout(treeish['name'])
		elif treeish['type'] == 'error':
			print treeish['message']
		else:
			print "Unexpected error."
