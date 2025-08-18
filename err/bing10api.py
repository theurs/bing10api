#!/usr/bin/env python3

import subprocess
import time

from flask import Flask, request, jsonify
from typing import Any, Dict, List

import cfg
import my_genimg
import my_log

import rotate_cookie
from utils import async_run, seconds_to_hms


# --- State Management Configuration ---

# Max consecutive failures before trying to rotate the cookie for a model
MAX_COOKIE_FAIL = 5
# Max consecutive failures before suspending the service for a model
MAX_COOKIE_FAIL_FOR_TERMINATE = 20
# Time in seconds to suspend the service before the next attempt (12 hours)
SUSPEND_TIME_SET = 12 * 60 * 60


# State management for different models
MODEL_STATE: Dict[str, Dict[str, Any]] = {
    'dalle': {
        "fail_count": 0,
        "initialized": False,
        "terminate_fail_count": 0,
        "suspend_time": 0,
    },
    'gpt4o': {
        "fail_count": 0,
        "initialized": False,
        "terminate_fail_count": 0,
        "suspend_time": 0,
    }
}


## rest api #######################################################################


# API for accessing the Bing image generator
FLASK_APP = Flask(__name__)


def bing(j: Dict[str, Any], iterations: int = 1, model: str = 'dalle') -> Any:
    '''
    Makes 1 request to Bing for drawing.
    If it fails, it returns an error.
    If it fails 5 times in a row, it tries to change the cookies for that model.
    If it fails 20 times in a row, it disables the service for that model for 12 hours.
    '''
    try:
        # Get state for the current model
        if model not in MODEL_STATE:
            return jsonify({"error": f"Model '{model}' is not supported"}), 400
        state = MODEL_STATE[model]

        # Check for service suspension for this model
        if state["terminate_fail_count"] >= MAX_COOKIE_FAIL_FOR_TERMINATE:
            if state["suspend_time"] and state["suspend_time"] > time.time():
                error_msg = f"Service for model '{model}' is disabled, time to next start is {seconds_to_hms(int(state['suspend_time'] - time.time()))}"
                return jsonify({"error": error_msg}), 500
            elif state["suspend_time"] == 0:
                state["suspend_time"] = time.time() + SUSPEND_TIME_SET
                my_log.log2(f'Suspend service for model {model}: {seconds_to_hms(int(SUSPEND_TIME_SET))}')

                # Check and execute command from cfg.CMD_ON_STOP
                if hasattr(cfg, 'CMD_ON_STOP') and cfg.CMD_ON_STOP:
                    try:
                        my_log.log2(f'Executing CMD_ON_STOP: {cfg.CMD_ON_STOP}')
                        subprocess.Popen(cfg.CMD_ON_STOP, shell=True)
                    except Exception as cmd_e:
                        my_log.log2(f'Error executing CMD_ON_STOP: {cmd_e}')

                return jsonify({"error": f"Service for model '{model}' is disabled for {seconds_to_hms(int(SUSPEND_TIME_SET))}"}), 500
            elif state["suspend_time"] and state["suspend_time"] < time.time():
                my_log.log2(f'Restart service for model {model}')
                state["suspend_time"] = 0
                state["terminate_fail_count"] = 0
                state["fail_count"] = 0

        if not state["initialized"]:
            rotate_cookie.rotate_cookie(model=model)
            state["initialized"] = True

        # Get JSON data from the request
        data: Dict[str, Any] = j
        prompt: str = data.get('prompt', '')

        if not prompt:
            return jsonify({"error": "Prompt is required"}), 400

        # Generate images using Bing API
        image_urls: List[str] = my_genimg.gen_images_bing_only(prompt, iterations, model=model)

        if not image_urls:
            state["fail_count"] += 1
            state["terminate_fail_count"] += 1

            if state["fail_count"] >= MAX_COOKIE_FAIL:
                state["fail_count"] = 0
                my_log.log2(f"Rotating cookie for model '{model}' due to failures.")
                rotate_cookie.rotate_cookie(model=model)

            return jsonify({"error": "No images generated"}), 404
        else:
            # Reset counters on success
            state["fail_count"] = 0
            state["terminate_fail_count"] = 0

        return jsonify({"urls": image_urls}), 200
    except Exception as e:
        my_log.log_bing_api(f'tb:bing: {e}')
        return jsonify({"error": str(e)}), 500


