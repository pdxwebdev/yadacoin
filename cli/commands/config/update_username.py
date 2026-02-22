"""Handler for updating username in config.json.

This module provides UsernameConfigUpdater, which handles the update logic for
changing the username field in a YadaCoin config file. When the username is
changed, the username_signature is automatically recalculated using the node's
private key through a deterministic signing process.

Usage:
    updater = UsernameConfigUpdater()
    if updater.confirm_backup('config/config.json', confirm_flag=False):
        config = updater.load_config('config/config.json')
        updater.update_username(config, 'new_username')
        updater.write_config('config/config.json', config)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)) + "/../../..")

from cli.commands.config.config_base import ConfigUpdaterBase
from yadacoin.core.transactionutils import TU


class UsernameConfigUpdater(ConfigUpdaterBase):
    """Updater for the username field in config.json.

    This class extends ConfigUpdaterBase to handle username updates. It validates
    the username is not empty and recalculates the deterministic signature using
    the private key whenever the username is changed.

    The signature is required for peer authentication on the YadaCoin network
    and must be recomputed any time the username changes.
    """

    def update_username(self, config, username):
        """Update username and recalculate username_signature.

        Sets the 'username' field and automatically computes a deterministic
        signature of the new username using the node's private key. This signature
        is required for peer-to-peer authentication and identity verification.

        Args:
            config (dict): The config dictionary to update in-place.
            username (str): New username value (cannot be empty).

        Raises:
            ValueError: If username is empty or config lacks 'private_key'.
        """
        if not username:
            raise ValueError("username cannot be empty")
        private_key = config.get("private_key")
        if not private_key:
            raise ValueError("config.json is missing 'private_key'")

        config["username"] = username
        config["username_signature"] = TU.generate_deterministic_signature(
            config, username, private_key=private_key
        )
