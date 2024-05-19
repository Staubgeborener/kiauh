import json
import shutil
import urllib.request
from http.client import HTTPResponse
from json import JSONDecodeError
from pathlib import Path
from subprocess import DEVNULL, PIPE, CalledProcessError, check_output, run
from typing import List, Optional, Type

from core.instance_manager.base_instance import BaseInstance
from core.instance_manager.instance_manager import InstanceManager
from utils.input_utils import get_confirm, get_number_input
from utils.logger import Logger


def git_clone_wrapper(
    repo: str, target_dir: Path, branch: Optional[str] = None
) -> None:
    """
    Clones a repository from the given URL and checks out the specified branch if given.

    :param repo: The URL of the repository to clone.
    :param branch: The branch to check out. If None, the default branch will be checked out.
    :param target_dir: The directory where the repository will be cloned.
    :return: None
    """
    log = f"Cloning repository from '{repo}'"
    Logger.print_status(log)
    try:
        if Path(target_dir).exists():
            question = f"'{target_dir}' already exists. Overwrite?"
            if not get_confirm(question, default_choice=False):
                Logger.print_info("Skip cloning of repository ...")
                return
            shutil.rmtree(target_dir)

        git_cmd_clone(repo, target_dir)
        git_cmd_checkout(branch, target_dir)
    except CalledProcessError:
        log = "An unexpected error occured during cloning of the repository."
        Logger.print_error(log)
        return
    except OSError as e:
        Logger.print_error(f"Error removing existing repository: {e.strerror}")
        return


def git_pull_wrapper(repo: str, target_dir: Path) -> None:
    """
    A function that updates a repository using git pull.

    :param repo: The repository to update.
    :param target_dir: The directory of the repository.
    :return: None
    """
    Logger.print_status(f"Updating repository '{repo}' ...")
    try:
        git_cmd_pull(target_dir)
    except CalledProcessError:
        log = "An unexpected error occured during updating the repository."
        Logger.print_error(log)
        return


def get_repo_name(repo: Path) -> str:
    """
    Helper method to extract the organisation and name of a repository |
    :param repo: repository to extract the values from
    :return: String in form of "<orga>/<name>"
    """
    if not repo.exists() or not repo.joinpath(".git").exists():
        return "-"

    try:
        cmd = ["git", "-C", repo, "config", "--get", "remote.origin.url"]
        result = check_output(cmd, stderr=DEVNULL)
        return "/".join(result.decode().strip().split("/")[-2:])
    except CalledProcessError:
        return "-"


def get_tags(repo_path: str) -> List[str]:
    try:
        url = f"https://api.github.com/repos/{repo_path}/tags"
        with urllib.request.urlopen(url) as r:
            response: HTTPResponse = r
            if response.getcode() != 200:
                Logger.print_error(
                    f"Error retrieving tags: HTTP status code {response.getcode()}"
                )
                return []

            data = json.loads(response.read())
            return [item["name"] for item in data]
    except (JSONDecodeError, TypeError) as e:
        Logger.print_error(f"Error while processing the response: {e}")
        raise


def get_latest_tag(repo_path: str) -> str:
    """
    Gets the latest stable tag of a GitHub repostiory
    :param repo_path: path of the GitHub repository - e.g. `<owner>/<name>`
    :return: tag or empty string
    """
    try:
        if len(latest_tag := get_tags(repo_path)) > 0:
            return latest_tag[0]
        else:
            return ""
    except Exception:
        Logger.print_error("Error while getting the latest tag")
        raise


def get_latest_unstable_tag(repo_path: str) -> str:
    """
    Gets the latest unstable (alpha, beta, rc) tag of a GitHub repository
    :param repo_path: path of the GitHub repository - e.g. `<owner>/<name>`
    :return: tag or empty string
    """
    try:
        if len(unstable_tags := [t for t in get_tags(repo_path) if "-" in t]) > 0:
            return unstable_tags[0]
        else:
            return ""
    except Exception:
        Logger.print_error("Error while getting the latest unstable tag")
        raise


def get_local_commit(repo: Path) -> str:
    if not repo.exists() or not repo.joinpath(".git").exists():
        return "-"

    try:
        cmd = f"cd {repo} && git describe HEAD --always --tags | cut -d '-' -f 1,2"
        return check_output(cmd, shell=True, text=True).strip()
    except CalledProcessError:
        return "-"


def get_remote_commit(repo: Path) -> str:
    if not repo.exists() or not repo.joinpath(".git").exists():
        return "-"

    try:
        # get locally checked out branch
        branch_cmd = f"cd {repo} && git branch | grep -E '\*'"
        branch = check_output(branch_cmd, shell=True, text=True)
        branch = branch.split("*")[-1].strip()
        cmd = f"cd {repo} && git describe 'origin/{branch}' --always --tags | cut -d '-' -f 1,2"
        return check_output(cmd, shell=True, text=True).strip()
    except CalledProcessError:
        return "-"


def git_cmd_clone(repo: str, target_dir: Path) -> None:
    try:
        command = ["git", "clone", repo, target_dir]
        run(command, check=True)

        Logger.print_ok("Clone successful!")
    except CalledProcessError as e:
        log = f"Error cloning repository {repo}: {e.stderr.decode()}"
        Logger.print_error(log)
        raise


def git_cmd_checkout(branch: str, target_dir: Path) -> None:
    if branch is None:
        return

    try:
        command = ["git", "checkout", f"{branch}"]
        run(command, cwd=target_dir, check=True)

        Logger.print_ok("Checkout successful!")
    except CalledProcessError as e:
        log = f"Error checking out branch {branch}: {e.stderr.decode()}"
        Logger.print_error(log)
        raise


def git_cmd_pull(target_dir: Path) -> None:
    try:
        command = ["git", "pull"]
        run(command, cwd=target_dir, check=True)
    except CalledProcessError as e:
        log = f"Error on git pull: {e.stderr.decode()}"
        Logger.print_error(log)
        raise


def rollback_repository(repo_dir: Path, instance: Type[BaseInstance]) -> None:
    q1 = "How many commits do you want to roll back"
    amount = get_number_input(q1, 1, allow_go_back=True)

    im = InstanceManager(instance)

    Logger.print_warn("Do not continue if you have ongoing prints!", start="\n")
    Logger.print_warn(
        f"All currently running {im.instance_type.__name__} services will be stopped!"
    )
    if not get_confirm(
        f"Roll back {amount} commit{'s' if amount > 1 else ''}",
        default_choice=False,
        allow_go_back=True,
    ):
        Logger.print_info("Aborting roll back ...")
        return

    im.stop_all_instance()

    try:
        cmd = ["git", "reset", "--hard", f"HEAD~{amount}"]
        run(cmd, cwd=repo_dir, check=True, stdout=PIPE, stderr=PIPE)
        Logger.print_ok(f"Rolled back {amount} commits!", start="\n")
    except CalledProcessError as e:
        Logger.print_error(f"An error occured during repo rollback:\n{e}")

    im.start_all_instance()
