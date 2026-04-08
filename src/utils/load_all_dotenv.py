from pathlib import Path
from dotenv import load_dotenv
import sys


def load_all_dotenv(path=".", verbose=True):
    """Load all .env files from a directory or a single .env file.

    Args:
        path: Either a directory path to load all .env files from or a specific .env file path.
        Defaults to current directory.
        verbose: If True, print status messages. Defaults to False.
    """
    path_obj = Path(path)

    if path_obj.is_file():
        # Load single file
        load_dotenv(path_obj)
        if verbose:
            print(f"✓ Loaded: {path_obj}")
    elif path_obj.is_dir():
        # Load all .env files in directory
        env_files = sorted(path_obj.glob("*.env"))
        if not env_files:
            if verbose:
                print(f"⚠ No .env files found in: {path_obj}")
        for env_file in env_files:
            load_dotenv(env_file)
            if verbose:
                print(f"✓ Loaded: {env_file}")
    else:
        raise ValueError(f"Path {path} is neither a file nor a directory")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "."
    load_all_dotenv(path, verbose=True)
    print(f"\nCompleted loading .env files from: {path}")
