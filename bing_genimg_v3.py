#!/usr/bin/env python3
# https://github.com/vra/bing_brush


import json
import html
import os
import random
import time
import traceback
from http.cookies import SimpleCookie
from typing import List, Tuple, Optional, Dict

import regex
import requests
from requests.utils import cookiejar_from_dict
from requests.cookies import RequestsCookieJar

import my_log


class BingBrush:
    def __init__(
        self,
        cookie: str,
        verbose: bool = False,
        max_wait_time: int = 60,
    ):
        self.max_wait_time = max_wait_time
        self.verbose = verbose
        self.session = self.construct_requests_session(cookie)
        self.error_message_dict = self.prepare_error_messages()

    def parse_cookie(self, cookie_string: str) -> RequestsCookieJar:
        # Tries to read from a file if the cookie_string is a valid path
        if os.path.exists(cookie_string):
            try:
                with open(cookie_string, 'r', encoding='utf-8') as f:
                    cookie_string = f.read()
            except Exception as e:
                my_log.log_bing_api(f"bing_genimg_v3:parse_cookie: Failed to read cookie file {cookie_string}: {e}")
                return RequestsCookieJar()  # Return empty jar on failure

        cookie = SimpleCookie()
        cookie.load(cookie_string)
        cookies_dict = {key: morsel.value for key, morsel in cookie.items()}
        return cookiejar_from_dict(cookies_dict)

    def prepare_error_messages(self) -> Dict[str, str]:
        return {
            "error_blocked_prompt": "Your prompt has been blocked by Bing. Try to change any bad words and try again.",
            "error_being_reviewed_prompt": "Your prompt is being reviewed by Bing. Try to change any sensitive words and try again.",
            "error_noresults": "Could not get results.",
            "error_unsupported_lang": "this language is currently not supported by bing.",
            "error_timeout": "Your request has timed out.",
            "error_redirect": "Redirect failed",
            "error_bad_images": "Bad images",
            "error_no_images": "No images",
        }

    def construct_requests_session(self, cookie: str) -> requests.Session:
        # Generate random US IP to simulate a different client
        forwarded_ip = f"100.{random.randint(43, 63)}.{random.randint(128, 255)}.{random.randint(0, 255)}"
        headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "accept-language": "en-US,en;q=0.9",
            "cache-control": "max-age=0",
            "content-type": "application/x-www-form-urlencoded",
            "referrer": "https://www.bing.com/images/create/",
            "origin": "https://www.bing.com",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
            "x-forwarded-for": forwarded_ip,
        }

        session = requests.Session()
        session.headers = headers
        session.cookies = self.parse_cookie(cookie)
        return session

    def process_error(self, response: requests.Response) -> Exception:
        for error_type, error_msg in self.error_message_dict.items():
            if error_msg in response.text.lower():
                return Exception(error_type)
        return Exception("Unknown error occurred during request.")

    def request_result_urls(self, response: requests.Response) -> Tuple[Optional[str], Optional[str]]:
        if "Location" not in response.headers:
            return None, None
        redirect_url = response.headers["Location"].replace("&nfy=1", "")
        try:
            request_id = redirect_url.split("id=")[-1]
        except IndexError:
            return None, None
        return redirect_url, request_id

    def obtain_image_urls_dalle(self, redirect_url: str, request_id: str, url_encoded_prompt: str) -> List[str]:
        self.session.get(f"https://www.bing.com{redirect_url}", timeout=self.max_wait_time)
        polling_url = f"https://www.bing.com/images/create/async/results/{request_id}?q={url_encoded_prompt}"

        start_wait = time.time()
        while True:
            if int(time.time() - start_wait) > self.max_wait_time:
                raise Exception(self.error_message_dict["error_timeout"])

            response = self.session.get(polling_url, timeout=self.max_wait_time)
            if response.status_code != 200:
                raise Exception(self.error_message_dict["error_noresults"])

            if not response.text or "errorMessage" in response.text:
                time.sleep(1)
                continue
            else:
                break

        image_links = regex.findall(r'src="([^"]+)"', response.text)
        # Normalize URLs by removing query parameters
        normal_image_links = [link.split("?w=")[0] for link in image_links]

        # Filter for valid image URLs and remove duplicates
        valid_urls = [url for url in set(normal_image_links) if url.startswith("https://th.bing.com/th/id/")]
        return valid_urls

    def obtain_image_urls_gpt(self, redirect_url: str) -> List[str]:
        timeout = self.max_wait_time + 60
        initial_page_response = self.session.get(f"https://www.bing.com{redirect_url}", timeout=timeout)
        if initial_page_response.status_code != 200:
            raise Exception("Failed to load result page.")

        polling_url_match = regex.search(r'data-c="([^"]+)"', initial_page_response.text)
        if not polling_url_match:
            raise Exception("Could not find polling URL (data-c attribute).")

        polling_url = html.unescape(polling_url_match.group(1))
        full_polling_url = f"https://www.bing.com{polling_url}"

        start_wait = time.time()
        latest_thumbnail_id = None

        while time.time() - start_wait < timeout:
            response = self.session.get(full_polling_url, timeout=timeout)
            if response.status_code != 200:
                raise Exception(self.error_message_dict["error_noresults"])

            if "Unsafe image content detected" in response.text:
                raise Exception("Unsafe image content detected")

            # Check if generation is complete by looking for non-empty rewrite URL
            if 'data-rewriteurl=""' not in response.text:
                m_json_blobs = regex.findall(r'm="([^"]+)"', response.text)
                if m_json_blobs:
                    try:
                        # Process the last JSON blob, as it's the most recent update
                        unescaped_blob = html.unescape(m_json_blobs[-1])
                        m_data = json.loads(unescaped_blob)
                        if "ThumbnailInfo" in m_data and m_data["ThumbnailInfo"]:
                            thumbnail_id = m_data["ThumbnailInfo"][0].get("ThumbnailId")
                            if thumbnail_id:
                                latest_thumbnail_id = thumbnail_id
                                break  # Found a complete image, exit the loop
                    except (json.JSONDecodeError, KeyError, IndexError):
                        pass  # Ignore parsing errors and try again

            time.sleep(2)

        if latest_thumbnail_id:
            return [f"https://th.bing.com/th/id/{latest_thumbnail_id}"]

        my_log.log_bing_api("bing_genimg_v3:obtain_image_urls_gpt: No completed image found within timeout.")
        return []

    def send_request(self, prompt: str, model: str, rt_type: int) -> Tuple[requests.Response, str]:
        model_id = "1" if model == "gpt4o" else "0"
        url_encoded_prompt = requests.utils.quote(prompt)
        payload = f"q={url_encoded_prompt}&qs=ds"
        url = f"https://www.bing.com/images/create?q={url_encoded_prompt}&rt={rt_type}&mdl={model_id}&FORM=GENCRE"

        response = self.session.post(
            url,
            allow_redirects=False,
            data=payload,
            timeout=self.max_wait_time,
        )
        return response, url_encoded_prompt

    def process(self, prompt: str, model: str = "dalle") -> List[str]:
        """
        Main method for generating images.
        model: "dalle" or "gpt4o"
        """
        try:
            # Try the fast channel first (rt=4)
            response, url_encoded_prompt = self.send_request(prompt, model=model, rt_type=4)

            if response.status_code != 302:
                raise self.process_error(response)

            my_log.log_bing_api(f'bing_genimg_v3:process: Start "{prompt}" with model "{model}"')
            redirect_url, request_id = self.request_result_urls(response)

            # If boosts have run out (no redirect), try the slow channel (rt=3)
            if redirect_url is None:
                my_log.log_bing_api('bing_genimg_v3:process: Boosts may have run out, trying slow pipeline...')
                response, url_encoded_prompt = self.send_request(prompt, model=model, rt_type=3)
                if response.status_code != 302:
                    raise self.process_error(response)

                redirect_url, request_id = self.request_result_urls(response)
                if redirect_url is None:
                    my_log.log_bing_api('bing_genimg_v3:process: Slow pipeline also failed. No redirect.')
                    return []

            # Ensure we have the necessary identifiers
            if not redirect_url or not request_id:
                 my_log.log_bing_api('bing_genimg_v3:process: Failed to get redirect URL or request ID.')
                 return []

            if model == 'gpt4o':
                img_urls = self.obtain_image_urls_gpt(redirect_url)
            else:  # dalle
                img_urls = self.obtain_image_urls_dalle(redirect_url, request_id, url_encoded_prompt)

            my_log.log_bing_api(f'bing_genimg_v3:process: Success. Got {len(img_urls)} URLs.')
            return img_urls

        except Exception as unknown_error:
            traceback_error = traceback.format_exc()
            my_log.log_bing_api(f'bing_genimg_v3:process: ERROR: {unknown_error}\n\n{traceback_error}')
            return []


