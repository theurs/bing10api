#!/usr/bin/env python3

import functools
import threading
import re


def async_run(func):
    '''Декоратор для запуска функции в отдельном потоке, асинхронно'''
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        thread = threading.Thread(target=func, args=args, kwargs=kwargs)
        thread.start()
    return wrapper


def replace_non_letters_with_spaces(text: str) -> str:
    """
    Replaces all characters in a string with spaces, except for letters and spaces.

    Args:
        text: The input string.

    Returns:
        A new string with non-letter and non-space characters replaced by spaces.
    """
    result = []
    for char in text:
        if char.isalpha():
            result.append(char)
        else:
            result.append(' ')
    r = "".join(result)
    #remove redundant spaces
    r = re.sub(' +', ' ', r)
    return r.strip()


def seconds_to_hms(seconds: int) -> str:
    """Converts seconds to a human-readable string with hours, minutes, and seconds."""
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0:
        return f"{hours} hr {minutes} min {seconds} sec"
    else:
        return f"{minutes} min {seconds} sec"


if __name__ == '__main__':
    pass
