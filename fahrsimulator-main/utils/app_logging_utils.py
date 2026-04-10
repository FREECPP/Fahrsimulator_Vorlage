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

    match level:
        case "DEBUG": logging.debug(message)
        case "INFO": logging.info(message)
        case "WARNING": logging.warning(message)
        case "ERROR": logging.error(message)
        case "CRITICAL": logging.critical(message)
        case "EXCEPTION": logging.exception(message)
        case _: logging.info(message)

    if std_print:
        print(f"{message}")
