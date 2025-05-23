import logging
from colorama import Fore, Style, init

init(autoreset=True)

LEVEL_COLORS = {
    logging.DEBUG:    Fore.CYAN,
    logging.INFO:     Fore.GREEN,
    logging.WARNING:  Fore.YELLOW,
    logging.ERROR:    Fore.RED,
    logging.CRITICAL: Fore.MAGENTA + Style.BRIGHT,
}

class ColorFormatter(logging.Formatter):
    LEVEL_WIDTH = 8     
    NAME_WIDTH  = 20     

    def format(self, record):
        original_levelname = record.levelname
        original_name = record.name

        padded_level = original_levelname.center(self.LEVEL_WIDTH)
        record.name = original_name.center(self.NAME_WIDTH)

        color = LEVEL_COLORS.get(record.levelno, "")
        record.levelname = f"{color}{padded_level}{Style.RESET_ALL}"

        try:
            return super().format(record)
        finally:
            record.levelname = original_levelname
            record.name = original_name


def create_logger(name: str = __name__, prefix: str = None, level: int = logging.INFO) -> logging.Logger:
    fmt = "%(asctime)s | %(name)s | %(levelname)s | [{}] %(message)s".format(prefix)
    datefmt = "%Y-%m-%d %H:%M:%S"

    console = logging.StreamHandler()
    console.setFormatter(ColorFormatter(fmt, datefmt=datefmt))

    file_ = logging.FileHandler("app.log", encoding="utf-8")
    file_.setFormatter(logging.Formatter(fmt, datefmt=datefmt))

    root = logging.getLogger()
    if not root.handlers:           
        root.setLevel(level)
        root.addHandler(console)
        root.addHandler(file_)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.handlers:         
        logger.addHandler(console)
        logger.addHandler(file_)

    logger.propagate = False        
    return logger
