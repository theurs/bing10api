#!/usr/bin/env python3
# pip install -U unidecode


import os
import datetime
import threading


import cfg


lock = threading.Lock()


if not os.path.exists('logs'):
    os.mkdir('logs')


def trancate_log_file(log_file_path: str):
    """
    Truncates the log file at the given file path if it exceeds the maximum file size.

    Parameters:
        log_file_path (str): The path to the log file.

    Returns:
        None

    This function checks if the log file exists and if its size exceeds the maximum file size.
    If it does, it opens the file in read and write mode and truncates it by keeping only the
    last half of the data. The function uses the os module to check the file path and the cfg
    module to get the maximum file size if it is defined.

    Note:
        The function assumes that the log file is in UTF-8 encoding.
    """
    try:
        if not os.path.exists(log_file_path):
            return
        fsize = os.path.getsize(log_file_path)
        max_fsize = cfg.MAX_LOG_FILE_SIZE if hasattr(cfg, 'MAX_LOG_FILE_SIZE') else 20*1024*1024
        if fsize > max_fsize:
            with open(log_file_path, 'r+') as f:
                f.seek(fsize - max_fsize // 2) # Переходим к середине от превышения размера
                data = f.read() # Читаем оставшиеся данные
                f.seek(0) # Переходим в начало файла
                f.write(data) # Записываем последние данные
                f.truncate(len(data)) # Обрезаем файл        
    except Exception as unknown:
        print(f'my_log:trancate_log_file: {unknown}')


def log2(text: str, fname: str = '') -> None:
    """
    Writes the given text to a log file.

    Args:
        text (str): The text to be written to the log file.
        fname (str, optional): The name of the log file. Defaults to an empty string.

    Returns:
        None: This function does not return anything.

    This function writes the given text to a log file. If the `fname` parameter is provided,
    the log file will be named `debug-{fname}.log`, otherwise it will be named `debug.log`.
    The function checks the value of the `LOG_MODE` variable and writes the text to the log
    file accordingly. If `LOG_MODE` is 1, the text is appended to the log file located at
    `logs/debug-{fname}.log`. If `LOG_MODE` is 0, the text is appended to both the log
    files located at `logs/debug-{fname}.log` and `logs2/debug-{fname}.log`. After writing
    the text, the function calls the `truncate_log_file` function to truncate the log file
    if it exceeds the maximum size defined in the `cfg` module.

    Note:
        The function assumes that the log files are in UTF-8 encoding.
    """
    with lock:
        time_now = datetime.datetime.now().strftime('%d-%m-%Y %H:%M:%S')
        if fname:
            log_file_path = f'logs/debug_{fname}.log'
        else:
            log_file_path = 'logs/debug.log'
        open(log_file_path, 'a', encoding="utf-8").write(f'{time_now}\n\n{text}\n{"=" * 80}\n')
        trancate_log_file(log_file_path)


def log_bing_api(text: str) -> None:
    """для логов bingapi"""
    log2(text, 'bing_api')


def log_bing_img(text: str) -> None:
    """для логов bingimg"""
    log2(text, 'bing_img')


def log_bing_success(text: str) -> None:
    """для логов bing_success"""
    log2(text, 'bing_success')


if __name__ == '__main__':
    pass
