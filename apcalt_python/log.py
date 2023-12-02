from quart import current_app


def get_logger():
    return current_app.logger
