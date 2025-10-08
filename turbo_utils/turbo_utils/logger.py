import logging
from pathlib import Path

def setup_simple_logging(logging_folder: Path):
    """Sets the formatting and destination files for the logging output"""
    format_string = "%(asctime)s - %(name)s - %(levelname)s > %(message)s"
    formatter = logging.Formatter(format_string)

    full_log_handler = logging.FileHandler(logging_folder / "full.log", 'a', 'utf-8')
    full_log_handler.setLevel(logging.DEBUG)
    full_log_handler.setFormatter(formatter)

    logging.basicConfig(handlers=[full_log_handler],
                level=logging.DEBUG)


def setup_multilevel_logging(logging_folder: Path):
    """Sets the formatting and destination files for the logging output"""
    format_string = "%(asctime)s - %(name)s - %(levelname)s > %(message)s"
    formatter = logging.Formatter(format_string)

    full_log_handler = logging.FileHandler(logging_folder / "full.log", 'a', 'utf-8')
    full_log_handler.setLevel(logging.DEBUG)
    full_log_handler.setFormatter(formatter)

    normal_log_handler = logging.FileHandler(logging_folder / "normal.log", 'a', 'utf-8')
    normal_log_handler.setLevel(logging.INFO)
    normal_log_handler.setFormatter(formatter)

    error_log_handler = logging.FileHandler(logging_folder / "error.log", 'a', 'utf-8')
    error_log_handler.setLevel(logging.WARNING)
    error_log_handler.setFormatter(formatter)

    logging.basicConfig(handlers=[full_log_handler, normal_log_handler, error_log_handler],
                    level=logging.DEBUG)

    logging.getLogger('werkzeug').setLevel(logging.INFO)
    logging.getLogger('urllib3').setLevel(logging.INFO)
    logging.getLogger('sewpy.sewpy').setLevel(logging.ERROR)
    logging.getLogger('matplotlib').setLevel(logging.INFO)
    logging.getLogger('PIL.Image').setLevel(logging.INFO)
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    
