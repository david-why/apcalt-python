from flask import current_app


def get_logger():
    return current_app.logger
