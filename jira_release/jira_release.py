import os
import re
import subprocess
import sys

import fire

from .changelog import Changelog, ChangelogGenerationError


def get_issues_in_deployment(jira_prefix, remote_version, to_deploy_version, git_path):
    """
    Returns a list of Jira issues that are found in the commit messages to deploy.
    This list is determined by matching a pattern in the pending commits' message
    @param jira_prefix: The prefix of the Jira issue
    @param remote_version: The version currently live on the remote server
    @param to_deploy_version: The version to be deployed
    @param git_path: The path of the local git repository
    @return: a list of Jira issues
    @rtype: List[Str]
    """
    path = os.path.join(os.getcwd(), git_path)
    if not os.path.exists(path) or not os.path.isdir(path):
        sys.exit(f"{path} is not a directory")
    changes = subprocess.check_output(
        "git log --no-color --oneline".split()
        + [f"{remote_version}..{to_deploy_version}"],
        cwd=path,
        text=True,
    )

    changes = changes.split("\n")

    issues = set()

    for change in changes:
        test = re.match(f"(.*)({jira_prefix}\d+)(.*)", change)
        if test:
            issues.add(test.groups()[1])

    return list(issues)


class JiraReleaseHelper(object):
    """
    Tool used at deploy-time that uses the Atlassian Jira API to post comments and
    change the state of Jira issues that are being deployed.
    """

    def __init__(self):
        from jira import JIRA

        try:
            username = os.environ["JIRA_USERNAME"]
            password = os.environ["JIRA_PASSWORD"]
            url = os.environ["JIRA_URL"]
        except KeyError:
            sys.exit(
                "Please set JIRA_USERNAME, JIRA_PASSWORD and JIRA_URL environment variables"
            )

        try:
            self.jira = JIRA(url, basic_auth=(username, password))
        except Exception:
            sys.exit("Jira authentication issue")

    def __comment_confirm_deploy(self, environment, issue):
        if (
            input(
                f"Do you want to comment about the deployment of {issue} to {environment} on the Jira issue? [y/N]: "
            ).lower()
            == "y"
        ):
            self.jira.add_comment(
                issue, f"{issue} was deployed in the {environment} environment"
            )

    def __close_and_resolve(self, issue):
        jira_issue = self.jira.issue(issue)
        resolution_mapping = {"Bug": "Fixed"}
        resolution_name = resolution_mapping.get(
            jira_issue.fields.issuetype.name, "Done"
        )
        transitions = self.jira.transitions(jira_issue)
        close_transition_id = None
        for transition in transitions:
            if transition["name"] == "Close":
                close_transition_id = transition["id"]

        if close_transition_id is None:
            print(
                f"Skipping closing procedure for Jira issue {issue} in status {jira_issue.fields.status.name}"
            )
            return

        if (
            input(
                f"Do you want to close Jira issue {issue} and mark it as {resolution_name} ? [y/N]: "
            ).lower()
            == "y"
        ):
            self.jira.transition_issue(
                jira_issue,
                close_transition_id,
                resolution={"name": resolution_name},
            )

    def comment_after_deploy(
        self,
        jira_prefix,
        environment,
        remote_version,
        to_deploy_version="HEAD",
        git_path=".",
    ):
        """
        Posts a comment on JIRA issues that are to be deployed
        @param jira_prefix: The prefix of the JIRA issue
        @param environment: The environment to be deploy in
        @param remote_version: The version currently live on the remote server
        @param to_deploy_version: The version to be deployed
        @param git_path: The path of the local git repository
        @return: None
        """
        issues = get_issues_in_deployment(
            jira_prefix, remote_version, to_deploy_version, git_path
        )

        if not issues:
            return "No JIRA issues found in this deployment"

        for issue in issues:
            self.__comment_confirm_deploy(environment, issue)

    def comment_and_close_issues_to_deploy(
        self,
        jira_prefix,
        environment,
        remote_version,
        to_deploy_version="HEAD",
        git_path=".",
    ):
        """
        Posts a comment on JIRA issues that are to be deployed, and asks to close and
        resolve them.
        @param jira_prefix: The prefix of the JIRA issue
        @param environment: The environment to be deploy in
        @param remote_version: The version currently live on the remote server
        @param to_deploy_version: The version to be deployed
        @param git_path: The path of the local git repository
        @return: None
        """

        issues = get_issues_in_deployment(
            jira_prefix, remote_version, to_deploy_version, git_path
        )

        if not issues:
            return "No JIRA issues found in this deployment"

        for issue in issues:
            self.__comment_confirm_deploy(environment, issue)
            self.__close_and_resolve(issue)

    def generate_changelog(
        self,
        jira_prefix,
        remote_version,
        to_deploy_version="HEAD",
        git_path=".",
        changelog_path="CHANGELOG.md",
        initialize=False,
    ):
        """
        Generates/updates a changelog data file found in git_path, based on JIRA issues to be deployed
        @param jira_prefix: The prefix of the JIRA issue
        @param remote_version: The version currently live on the remote server
        @param to_deploy_version: The version to be deployed
        @param git_path: The path of the local git repository
        @param changelog_path: The relative path of the changelog file within git_path
        @param initialize: Creates or overwrite the changelog file
        @return: None
        """

        full_changelog_path = os.path.join(git_path, changelog_path)
        changelog_gen = Changelog(self.jira, full_changelog_path)

        try:
            file_exists = changelog_gen.check_if_changelog_exists(raise_exception=False)
            if initialize:
                if file_exists and (
                    input(
                        f"A changelog file already exists, do you want to overwrite it? [y/N]: "
                    ).lower()
                    != "y"
                ):
                    return
                has_to_initialize = True
            elif not file_exists:
                if (
                    input(
                        f"A changelog file was not found. Would you like to initialize it ? [y/N]: "
                    ).lower()
                    != "y"
                ):
                    return
                else:
                    has_to_initialize = True
            else:
                has_to_initialize = False

            if file_exists and not has_to_initialize:
                first_git_marker = changelog_gen.find_first_git_marker()
                if remote_version != first_git_marker and (
                    input(
                        f"WARNING: The remote version is different from the last deployment found in {changelog_path} !\n"
                        f"As a result, the CHANGELOG could be update with erroneous information\n. Proceed anyway ? [y/N]"
                    ).lower()
                    != "y"
                ):
                    return
                remote_version = first_git_marker

            issues = get_issues_in_deployment(
                jira_prefix, remote_version, to_deploy_version, git_path
            )
            if not issues:
                sys.exit(
                    "No JIRA issues were found in the commits, the changelog was not updated !"
                )

            changelog_gen.update_changelog(issues, to_deploy_version, has_to_initialize)

            if has_to_initialize:
                return f"{changelog_path} was correctly initialized."
            else:
                return f"{changelog_path} was updated."
        except ChangelogGenerationError as exc:
            sys.exit(str(exc))


def main():
    fire.Fire(JiraReleaseHelper)


if __name__ == "__main__":
    main()
