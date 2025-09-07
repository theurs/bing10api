#!/usr/bin/env python3

import subprocess
import time
import traceback 

from flask import Flask, request, jsonify
from typing import Any, Dict, List

import cfg
import my_genimg
import my_log

import rotate_cookie
from utils import async_run, seconds_to_hms


# сколько раз подряд должно быть фейлов что бы принять меры - сменить куки
MAX_COOKIE_FAIL = 5
COOKIE_FAIL = 0
COOKIE_INITIALIZED = False
# сколько раз подряд должно быть фейлов что бы принять меры - выключить сервис
MAX_COOKIE_FAIL_FOR_TERMINATE = 20
COOKIE_FAIL_FOR_TERMINATE = 0
SUSPEND_TIME = 0 # время когда можно снова запустить сервис
SUSPEND_TIME_SET = 12 * 60 * 60 # время в секундах до следующего запуска сервиса (12 часов)

# после такого количества запросов принудительно сменить куки
MAX_REQUESTS_BEFORE_ROTATE_COOKIE = 50
REQUESTS_BEFORE_ROTATE_COOKIE = 0


def get_last_attempts(log_file: str = 'logs/debug_bing_api.log', num_attempts: int = 10) -> list[dict[str, str]]:
    """
    Parses the log file to get the status of the last N attempts.
    Robust version that handles multi-line log entries.
    """
    if not os.path.exists(log_file):
        return [{"time": "N/A", "status": "LOG NOT FOUND"}]

    attempts = []
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception:
        return [{"time": "N/A", "status": "LOG READ ERROR"}]

    # Pre-find all lines that are timestamps to make searching faster
    timestamp_indices = {i for i, line in enumerate(lines) if re.match(r'^\d{2}-\d{2}-\d{4}', line)}

    for i in range(len(lines) - 1, -1, -1):
        if len(attempts) >= num_attempts:
            break

        line = lines[i].strip()

        status = None
        # Success markers
        if 'bing_genimg_v3:process: [' in line and "http" in line:
            status = "OK"
        # Failure markers
        elif ('bing_genimg_v3:process: []' in line or
              '==> Error occurs' in line or
              '"error": "No images generated"' in line):
            status = "FAIL"
        # Generic traceback error marker
        elif 'Traceback (most recent call last):' in line or 'tb:' in line:
            status = "ERROR"

        if status:
            # Find the timestamp associated with this event by looking backwards
            timestamp = "N/A"
            for ts_index in range(i, -1, -1):
                if ts_index in timestamp_indices:
                    timestamp = lines[ts_index].strip()
                    break
            attempts.append({"time": timestamp, "status": status})

    return attempts


def get_current_cookie(log_file: str = 'logs/debug.log') -> str:
    """
    Parses the log file to find the last used cookie file name.
    """
    if not os.path.exists(log_file):
        return "LOG NOT FOUND"

    last_cookie_line = "Unknown"
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            for line in reversed(list(f)):
                if 'rotate_cookie:' in line and '-> cookie.txt' in line:
                    # Extract the source cookie filename
                    match = re.search(r'rotate_cookie: (cookie.*?.txt) ->', line)
                    if match:
                        last_cookie_line = match.group(1)
                        break
    except Exception:
        return "LOG READ ERROR"
    return last_cookie_line


## rest api #######################################################################


# API для доступа к генератору картинок бинг
FLASK_APP = Flask(__name__)


