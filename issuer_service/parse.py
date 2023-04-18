from argparse import BooleanOptionalAction

import configargparse

from .presets import *


def init_argparser():
    """Initialize argparser."""

    parser = configargparse.get_argument_parser(
        prog="issuer_service",
        description="Start the NC Issuer Service HTTP Server.",
        config_file_parser_class=configargparse.YAMLConfigFileParser,
    )

    parser.add_argument(
        "--arg-file",
        metavar="FILE",
        is_config_file=True,
        help="config file in YAML syntax",
    )
    parser.add_argument(
        "--host",
        type=str,
        env_var="WEBAPP_HOST",
        help=f"IP or hostname",
        default=DEFAULT_HOST,
    )
    parser.add_argument(
        "--port",
        type=int,
        env_var="WEBAPP_PORT",
        help=f"Port to listen to",
        default=DEFAULT_PORT,
    )
    parser.add_argument(
        "--agent-admin-api",
        metavar="URL",
        type=str,
        env_var="WEBAPP_AGENT_ADMIN_API",
        help="URL where agent admin api is located",
        required=True,
    )
    parser.add_argument(
        "--issuance-timeout",
        metavar="SECONDS",
        type=float,
        env_var="WEBAPP_ISSUANCE_TIMEOUT",
        help=(
            "Period during which the issuance flow must be completed. "
            "After a timeout, the invitation becomes invalid."
        ),
    )
    parser.add_argument(
        "--auto-remove-conn-record",
        action=BooleanOptionalAction,
        default=AUTO_REMOVE_CONN_RECORD,
        help="remove connection record after issuance or timeout",
    )
    parser.add_argument(
        "--did-seed",
        metavar="SEED",
        type=str,
        env_var="DID_SEED",
        help="seed to use for did creation",
    )
    parser.add_argument(
        "--oob-base-url",
        metavar="URL",
        type=str,
        env_var="WEBAPP_OOB_BASE_URL",
        help="url used to construct invitation url",
    )
    excl_group = parser.add_mutually_exclusive_group()
    excl_group.add_argument(
        "--log-level",
        choices=["debug", "info", "warning", "error", "critical"],
        default=DEFAULT_LOG_LEVEL,
        env_var="WEBAPP_LOG_LEVEL",
    )
    excl_group.add_argument(
        "--log-config", type=str, metavar="FILE", help="log config file in JSON format"
    )

    return parser
