GIT_REPO = ARGV[0]
command = ARGV[1]

if !File.exist? GIT_REPO
	puts "Directory #{ARGV[0]} does not exist."
elsif !File.exist? ARGV[0] + "/.git"
	puts "Directory #{ARGV[0]} is not a git repository."
end

def run_command(cmd)
	output = `#{cmd}`

	if $?.exitstatus != 0
		puts "Error running command: #{cmd}"
		puts output
		exit($?.exitstatus)
	end

	{:status => $?.exitstatus, :output => output}
end

GIT_LOG_DATA= "#{File.basename ARGV[0]}.gitwalkcommits"
GIT_LOG_CURRENT = "#{File.basename ARGV[0]}.gitwalkcurrent"

if !File.exist?(GIT_LOG_DATA) || ARGV[1] == 'reset'
	data = run_command("cd #{ARGV[0]}; git log | grep ^commit | cut -d \\  -f 2 2>&1")
	File.open(GIT_LOG_DATA, 'w+') {|f| f.write data[:output].strip }
	File.delete(GIT_LOG_CURRENT) if File.exist?(GIT_LOG_CURRENT)
end

commits = File.read(GIT_LOG_DATA).split("\n").reverse

commit_index = 0

def checkout(treeish)
        run_command("cd #{GIT_REPO}; git checkout #{treeish} 2>&1")
end

def point_to_commit(commits, commit_index)
	if commits.length == 0
		puts "No commits found in the repo yet."
		exit(0)
	end

	commit_index = commit_index.to_i

	if commit_index >= commits.length
		puts "Specified commit index is greater than the number of commits in this repo."
		exit 0
	end

	checkout commits[commit_index]
	File.open(GIT_LOG_CURRENT, 'w+') {|f| f.write commit_index.to_s }
end

def get_current_index(default)
	return File.read(GIT_LOG_CURRENT).to_i if File.exist?(GIT_LOG_CURRENT)
	return default
end

if command == nil
	current_index = get_current_index(nil)
	commits.each_with_index {|commit, i|
		print '=> ' if i == current_index
		puts commit
	}
	exit(0)
elsif command == 'reset'
	exit 0
elsif command == 'start'
	point_to_commit commits, 0
elsif command == 'end'
	point_to_commit commits, commits.length - 1
elsif command == 'next'
	commit_index = get_current_index(0)

	if commit_index >= commits.length
		puts "Already at the latest commit."
		exit(0)
	end

	point_to_commit commits, commit_index
else
	if command.to_i.to_s != command
		puts "Checkout out the #{branch} branch"
		checkout command
		exit 0
	end
end


