import logging

import coloredlogs

APPLICATION_NAME = "DJANGO-RAG-ANALYTICS"

logger = logging.getLogger(APPLICATION_NAME)
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
console_handler.setFormatter(
    logging.Formatter(
        "[%(asctime)s]::[%(levelname)s]::[%(module)s]::[%(funcName)s]::%(message)s"
    )
)
logger.addHandler(console_handler)


# Configure coloredlogs
coloredlogs.install(
    level="DEBUG",
    logger=logger,
    fmt="[%(asctime)s]::[%(levelname)s]::[%(module)s]::[%(funcName)s]::%(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level_styles={
        "debug": {"color": "blue"},
        "info": {"color": "green"},
        "warning": {"color": "yellow"},
        "error": {"color": "red"},
        "critical": {"color": "red", "bold": True},
    },
    field_styles={
        "asctime": {"color": "cyan"},
        "levelname": {"color": "white", "bold": True},
        "module": {"color": "magenta"},
        "funcName": {"color": "blue"},
        "message": {"color": "white"},
    },
)