def _reload_model_cookie(model: str) -> Any:
    """
    Helper function to reload cookies and reset state for a specific model.

    :param model: The name of the model to reload ('dalle', 'gpt4o').
    :return: A Flask response object.
    """
    if model not in MODEL_STATE:
        return jsonify({"error": f"Model '{model}' not found"}), 404

    try:
        rotate_cookie.rotate_cookie(model=model)
        state = MODEL_STATE[model]
        state["fail_count"] = 0
        state["initialized"] = True
        state["terminate_fail_count"] = 0
        state["suspend_time"] = 0
        my_log.log2(f"Cookies for model '{model}' reloaded successfully via API.")
        return jsonify({"message": f"Cookies for model '{model}' reloaded successfully"}), 200
    except Exception as e:
        my_log.log_bing_api(f'tb:_reload_model_cookie ({model}): {e}')
        return jsonify({"error": str(e)}), 500


@FLASK_APP.route('/reload_cookies', methods=['POST'])
def reload_cookies_api() -> Any:
    """
    API endpoint for reloading Bing cookies for all models.

    :return: A JSON response indicating success or failure for all models.
    """
    results = {}
    overall_status_code = 200
    for model in MODEL_STATE:
        response_obj = _reload_model_cookie(model)
        results[model] = response_obj.get_json()
        if response_obj.status_code != 200:
            overall_status_code = 500

    return jsonify(results), overall_status_code


@FLASK_APP.route('/reload_dalle', methods=['POST'])
def reload_dalle_api() -> Any:
    """
    API endpoint for reloading Bing cookies for the 'dalle' model.
    """
    return _reload_model_cookie('dalle')


@FLASK_APP.route('/reload_gpt4o', methods=['POST'])
def reload_gpt4o_api() -> Any:
    """
    API endpoint for reloading Bing cookies for the 'gpt4o' model.
    """
    return _reload_model_cookie('gpt4o')


@FLASK_APP.route('/bing10', methods=['POST'])
def bing_api_post10() -> Any:
    """
    API endpoint for generating images using Bing (dalle).
    x10 times bing repeat
    """
    return bing(request.get_json(), 10, model='dalle')


@FLASK_APP.route('/bing20', methods=['POST'])
def bing_api_post20() -> Any:
    """
    API endpoint for generating images using Bing (dalle).
    x20 times bing repeat
    """
    return bing(request.get_json(), 20, model='dalle')


@FLASK_APP.route('/bing2', methods=['POST'])
def bing_api_post2() -> Any:
    """
    API endpoint for generating images using Bing (dalle).
    x2 times bing repeat
    """
    return bing(request.get_json(), 2, model='dalle')


@FLASK_APP.route('/bing', methods=['POST'])
def bing_api_post() -> Any:
    """
    API endpoint for generating images using Bing (dalle).
    """
    return bing(request.get_json(), 1, model='dalle')


@FLASK_APP.route('/bing_gpt', methods=['POST'])
def bing_api_post_gpt() -> Any:
    """
    API endpoint for generating images using Bing with gpt.
    """
    return bing(request.get_json(), 1, model='gpt4o')


@async_run
def run_flask(addr: str = '127.0.0.1', port: int = 58796) -> None:
    """
    Starts the Flask web server.
    """
    try:
        FLASK_APP.run(debug=False, use_reloader=False, host=addr, port=port)
    except Exception as error:
        my_log.log_sbing_api(f'tb:run_flask: {error}')


## main ###########################################################################


if __name__ == '__main__':
    run_flask(addr=cfg.ADDR, port=cfg.PORT)
    my_log.log2(f'run_flask: {cfg.ADDR}:{cfg.PORT} started')
    while True:
        time.sleep(1)