def bing(j: Dict[str, Any], iterations=1, model: str = 'dalle') -> Dict[str, Any]:
    '''
    Делает 1 запрос на рисование бингом.
    Если не получилось - возвращает ошибку.
    Если не получилось 5 раз подряд то пытается сменить куки.
    Если не получилось 20 раз подряд то выключает сервис на 12 часов.
    '''
    try:
        global COOKIE_FAIL, COOKIE_INITIALIZED, COOKIE_FAIL_FOR_TERMINATE, SUSPEND_TIME
        global REQUESTS_BEFORE_ROTATE_COOKIE

        if COOKIE_FAIL_FOR_TERMINATE >= MAX_COOKIE_FAIL_FOR_TERMINATE:
            if SUSPEND_TIME and SUSPEND_TIME > time.time():
                return jsonify({"error": "Service is disabled, time to next start is " + seconds_to_hms(int(SUSPEND_TIME - time.time())) + " seconds"}), 500
            elif SUSPEND_TIME == 0:
                SUSPEND_TIME = time.time() + SUSPEND_TIME_SET
                my_log.log2(f'Suspend service: {seconds_to_hms(int(SUSPEND_TIME_SET))}')

                # Проверку и выполнение команды из cfg.CMD_ON_STOP
                if hasattr(cfg, 'CMD_ON_STOP') and cfg.CMD_ON_STOP:
                    try:
                        my_log.log2(f'Executing CMD_ON_STOP: {cfg.CMD_ON_STOP}')
                        subprocess.Popen(cfg.CMD_ON_STOP, shell=True)
                    except Exception as cmd_e:
                        my_log.log2(f'Error executing CMD_ON_STOP: {cmd_e}')

                return jsonify({"error": "Service is disabled for " + seconds_to_hms(int(SUSPEND_TIME_SET)) + " seconds"}), 500
            elif SUSPEND_TIME and SUSPEND_TIME < time.time():
                my_log.log2(f'Restart service')
                SUSPEND_TIME = 0
                COOKIE_FAIL_FOR_TERMINATE = 0
                COOKIE_FAIL = 0

        if not COOKIE_INITIALIZED:
            rotate_cookie.rotate_cookie()
            COOKIE_INITIALIZED = True


        # # принудительно сменить куки после определенного количества запросов
        # if REQUESTS_BEFORE_ROTATE_COOKIE > MAX_REQUESTS_BEFORE_ROTATE_COOKIE:
        #     rotate_cookie.rotate_cookie()
        #     REQUESTS_BEFORE_ROTATE_COOKIE = 0
        #     COOKIE_FAIL = 0
        #     COOKIE_FAIL_FOR_TERMINATE = 0
        #     my_log.log2(f'rotate_cookie: after {MAX_REQUESTS_BEFORE_ROTATE_COOKIE} requests')
        # else:
        #     REQUESTS_BEFORE_ROTATE_COOKIE += 1


        # Get JSON data from the request
        data: Dict[str, Any] = j

        # Extract the prompt from the JSON data
        prompt: str = data.get('prompt', '')

        if not prompt:
            return jsonify({"error": "Prompt is required"}), 400

        # Generate images using Bing API
        image_urls: List[str] = my_genimg.gen_images_bing_only(prompt, iterations, model=model)

        if not image_urls:
            COOKIE_FAIL += 1
            COOKIE_FAIL_FOR_TERMINATE += 1

            if COOKIE_FAIL >= MAX_COOKIE_FAIL:
                COOKIE_FAIL = 0
                rotate_cookie.rotate_cookie()

            return jsonify({"error": "No images generated"}), 404
        else:
            COOKIE_FAIL = 0
            COOKIE_FAIL_FOR_TERMINATE = 0

        return jsonify({"urls": image_urls}), 200
    except Exception as e:
        my_log.log_bing_api(f'tb:bing: {e}')
        return jsonify({"error": str(e)}), 500


@FLASK_APP.route('/reload_cookies', methods=['POST'])
def reload_cookies_api() -> Dict[str, Any]:
    """
    API endpoint for reloading Bing cookies.

    :return: A JSON response indicating success or failure.
    """
    try:
        rotate_cookie.rotate_cookie()
        global COOKIE_FAIL, COOKIE_INITIALIZED, COOKIE_FAIL_FOR_TERMINATE, REQUESTS_BEFORE_ROTATE_COOKIE
        COOKIE_FAIL = 0
        COOKIE_INITIALIZED = True
        COOKIE_FAIL_FOR_TERMINATE = 0
        REQUESTS_BEFORE_ROTATE_COOKIE = 0
        my_log.log2('Cookies reloaded successfully via API.')
        return jsonify({"message": "Cookies reloaded successfully"}), 200
    except Exception as e:
        my_log.log_bing_api(f'tb:reload_cookies_api: {e}')
        return jsonify({"error": str(e)}), 500


