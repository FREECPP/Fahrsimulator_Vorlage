import logging

logging.basicConfig(
    filename='fahrsimulator.log',
    filemode="w", # Ändern zu "a" für 'append' um die logs anzuhängen!
    encoding='utf-8',
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)


def printlog(message: str, debug_lvl: str = "INFO", std_print: bool = True) -> None:
    level = debug_lvl.upper()

    if level == "DEBUG":
        logging.debug(message)
    elif level == "INFO":
        logging.info(message)
    elif level == "WARNING":
        logging.warning(message)
    elif level == "ERROR":
        logging.error(message)
    elif level == "CRITICAL":
        logging.critical(message)
    elif level == "EXCEPTION":
        logging.exception(message)
    else:
        logging.info(message)

    if std_print:
        print(f"{message}")
