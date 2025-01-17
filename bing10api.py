#!/usr/bin/env python3

import time

from flask import Flask, request, jsonify
from typing import Any, Dict, List

import cfg
import my_genimg
import my_log

import rotate_cookie
from utils import async_run


# сколько раз подряд должно быть фейлов что бы приняьт меры - сменить куки
MAX_COOKIE_FAIL = 5
COOKIE_FAIL = 0
COOKIE_INITIALIZED = False


## rest api #######################################################################


# API для доступа к генератору картинок бинг
FLASK_APP = Flask(__name__)


def bing(j: Dict[str, Any], iterations=1) -> Dict[str, Any]:
    '''
    Делает 1 запрос на рисование бингом.
    Если не получилось - возвращает ошибку.
    Если не получилось 5 раз подряд то пытается сменить куки.
    '''
    try:
        global COOKIE_FAIL, COOKIE_INITIALIZED

        if not COOKIE_INITIALIZED:
            rotate_cookie.rotate_cookie()
            COOKIE_INITIALIZED = True

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

            if COOKIE_FAIL >= MAX_COOKIE_FAIL:
                COOKIE_FAIL = 0
                rotate_cookie.rotate_cookie()

            return jsonify({"error": "No images generated"}), 404
        else:
            COOKIE_FAIL = 0

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
        FLASK_APP.run(debug=True, use_reloader=False, host=addr, port = port)
    except Exception as error:
        my_log.log_bing_api(f'tb:run_flask: {error}')


## rest api #######################################################################


if __name__ == '__main__':
    run_flask(addr=cfg.ADDR, port=cfg.PORT)

    while 1:
        time.sleep(1)



# curl -X POST   -H "Content-Type: application/json"   -d '{
#     "prompt": "a beautiful landscape"
#   }'   http://172.28.1.6:58796/bing2
