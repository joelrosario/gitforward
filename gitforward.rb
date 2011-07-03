git_repo = ARGV[0]
commit_index = ARGV[1]

if !File.exist? git_repo
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

git_log_data = "#{File.basename ARGV[0]}.gitwalkcommits"
git_log_current = "#{File.basename ARGV[0]}.gitwalkcurrent"

if !File.exist?(git_log_data) || ARGV[1] == 'reset'
	data = run_command("cd #{ARGV[0]}; git log | grep ^commit | cut -d \\  -f 2 2>&1")
	File.open(git_log_data, 'w+') {|f| f.write data[:output].strip }
	File.delete(git_log_current) if File.exist?(git_log_current)
end

exit 0 if ARGV[1] == 'reset'

commits = File.read(git_log_data).split("\n").reverse

if commit_index == nil
	current_index = (File.exist?(git_log_current) ? File.read(git_log_current).to_i : nil)
	commits.each_with_index {|commit, i|
		print '=> ' if i == current_index
		puts commit
	}
	exit(0)
elsif commit_index == 'start'
	commit_index = 0
elsif commit_index == 'end'
	commit_index = commits.length - 1
elsif commit_index == 'next'
	if !File.exist?(git_log_current)
		commit_index = 0
	else
		commit_index = File.read(git_log_current).to_i + 1
	end

	if commit_index >= commits.length
		puts "Already at the latest commit."
		exit(0)
	end
else
	if ARGV[1].to_i.to_s != ARGV[1]
		puts "Checkout out the #{ARGV[1]} branch"
		run_command("cd #{git_repo}; git checkout #{ARGV[1]} 2>&1")
		exit 0
	end
end

if commits.length == 0
	puts "No commits found in the repo yet."
	exit(0)
end

commit_index = commit_index.to_i

if commit_index >= commits.length
	puts "Specified commit index is greater than the number of commits in this repo."
	exit 0
end

run_command("cd #{git_repo}; git checkout #{commits[commit_index]} 2>&1")
File.open(git_log_current, 'w+') {|f| f.write commit_index.to_s }

