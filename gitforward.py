import sys
import os
import re
import subprocess

import argparse

parser = argparse.ArgumentParser(description='Gitforward helps you step easily from one commit to another, using a few simple directives.')

parser.add_argument('-n', '--next', dest='next', action='store_const', const='next', help='Next commit')
parser.add_argument('-p', '--prev', dest='prev', action='store_const', const='prev', help='Previous commit')
parser.add_argument('-s', '--start', dest='start', action='store_const', const='start', help='First commit')
parser.add_argument('-e', '--end', dest='end', action='store_const', const='end', help='Last commit')
parser.add_argument('-b', '--branch', dest='branch', help='Branch to checkout')
parser.add_argument('-i', '--index', dest='index', type=int, help='Index of the commit in Gitforward\'s list to checkout')
parser.add_argument('-l', '--list', dest='list', action='store_const', const='list', help='Display all commits')
parser.add_argument('-r', '--reset', dest='reset', action='store_const', const='reset', help='Reset data')
parser.add_argument('-t', '--tests', dest='tests', action='store_const', const='tests', help='Run tests')
parser.add_argument('-o', '--repository', dest='repository', help='The git repository to work with')

cmdargs = parser.parse_args(sys.argv[1:])
cmdargs.direction = cmdargs.next or cmdargs.prev or cmdargs.start or cmdargs.end

if not cmdargs.tests and not cmdargs.repository:
	print "Please specify a repository."
	sys.exit(0)

git_repo = cmdargs.repository
git_log_data = (os.path.basename(git_repo) + ".gitfwd") if git_repo else None

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
	if not os.path.exists(git_log_data):
		return {}

	with open(git_log_data) as f:
		return from_blob(f.read())

def write_db(data):
	with open(git_log_data, 'w+') as f:
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
	if key in db: del db[key]
	write_db(db)

def execute_cmd(cmd, cwd=None):
	try:
		proc = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		proc.wait()
		if proc.returncode != 0:
			print "Error running command " + str.join(',', cmd)
			print "Return code: " + str(proc.returncode)
			print "Standout output:"
			print proc.stdout.read()
			print ""
			print "Standard error:"
			print proc.stderr.read()
			sys.exit(0)
		return proc.stdout.read()
	except OSError, e:
		print "Execution failed: " + str(e)
		sys.exit(0)

def get_commits_from_repo():
	commits = []
	lines = []

	rawlogs = [l.strip() for l in [l.strip() for l in execute_cmd(['git', 'log'], git_repo).split("\n")]]

	for line in rawlogs:
		if re.match(r'^commit', line):
			if len(lines) > 0: commits.append(lines)
			lines = []
		lines.append(line)

	if len(lines) > 0: commits.append(lines)

	return [{'name': commit[0].split(' ')[1], 'comment': commit[commit.index("") + 1].strip() } for commit in commits][::-1]

def write_commits_to_index(commits):
	commits = get_commits_from_repo()
	write_db_data('commits', commits)

def parse_commit_data(data):
	no_zero_length_lines = lambda l: len(l.strip()) > 0
	lines = filter(no_zero_length_lines, data.split('\n'))
	return [{'name': line[0], 'comment': line[1].strip()} for line in [line.split(' ', 1) for line in lines] ]

def get_commits_from_index():
	return read_db_data('commits', {})

def get_current_index(db_data, default):
	if 'current' in db_data: return int(db_data['current'])
	return default

def write_current_index(index):
	write_db_data('current', str(index))

def unless_no_commits(commits, fn):
	'''
	>>> commits = [{'comment': 'testcomment', 'name': 'testname'}, {'comment': 'testcomment2', 'name': 'testname2'}]
	>>> unless_no_commits([], lambda x: x)
	{'message': 'No commit found.', 'type': 'error'}
	>>> unless_no_commits(commits, lambda x: x)
	[{'comment': 'testcomment', 'name': 'testname'}, {'comment': 'testcomment2', 'name': 'testname2'}]
	'''
	if len(commits) == 0: return {'type': 'error', 'message': 'No commit found.'}
	return fn(commits)

