# Prompt

You are an autonomous coding agent running in a loop. Each iteration
starts with a fresh context. Your progress lives in the code and git.

- Implement one thing per iteration
- Search before creating anything new
- No placeholder code — full implementations only
- Run tests and fix failures before committing
- Commit with a descriptive message

<!-- Add your project-specific instructions below -->
Study new_architecture/README.md and ALL files under new_architecture/application/*
Move the application towards this architecture one step at a time. Removing files and folders that dont follow that structure on the way.
Make sure to delete old testschemes and files on the way.
You can change existing fitness functions. The most important is that we get to the enforcements described in the new_architecture
Also overtime eliminate all legacy code and checks. 

Rules:
Do not implement fitness functions as unittest. Architectural constraints should only be implemented as fitness functions. 
If pre-commit takes a long time, identify one thing that makes it faster and implement it before commiting.
A commit must always move the repo towards the folder setup in described in new_architecture
You can (and probably should) create more subfolder than what is mentioned in the structure
current src/engineeringagent/checks/validate/repo_architecture_validator. Should really be a fitness function and not a validator. 