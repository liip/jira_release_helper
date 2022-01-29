import datetime
import os.path


class ChangelogGenerationError(Exception):
    pass


class ChangelogFileInvalidFormatError(Exception):
    pass


class ChangelogFileNotFoundError(ChangelogGenerationError):
    pass


CHANGELOG_FORMAT = """
# Historique des changements

{changes}
"""

CHANGE_FORMAT = "## {date}"

ISSUE_FORMAT = "- **{issue_code}**: {issue_summary}"

CHANGES_MARKER = "<!--- changes -->"
GIT_FORMAT = "<!--- git-{hash} -->"

DATETIME_FORMAT = "%d.%m.%Y"


class Changelog(object):
    def __init__(self, jira_client, changelog_path):
        self.jira_client = jira_client
        if not os.path.isfile(changelog_path):
            raise ChangelogFileNotFoundError
        self.changelog_path = changelog_path

    def find_changes_marker(self, changelog_lines):
        for i, line in enumerate(changelog_lines):
            if "<!--- changes -->" in line:
                return i
        raise ChangelogFileInvalidFormatError

    def create_or_update_changelog(self, jira_issues, to_deploy_commit_hash):
        with open(self.changelog_path, "r+") as changelog_file:
            changelog_lines = changelog_file.readlines()
            changes_marker = self.find_changes_marker(changelog_lines)

            today = datetime.datetime.today()
            today_formatted = today.strftime(DATETIME_FORMAT)
            date_line = CHANGE_FORMAT.format(date=today_formatted)
            git_line = GIT_FORMAT.format(hash=to_deploy_commit_hash)

            start_line = None

            if len(changelog_lines) >= changes_marker:
                for i, changelog_line in enumerate(
                    changelog_lines[changes_marker + 1 : -1]
                ):
                    if git_line == changelog_line.strip():
                        return
                    if date_line == changelog_line.strip():
                        start_line = i + changes_marker + 1 + 1

            if start_line is None:
                changelog_lines.insert(changes_marker + 1, date_line + "\n")
                start_line = changes_marker + 2

            issue_lines = [GIT_FORMAT.format(hash=to_deploy_commit_hash) + "\n"]
            for issue in jira_issues:
                jira_issue = self.jira_client.issue(issue)
                summary = jira_issue.fields.summary
                issue_lines.append(
                    ISSUE_FORMAT.format(issue_code=issue, issue_summary=summary) + "\n"
                )
            issue_lines.append("\n")

            new_changelog_lines = (
                changelog_lines[:start_line]
                + issue_lines
                + changelog_lines[start_line:]
            )

            changelog_file.seek(0)
            changelog_file.writelines(new_changelog_lines)
            changelog_file.truncate()
