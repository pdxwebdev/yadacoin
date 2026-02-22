"""YadaCoin CLI - Main entry point for command-line interface.

This module provides a generalized CLI interface for YadaCoin node management,
with support for multiple command namespaces (e.g., config, status, etc.).
Commands are organized hierarchically and delegate to specific handler classes.

Usage:
    python3 cli/cli.py <command> <subcommand> [options]
    python3 cli/cli.py --help  # Show available commands

Example:
    python3 cli/cli.py config set-username -u "mynode" --confirm-backup
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)) + "/..")

from cli.commands.config.update_username import UsernameConfigUpdater


class CommandError(Exception):
    """Exception raised when a command encounters an error.

    This exception is caught by main() and the error message is printed
    to the user before exiting with code 1.
    """


def _handle_set_username(args):
    """Handle the 'config set-username' command.

    This handler updates the username in a config.json file and recalculates
    the username_signature field using the private key. It ensures the user has
    backed up their config file before making any changes.

    Args:
        args: Parsed command-line arguments containing:
            - config: Path to config.json file
            - username: New username to set
            - confirm_backup: Boolean flag for backup confirmation

    Returns:
        0 on success, 1 if backup confirmation was denied or an error occurred.
    """
    updater = UsernameConfigUpdater()
    if not updater.confirm_backup(args.config, args.confirm_backup):
        return 1

    config = updater.load_config(args.config)
    updater.update_username(config, args.username)
    updater.write_config(args.config, config)
    print("Updated username and username_signature in {}".format(args.config))
    return 0


def build_parser():
    """Build and return the argument parser for the CLI.

    This function configures all available command namespaces and subcommands.
    New commands should be registered here by creating a new subparser and
    setting a handler function via set_defaults(handler=...).

    Returns:
        ArgumentParser: Configured argument parser with all subcommands registered.
    """
    parser = argparse.ArgumentParser(
        description="YadaCoin CLI (generalized interface)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Update node username:
    %(prog)s config set-username -u "mynode" --confirm-backup
  
  Interactive mode (prompts for backup confirmation):
    %(prog)s config set-username -u "mynode"
""",
    )
    subparsers = parser.add_subparsers(dest="command")

    config_parser = subparsers.add_parser("config", help="Config operations")
    config_subparsers = config_parser.add_subparsers(dest="config_command")

    set_username_parser = config_subparsers.add_parser(
        "set-username",
        help="Update username and username_signature in config.json",
    )
    set_username_parser.add_argument(
        "-c",
        "--config",
        default="config/config.json",
        help="Path to config.json",
    )
    set_username_parser.add_argument(
        "-u",
        "--username",
        required=True,
        help="New username",
    )
    set_username_parser.add_argument(
        "--confirm-backup",
        action="store_true",
        help="Confirm you have backed up your config.json",
    )
    set_username_parser.set_defaults(handler=_handle_set_username)

    return parser


def main():
    """Main entry point for the CLI.

    This function parses command-line arguments and dispatches to the
    appropriate handler function. Each subcommand must set a 'handler'
    attribute via set_defaults().

    Returns:
        int: Exit code (0 = success, 1 = command error, 2 = no command given).
    """
    parser = build_parser()
    args = parser.parse_args()

    if not hasattr(args, "handler"):
        parser.print_help()
        return 2

    try:
        return args.handler(args)
    except CommandError as exc:
        print(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