@FLASK_APP.route('/bing10', methods=['POST'])
def bing_api_post10() -> Dict[str, Any]:
    """
    API endpoint for generating images using Bing.

    x10 times bing repeat

    :return: A JSON response containing a list of URLs or an error message.
    """
    return bing(request.get_json(), 10)


@FLASK_APP.route('/bing20', methods=['POST'])
def bing_api_post20() -> Dict[str, Any]:
    """
    API endpoint for generating images using Bing.

    x20 times bing repeat

    :return: A JSON response containing a list of URLs or an error message.
    """
    return bing(request.get_json(), 20)


@FLASK_APP.route('/bing2', methods=['POST'])
def bing_api_post2() -> Dict[str, Any]:
    """
    API endpoint for generating images using Bing.

    x2 times bing repeat

    :return: A JSON response containing a list of URLs or an error message.
    """
    return bing(request.get_json(), 2)


@FLASK_APP.route('/bing', methods=['POST'])
def bing_api_post() -> Dict[str, Any]:
    """
    API endpoint for generating images using Bing.

    :return: A JSON response containing a list of URLs or an error message.
    """
    return bing(request.get_json(), 1)


@FLASK_APP.route('/bing_gpt', methods=['POST'])
def bing_api_post_gpt() -> Dict[str, Any]:
    """
    API endpoint for generating images using Bing with gpt.

    :return: A JSON response containing a list of URLs or an error message.
    """
    return bing(request.get_json(), 1, model='gpt4o')


@FLASK_APP.route('/status', methods=['GET'])
def status_api() -> Dict[str, Any]:
    """
    API endpoint for getting the current status of the service.
    Now with error handling.
    """
    try:
        status_data = {
            "service_status": "OK",
            "cookie_fail_count": COOKIE_FAIL,
            "total_fail_count": COOKIE_FAIL_FOR_TERMINATE,
            "max_fail_for_rotate": MAX_COOKIE_FAIL,
            "max_fail_for_suspend": MAX_COOKIE_FAIL_FOR_TERMINATE,
            "requests_before_rotate": f"{REQUESTS_BEFORE_ROTATE_COOKIE}/{MAX_REQUESTS_BEFORE_ROTATE_COOKIE}",
            "current_cookie": get_current_cookie(),
            "last_attempts": get_last_attempts(),
        }

        if COOKIE_FAIL_FOR_TERMINATE >= MAX_COOKIE_FAIL_FOR_TERMINATE and SUSPEND_TIME > time.time():
            status_data["service_status"] = "SUSPENDED"
            status_data["time_to_restart"] = seconds_to_hms(int(SUSPEND_TIME - time.time()))

        return jsonify(status_data), 200
    except Exception as e:
        error_details = traceback.format_exc()
        my_log.log_bing_api(f'tb:status_api: {e}\n{error_details}')
        return jsonify({"error": "Failed to get status", "details": str(e)}), 500


@async_run
def run_flask(addr: str ='127.0.0.1', port: int = 58796):
    try:
        FLASK_APP.run(debug=False, use_reloader=False, host=addr, port = port)
    except Exception as error:
        my_log.log_bing_api(f'tb:run_flask: {error}')


## rest api #######################################################################


if __name__ == '__main__':
    run_flask(addr=cfg.ADDR, port=cfg.PORT)
    my_log.log2(f'run_flask: {cfg.ADDR}:{cfg.PORT} started')
    while 1:
        time.sleep(1)



# curl -X POST   -H "Content-Type: application/json"   -d '{
#     "prompt": "a beautiful landscape"
#   }'   http://172.28.1.6:58796/bing2
