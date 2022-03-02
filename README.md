# Jira Release Helper

A tool that uses a `git` repo's commit history to:

- Determine which Jira issues are being deployed and consequently comment and/or close them.
- Generate a changelog entry, using the `keepachangelog.com` philosophy


## Usage

### Generate a changelog

```
jira_release generate_changelog <jira prefix> <environment> <remote commit hash> <local commit hash> <local git repo path> <changelog_path> <initialize>
```


**Notable parameters**
`changelog_path` is the relative path of the CHANGELOG file within the git repo.
`initialize` is a boolean that is used to generate the CHANGELOG file if this does not yet exist. It will contain the current deployment's changes.

**Example**

```
jira_release generate_changelog SWING- staging 8278cf99cf270332d113f6a3de7ea526c9a126db 5be893162f4bc698acdd6c969388117f0e25c931 /code CHANGELOG.md False
```

### Comment and close JIRA issues

```
jira_release <COMMAND> <jira prefix> <environment> <remote commit hash> <local commit hash> <local git repo path>
```

The `COMMAND` can be either:

- `comment_and_close_issues_to_deploy`: for each detected Jira issue, this command will ask the user if he allows a commment to be posted, THEN asks if the program should close and resolve the issue.
- `comment_after_deploy`: for each detected Jira issue, this command will ask the user if he allows a commment to be posted.

**Example**

```
jira_release comment_after_deploy SWING- staging 8278cf99cf270332d113f6a3de7ea526c9a126db 5be893162f4bc698acdd6c969388117f0e25c931 /code
```