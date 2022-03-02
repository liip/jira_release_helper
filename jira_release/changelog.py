import datetime
import os.path
import re


class ChangelogGenerationError(Exception):
    pass


class ChangelogFileInvalidFormatError(Exception):
    pass


class ChangelogFileNotFoundError(ChangelogGenerationError):
    pass


CHANGELOG_HEADER = """# Historique des changements

<!--- changes -->
"""

CHANGE_FORMAT = "## {date}"

ISSUE_FORMAT = (
    "- **[{issue_code}](https://jira.liip.ch/browse/{issue_code})**: {issue_summary}"
)

CHANGES_MARKER = "<!--- changes -->"
GIT_FORMAT = "<!--- git-{hash} -->"
GIT_REGEX = r"<!--- git-([a-f0-9]{40}) -->"

DATETIME_FORMAT = "%d.%m.%Y"


class Changelog(object):
    def __init__(self, jira_client, changelog_path):
        self.jira_client = jira_client
        self.changelog_path = changelog_path

    def find_first_git_marker(self):
        with open(self.changelog_path, "r") as changelog_file:
            for line in changelog_file.readlines():
                match = re.match(GIT_REGEX, line.strip())
                if match:
                    return match.group(1)

    def check_if_changelog_exists(self, raise_exception=True):
        is_file = os.path.isfile(self.changelog_path)

        if raise_exception and not is_file:
            raise ChangelogFileNotFoundError

        return is_file

    def find_changes_marker(self, changelog_lines):
        for i, line in enumerate(changelog_lines):
            if "<!--- changes -->" in line:
                return i
        raise ChangelogFileInvalidFormatError

    def update_changelog(self, jira_issues, to_deploy_commit_hash, initialize=False):
        """
        Updates a changelog file with
        @param jira_issues:
        @param to_deploy_commit_hash:
        @param initialize:
        @return:
        """
        if not initialize:
            self.check_if_changelog_exists()
            lines_func = lambda file: file.readlines()
            mode = "r+"
        else:
            lines_func = lambda file: [l + "\n" for l in CHANGELOG_HEADER.split("\n")]
            mode = "w+"

        with open(self.changelog_path, mode) as changelog_file:
            changelog_lines = lines_func(changelog_file)
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
