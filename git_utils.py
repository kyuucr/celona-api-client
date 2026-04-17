import os
import stat
import tempfile
from git import Repo, GitCommandError
import logging


def update_file(
    repo_ssh_url: str, 
    local_dir: str, 
    file_relative_path: str, 
    new_content: str, 
    ssh_key_content: str,
    commit_message: str = "Update file via GitPython"
) -> bool:
    """
    Clones/pulls a repo using an SSH deploy key string, updates a file, and pushes the change.
    """
    # Create a temporary file to hold the private key content securely
    # delete=False ensures we control exactly when it gets deleted
    with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as temp_key_file:
        temp_key_file.write(ssh_key_content)
        temp_key_path = temp_key_file.name

    try:
        # SSH strictly enforces that private keys must not be publicly readable.
        # We set the permissions to 600 (Read/Write for the owner only).
        os.chmod(temp_key_path, stat.S_IRUSR | stat.S_IWUSR)

        # Create the SSH command targeting our temporary key file
        ssh_cmd = f'ssh -i {temp_key_path} -o StrictHostKeyChecking=no'
        custom_env = {"GIT_SSH_COMMAND": ssh_cmd}

        # ==========================================
        # Step 1: Clone or Open the Repository
        # ==========================================
        if not os.path.exists(local_dir):
            logging.debug(f"Cloning repository into {local_dir}...")
            repo = Repo.clone_from(repo_ssh_url, local_dir, env=custom_env)
        else:
            logging.debug(f"Repository already exists at {local_dir}. Pulling latest changes...")
            repo = Repo(local_dir)
            with repo.git.custom_environment(**custom_env):
                repo.remotes.origin.pull()

        # ==========================================
        # Step 2: Modify the file locally
        # ==========================================
        full_file_path = os.path.join(local_dir, file_relative_path)
        os.makedirs(os.path.dirname(full_file_path), exist_ok=True)
        
        with open(full_file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        logging.debug(f"Updated local file: {full_file_path}")

        # ==========================================
        # Step 3: Add, Commit, and Push
        # ==========================================
        if not repo.is_dirty(untracked_files=True):
            logging.warning("No changes detected. Nothing to push.")
            return True

        repo.index.add([file_relative_path])
        repo.index.commit(commit_message)
        logging.debug("Committed changes.")

        with repo.git.custom_environment(**custom_env):
            push_info = repo.remotes.origin.push()
            for info in push_info:
                if info.flags & info.ERROR:
                    logging.debug(f"Push failed: {info.summary}")
                    return False

        logging.debug("Successfully pushed changes to GitHub.")
        return True

    except GitCommandError as e:
        logging.error(f"A Git command failed: {e}")
        return False
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        return False
        
    finally:
        # ==========================================
        # Step 4: Secure Cleanup
        # ==========================================
        # This block ALWAYS runs, ensuring the private key is wiped from the disk
        if os.path.exists(temp_key_path):
            os.remove(temp_key_path)
            logging.debug("Cleaned up temporary SSH key file.")
