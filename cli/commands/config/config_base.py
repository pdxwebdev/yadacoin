"""Base class for config file updaters.

This module provides ConfigUpdaterBase, an abstract base class that handles
common config update operations like loading, validating, backing up, and writing
config files atomically. Subclasses implement specific update logic for different
config fields.

Design:
    - Load: Parse JSON config file
    - Confirm: Prompt user to confirm they've backed up the file
    - Update: Modify specific config fields (implemented by subclasses)
    - Write: Atomically write updated config back to disk
"""

import json
import os


class ConfigUpdaterBase:
    """Base class for config file update handlers.

    This class provides common functionality for updating config.json files:
    - Loading and parsing JSON
    - Prompting for backup confirmation (with data-loss warnings)
    - Atomic file writes (using temp file + rename pattern)

    Subclasses must implement config-specific update logic.

    Attributes:
        warning_text (str): Warning message shown before any modifications.
    """

    warning_text = (
        "WARNING: Updating your config.json can invalidate existing data or keys. "
        "There is a possibility that all data could be lost."
    )

    def load_config(self, path):
        """Load and parse a JSON config file.

        Args:
            path (str): File path to the config.json file.

        Returns:
            dict: Parsed JSON configuration object.

        Raises:
            FileNotFoundError: If the config file does not exist.
            json.JSONDecodeError: If the file is not valid JSON.
            ValueError: If the JSON is not a dictionary/object.
        """
        with open(path, "r") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError("config.json must contain a JSON object")
        return data

    def confirm_backup(self, path, confirmed_flag):
        """Confirm that the user has backed up their config file.

        Displays a warning about potential data loss, then either accepts the
        --confirm-backup flag or prompts the user to type 'yes' to continue.

        Args:
            path (str): Path to the config file (used in confirmation message).
            confirmed_flag (bool): If True, skip the prompt and return True immediately.

        Returns:
            bool: True if confirmed, False if user declined or didn't type 'yes'.
        """
        print(self.warning_text)
        if confirmed_flag:
            return True

        response = input(
            "Have you backed up {}? Type 'yes' to continue: ".format(path)
        ).strip()
        if response.lower() != "yes":
            print("Aborted: backup confirmation was not provided.")
            return False
        return True

    def write_config(self, path, config):
        """Atomically write config dict back to file.

        Uses a temp file + atomic rename pattern to minimize corruption risk:
        1. Write to a temporary file
        2. Atomically rename temp file to target path
        3. Preserve original file permissions (mode)

        Args:
            path (str): Target file path for the config.json.
            config (dict): Configuration dictionary to write.
        """
        temp_path = "{}.tmp".format(path)
        with open(temp_path, "w") as handle:
            json.dump(config, handle, indent=4)
            handle.write("\n")

        try:
            original_mode = os.stat(path).st_mode
        except FileNotFoundError:
            original_mode = None

        os.replace(temp_path, path)
        if original_mode is not None:
            os.chmod(path, original_mode)
