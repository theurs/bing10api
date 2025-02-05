#!/usr/bin/env python3

import time

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


## rest api #######################################################################


# API для доступа к генератору картинок бинг
FLASK_APP = Flask(__name__)


def bing(j: Dict[str, Any], iterations=1) -> Dict[str, Any]:
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
        image_urls: List[str] = my_genimg.gen_images_bing_only(prompt, iterations)

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

    x10 times bing repeat

    :return: A JSON response containing a list of URLs or an error message.
    """
    return bing(request.get_json(), 20)


@FLASK_APP.route('/bing2', methods=['POST'])
def bing_api_post2() -> Dict[str, Any]:
    """
    API endpoint for generating images using Bing.

    x10 times bing repeat

    :return: A JSON response containing a list of URLs or an error message.
    """
    return bing(request.get_json(), 2)


@FLASK_APP.route('/bing', methods=['POST'])
def bing_api_post() -> Dict[str, Any]:
    """
    API endpoint for generating images using Bing.

    x10 times bing repeat

    :return: A JSON response containing a list of URLs or an error message.
    """
    return bing(request.get_json(), 1)


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
