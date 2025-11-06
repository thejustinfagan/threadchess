"""
Logging configuration for Battle Dinghy bot.

This module provides centralized logging configuration for all bot components.
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime


def setup_logging(
    log_level=logging.INFO,
    log_to_file=True,
    log_to_console=True,
    log_dir="logs",
    max_bytes=10485760,  # 10MB
    backup_count=5
):
    """
    Set up logging configuration for the bot.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_file: Whether to log to file
        log_to_console: Whether to log to console
        log_dir: Directory to store log files
        max_bytes: Maximum size of each log file before rotation
        backup_count: Number of backup log files to keep

    Returns:
        logging.Logger: Configured logger instance
    """
    # Create logs directory if it doesn't exist
    if log_to_file and not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Create logger
    logger = logging.getLogger('battle_dinghy')
    logger.setLevel(log_level)

    # Clear existing handlers to avoid duplicates
    logger.handlers = []

    # Create formatters
    detailed_formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    simple_formatter = logging.Formatter(
        fmt='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler
    if log_to_console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        console_handler.setFormatter(simple_formatter)
        logger.addHandler(console_handler)

    # File handler with rotation
    if log_to_file:
        # Create timestamped log filename
        log_filename = os.path.join(
            log_dir,
            f"battle_dinghy_{datetime.now().strftime('%Y%m%d')}.log"
        )

        file_handler = RotatingFileHandler(
            log_filename,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(detailed_formatter)
        logger.addHandler(file_handler)

    # Error file handler (only ERROR and CRITICAL)
    if log_to_file:
        error_log_filename = os.path.join(
            log_dir,
            f"battle_dinghy_errors_{datetime.now().strftime('%Y%m%d')}.log"
        )

        error_handler = RotatingFileHandler(
            error_log_filename,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(detailed_formatter)
        logger.addHandler(error_handler)

    # Log startup message
    logger.info("=" * 60)
    logger.info("Battle Dinghy Bot - Logging initialized")
    logger.info(f"Log level: {logging.getLevelName(log_level)}")
    logger.info(f"Log to file: {log_to_file}")
    logger.info(f"Log to console: {log_to_console}")
    if log_to_file:
        logger.info(f"Log directory: {log_dir}")
    logger.info("=" * 60)

    return logger


def get_logger(name=None):
    """
    Get a logger instance.

    Args:
        name: Name for the logger (defaults to 'battle_dinghy')

    Returns:
        logging.Logger: Logger instance
    """
    if name:
        return logging.getLogger(f'battle_dinghy.{name}')
    return logging.getLogger('battle_dinghy')


# Example usage functions
def log_game_start(logger, game_number, player1, player2, thread_id):
    """Log game start event."""
    logger.info(f"Game #{game_number} started: {player1} vs {player2} (thread: {thread_id})")


def log_game_end(logger, game_number, winner, thread_id, total_moves):
    """Log game end event."""
    logger.info(f"Game #{game_number} completed: Winner {winner} in {total_moves} moves (thread: {thread_id})")


def log_shot(logger, game_number, player, coordinate, result):
    """Log shot event."""
    logger.debug(f"Game #{game_number}: {player} fired at {coordinate} -> {result}")


def log_api_error(logger, api_name, error, context=""):
    """Log API error."""
    logger.error(f"{api_name} API error{': ' + context if context else ''}: {error}")


def log_database_error(logger, operation, error):
    """Log database error."""
    logger.error(f"Database error during {operation}: {error}")


def log_rate_limit(logger, api_name, reset_time=None):
    """Log rate limit hit."""
    if reset_time:
        logger.warning(f"{api_name} rate limit hit. Resets at {reset_time}")
    else:
        logger.warning(f"{api_name} rate limit hit")


# Configuration presets
PRODUCTION_CONFIG = {
    'log_level': logging.INFO,
    'log_to_file': True,
    'log_to_console': True,
    'log_dir': 'logs',
    'max_bytes': 10485760,  # 10MB
    'backup_count': 10
}

DEVELOPMENT_CONFIG = {
    'log_level': logging.DEBUG,
    'log_to_file': True,
    'log_to_console': True,
    'log_dir': 'logs',
    'max_bytes': 5242880,  # 5MB
    'backup_count': 3
}

TESTING_CONFIG = {
    'log_level': logging.DEBUG,
    'log_to_file': False,
    'log_to_console': True,
}


if __name__ == "__main__":
    # Demo logging setup
    print("Setting up logging with default configuration...")

    logger = setup_logging(**DEVELOPMENT_CONFIG)

    # Test different log levels
    logger.debug("This is a DEBUG message")
    logger.info("This is an INFO message")
    logger.warning("This is a WARNING message")
    logger.error("This is an ERROR message")
    logger.critical("This is a CRITICAL message")

    # Test helper functions
    log_game_start(logger, 42, "@player1", "@player2", "1234567890")
    log_shot(logger, 42, "@player1", "A5", "Hit!")
    log_api_error(logger, "Twitter", "Rate limit exceeded", "while fetching user")
    log_game_end(logger, 42, "@player1", "1234567890", 25)

    print("\nLogging demo complete. Check the 'logs' directory for log files.")
