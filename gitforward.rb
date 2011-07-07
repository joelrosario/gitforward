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

def get_commits_from_repo
	commits = []
	lines = []
	`cd #{GIT_REPO}; git log`.split("\n").each {|line|
		if line =~ /^commit/
			commits << lines if lines.length > 0
			lines = []
		end

		lines << line
	}

	commits << lines if lines.length > 0
	commits.collect {|commit|
		[commit[0], commit[commit.index("") + 1..commit.length]].flatten
	}.collect {|commit|
		{
			:name => commit[0].split(' ')[1],
			:comment => commit[1].strip
		}
	}
end

GIT_LOG_DATA= "#{File.basename ARGV[0]}.gitwalkcommits"
GIT_LOG_CURRENT = "#{File.basename ARGV[0]}.gitwalkcurrent"

if !File.exist?(GIT_LOG_DATA) || ARGV[1] == 'reset'
	data = get_commits_from_repo
	File.open(GIT_LOG_DATA, 'w+') {|f| f.write data.collect {|commit| "#{commit[:name]} #{commit[:comment]}"}.join("\n") }
	File.delete(GIT_LOG_CURRENT) if File.exist?(GIT_LOG_CURRENT)
end

commits = File.read(GIT_LOG_DATA).split("\n").reverse.collect {|l| name, comment = l.split(' ', 2); {:name => name, :comment => comment} }
commit_index = 0

def checkout(treeish)
        run_command("cd #{GIT_REPO}; git checkout #{treeish} 2>&1")
end

def point_to_commit(commits, commit_index)
	commit_index = commit_index.to_i
	commit = commits[commit_index]
	puts " * #{commit_index}. #{commit[:name]} -> #{commit[:comment]}"
	checkout commit[:name]
	File.open(GIT_LOG_CURRENT, 'w+') {|f| f.write commit_index.to_s }
end

def get_current_index(default)
	return File.read(GIT_LOG_CURRENT).to_i if File.exist?(GIT_LOG_CURRENT)
	return default
end

def to_commit(commit_index)
	return {:type => :commit_index, :commit_index => commit_index}
end

def unless_no_commits
	proc {|commits|
		if commits.length == 0
			{:type => :error, :message => 'No commits'}
		elsif block_given?
			yield(commits)
		else
			{:type => :error, :message => "Couldn't figure out which commit" }
		end
	}
end

def valid_commit_index(commits, commit_index)
	if commit_index >= commits.length
		{:type => :error, :message => "Commit index '#{commit_index}' is greater than the number of commits."}
	elsif commit_index < 0
		{:type => :error, :message => "Commit index '#{commit_index}' is less than 0." }
	else
		to_commit(commit_index)
	end
end

def to_treeish(val)
	{
		'start' => unless_no_commits {|commits| to_commit(0) },
		'end'   => unless_no_commits {|commits| to_commit(commits.length - 1) },
		'next'  => unless_no_commits {|commits| valid_commit_index(commits, get_current_index(-1) + 1) },
		'prev'  => unless_no_commits {|commits| valid_commit_index(commits, get_current_index(1) -1 ) }
	}[val] || proc {|commits|
		if val.to_i.to_s != val
			{:type => :branch, :name => val} 
		else
			unless_no_commits {|commits| valid_commit_index(commits, val.to_i) }.call(commits)
		end
	}
end

if command == nil
	current_index = get_current_index(nil)
	index_str_length = (commits.length - 1).to_s.length
	commits.each_with_index {|commit, i|
		if i == current_index
			print "* "
		else
			print "  "
		end

		print i.to_s.rjust(index_str_length, ' ') + '. '
		print commit[:name]

		if i == current_index
			print " -> "
		else
			print "    "
		end

		puts commit[:comment]
	}
elsif command == 'reset'
	exit 0
else
	treeish = to_treeish(command).call(commits)

	if treeish[:type] == :commit_index
		point_to_commit commits, treeish[:commit_index]
	elsif treeish[:type] == :branch
		puts "Checking out branch #{treeish[:name]}"
		checkout treeish[:name]
	elsif treeish[:type] == :error
		puts "Error: " + treeish[:message]
	else
		puts "Unexpected error."
	end
end

