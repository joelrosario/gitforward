import sys
import os
import re
import subprocess

GIT_REPO = sys.argv[1]
command = sys.argv[2] if len(sys.argv) > 2 else None

if not os.path.exists(GIT_REPO):
	print "Directory " + GIT_REPO + " does not exist."
	sys.exit(0)
elif not os.path.exists(GIT_REPO + "/.git"):
	print "Directory " + GIT_REPO + "/.git is not a git repository."

GIT_LOG_DATA = os.path.basename(GIT_REPO) + ".gitwalkcommits"
GIT_LOG_CURRENT = os.path.basename(GIT_REPO) + ".gitwalkcurrent"

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

if not os.path.exists(GIT_LOG_DATA) or command == 'reset':
	commits_in_repo = get_commits_from_repo()
	with open(GIT_LOG_DATA, 'w+') as f:
		commits = get_commits_from_repo()
		for commit in commits:
			f.write(commit['name'] + ' ' + commit['comment'] + '\n')

def get_commits_from_index():
	with open(GIT_LOG_DATA) as f:
		return [{'name': line[0], 'comment': line[1].strip()} for line in [line.split(' ', 1) for line in f.readlines()] ]

def get_current_index(default):
	if os.path.exists(GIT_LOG_CURRENT):
		with open(GIT_LOG_CURRENT) as f:
			return int(f.read())
	return default

def unless_no_commits(fn):
	def _(commits):
		if len(commits) == 0: return {'type': 'error', 'message': 'No commit found.'}
		return fn(commits)
	
	return _

def to_commit_index(index):
	return {'type': 'commitindex', 'index': str(index)}

def error_msg(message):
	return {'type': 'error', 'message': 'Error: ' + message}

def within_bounds(commits, index):
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
	def valid_commit_index(index):
		return unless_no_commits(lambda commits: within_bounds(commits, index))

	actions = {
		'start': valid_commit_index(0),
		'end': valid_commit_index(len(commits) - 1),
		'next': valid_commit_index(get_current_index(-1) + 1),
		'prev': valid_commit_index(get_current_index(1) - 1)
	}

	if val in actions:
		return actions[val]

	def defaultaction(commits):
		try:
			if len(commits) > 0:
				return to_commit_index(str(int(str(val))))
			return error_msg('No commit found.')
		except ValueError:
			return {'type': 'branch', 'name': val}

	return defaultaction

def format_commit(commits, index):
	index_str_length = len(str(len(commits) - 1))
	format = "%(num)" + str(index_str_length) + "s"
	line = "  " + format % {'num': str(index) } + ". " + commits[index]['name'] + '   ' + commits[index]['comment']
	return line

def format_current_commit(commits, index):
	index_str_length = len(str(len(commits) - 1))
	format = "%(num)" + str(index_str_length) + "s"
	line = "> " + format % {'num': str(index) } + ". " + commits[index]['name'] + ' > ' + commits[index]['comment']
	return line

def point_to_commit(commits, commit_index):
	commit_index = int(commit_index)
	commit = commits[commit_index]
	print format_current_commit(commits, commit_index)
	checkout(commit['name'])
	with open(GIT_LOG_CURRENT, 'w+') as f:
		f.write(str(commit_index))

commits = get_commits_from_index()

if command == None:
	current_index = get_current_index(None)

	for i in range(len(commits)):
		print (format_current_commit if i == current_index else format_commit)(commits, i)
elif command == 'reset':
	if os.path.exists(GIT_LOG_CURRENT): os.remove(GIT_LOG_CURRENT)
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