def gen_images(prompt: str, model: str = 'dalle') -> List[str]:
    """
    Generates images using Bing, selecting the cookie file based on the model.
    This function is the entry point from my_genimg.py.
    """
    # Dynamically determine the cookie file based on the selected model
    cookie_filename = f'cookie_{model}.txt'

    # Check if the required cookie file exists before proceeding
    if not os.path.exists(cookie_filename):
        my_log.log_bing_api(f'bing_genimg_v3:gen_images: Cookie file "{cookie_filename}" not found for model "{model}". The API should create it via rotate_cookie first.')
        return []

    brush = BingBrush(cookie=cookie_filename)
    return brush.process(prompt, model=model)


if __name__ == "__main__":
    # Example for direct testing of this script
    # Make sure you have a 'cookie_dalle.txt' or 'cookie_gpt4o.txt' file in the same directory.
    # These files are created by the rotate_cookie.py script.

    test_prompt = 'A cute cat wearing a small wizard hat'
    test_model = 'dalle'  # or 'gpt4o'

    print(f"Generating images for prompt: '{test_prompt}' using model: '{test_model}'...")
    result_urls = gen_images(test_prompt, model=test_model)

    if result_urls:
        print("Generated Image URLs:")
        for url in result_urls:
            print(url)
    else:
        print("Failed to generate images. Check logs/debug_bing_api.log for details.")