def to_commit_index(index):
	'''
	>>> to_commit_index(10)
	{'index': '10', 'type': 'commitindex'}
	'''
	return {'type': 'commitindex', 'index': str(index)}

def error_msg(message):
	'''
	>>> error_msg('hello world')
	{'message': 'Error: hello world', 'type': 'error'}
	'''
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
	execute_cmd(['git', 'checkout', treeish], git_repo)

def to_treeish(val, db_data):
	'''
	>>> db_data = {'commits': [{'comment': 'testcomment', 'name': 'testname'}, {'comment': 'testcomment2', 'name': 'testname2'}, {'comment': 'testcomment3', 'name': 'testname3'}], 'current': '1'}
	>>> def to_treeish_test(command): return to_treeish(command, db_data)
	>>> to_treeish_test('start')
	{'index': '0', 'type': 'commitindex'}
	>>> to_treeish_test('end')
	{'index': '2', 'type': 'commitindex'}
	>>> to_treeish_test('next')
	{'index': '2', 'type': 'commitindex'}
	>>> to_treeish_test('prev')
	{'index': '0', 'type': 'commitindex'}
	>>> db_data['current'] = 0
	>>> to_treeish_test('prev')
	{'message': 'Error: Index -1 is less than 0.', 'type': 'error'}
	>>> db_data['current'] = 2
	>>> to_treeish_test('next')
	{'message': 'Error: Index 3 is greater than the largest commit index.', 'type': 'error'}
	'''

	commits = db_data['commits']

	def valid_commit_index(index):
		return unless_no_commits(commits, lambda commits: within_bounds(commits, int(index)))

	commit_index_table = {
		'start': 0,
		'end': len(commits) - 1,
		'next': get_current_index(db_data, -1) + 1,
		'prev': get_current_index(db_data, 1) - 1
	}

	if val in commit_index_table: return valid_commit_index(commit_index_table[val])

	try:
		return valid_commit_index(str(int(str(val))))
	except ValueError:
		return {'type': 'branch', 'name': val}

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

def point_to_commit(db_data, commit_index):
	commit_index = int(commit_index)
	commits = db_data['commits']
	commit = commits[commit_index]
	print format_current_commit(commits, commit_index)
	checkout(commit['name'])
	db_data['current'] = commit_index
	write_db(db_data)

if __name__ == '__main__' and cmdargs.tests:
	import doctest
	doctest.testmod()
elif __name__ == '__main__':
	git_repo = cmdargs.repository
	git_log_data = os.path.basename(git_repo) + ".gitfwd"

	if not os.path.exists(git_repo):
		print "Directory " + git_repo + " does not exist."
		sys.exit(0)
	elif not os.path.exists(git_repo + "/.git"):
		print "Directory " + git_repo + "/.git is not a git repository."

	if not os.path.exists(git_log_data) or cmdargs.reset:
		write_commits_to_index(get_commits_from_repo())

	db_data = read_db()
	commits = db_data['commits']
	
	if cmdargs.list:
		current_index = get_current_index(db_data, -1)
		
		for i in range(len(commits)):
			print (format_current_commit if i == current_index else format_commit)(commits, i)
	elif cmdargs.reset:
		del_db_data('current')
	elif cmdargs.direction:
		treeish = to_treeish(cmdargs.direction, db_data)
		if treeish['type'] == 'error':
			print treeish['message']
		else:
			point_to_commit(db_data, treeish['index'])
	elif cmdargs.index:
		treeish = to_treeish(cmdargs.index, db_data)
		if treeish['type'] == 'error':
			print treeish['message']
		else:
			point_to_commit(db_data, treeish['index'])
	elif cmdargs.branch:
		treeish = to_treeish(cmdargs.branch, db_data)
		if treeish['type'] == 'error':
			print treeish['message']
		else:
			print "Checking out branch " + treeish['name']
			checkout(treeish['name'])
	else:
		print 'No command specified.'
