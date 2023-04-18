import json
import logging

logger = logging.getLogger(__name__)


def configure_logger(log_level: str, config_file: str = None):
    def apply_basic_logger_config():
        logging.basicConfig(
            level=log_level.upper(),
            format="%(asctime)s %(levelname)-8s %(name)s : %(message)s",
        )

    if config_file:
        try:
            with open(config_file, "r") as conf:
                log_config = json.loads(conf.read())
            logging.config.dictConfig(log_config)
        except Exception as e:
            apply_basic_logger_config()
            logger.warning(e)
            logger.warning("falling back to basic logger config")
    else:
        apply_basic_logger_config()
        logger.info("using basic logger config")
