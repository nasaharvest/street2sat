from datetime import datetime


def current_time() -> str:
    return datetime.now().strftime("%B %d, %Y at %H:%M:%S")
