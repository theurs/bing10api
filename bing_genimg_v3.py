#!/usr/bin/env python3
# https://github.com/vra/bing_brush


import json
import html
import os
import random
import time
import traceback
from http.cookies import SimpleCookie
from typing import Optional

import regex
import requests
from requests.utils import cookiejar_from_dict

import my_log


class BingBrush:
    def __init__(
        self,
        cookie,
        verbose=False,
        max_wait_time=60,
    ):
        self.max_wait_time = max_wait_time
        self.verbose = verbose

        self.session = self.construct_requests_session(cookie)

        self.prepare_error_messages()

    def parse_cookie(self, cookie_string):
        cookie = SimpleCookie()
        if os.path.exists(cookie_string):
            with open(cookie_string) as f:
                cookie_string = f.read()

        cookie.load(cookie_string)
        cookies_dict = {}
        cookiejar = None
        for key, morsel in cookie.items():
            cookies_dict[key] = morsel.value
            cookiejar = cookiejar_from_dict(
                cookies_dict, cookiejar=None, overwrite=True
            )
        return cookiejar

    def prepare_error_messages(self):
        self.error_message_dict = {
            "error_blocked_prompt": "Your prompt has been blocked by Bing. Try to change any bad words and try again.",
            "error_being_reviewed_prompt": "Your prompt is being reviewed by Bing. Try to change any sensitive words and try again.",
            "error_noresults": "Could not get results.",
            "error_unsupported_lang": "this language is currently not supported by bing.",
            "error_timeout": "Your request has timed out.",
            "error_redirect": "Redirect failed",
            "error_bad_images": "Bad images",
            "error_no_images": "No images",
        }

    def construct_requests_session(self, cookie):
        # Generate random US IP 
        FORWARDED_IP = f"100.{random.randint(43, 63)}.{random.randint(128, 255)}.{random.randint(0, 255)}"
        HEADERS = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "accept-language": "en-US,en;q=0.9",
            "cache-control": "max-age=0",
            "content-type": "application/x-www-form-urlencoded",
            "referrer": "https://www.bing.com/images/create/",
            "origin": "https://www.bing.com",
            # "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36 Edg/110.0.1587.63",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
            "x-forwarded-for": FORWARDED_IP,
        }

        session = requests.Session()
        session.headers = HEADERS
        session.cookies = self.parse_cookie(cookie)
        return session

    def process_error(self, response):
        for error_type, error_msg in self.error_message_dict.items():
            if error_msg in response.text.lower():
                return Exception(error_type)

    def request_result_urls(self, response, url_encoded_prompt):
        if "Location" not in response.headers:
            return None, None
        redirect_url = response.headers["Location"].replace("&nfy=1", "")
        request_id = redirect_url.split("id=")[-1]
        return redirect_url, request_id


    def obtaion_image_url_dalle(self, redirect_url, request_id, url_encoded_prompt):
        self.session.get(f"https://www.bing.com{redirect_url}", timeout=self.max_wait_time)
        polling_url = f"https://www.bing.com/images/create/async/results/{request_id}?q={url_encoded_prompt}"
        # Poll for results
        start_wait = time.time()
        while True:
            if int(time.time() - start_wait) > self.max_wait_time:
                raise Exception(self.error_message_dict["error_timeout"])
            response = self.session.get(polling_url, timeout=self.max_wait_time)
            if response.status_code != 200:
                raise Exception(self.error_message_dict["error_noresults"])
            if not response.text or response.text.find("errorMessage") != -1:
                time.sleep(1)
                continue
            else:
                break

        image_links = regex.findall(r'src="([^"]+)"', response.text)
        normal_image_links = [link.split("?w=")[0] for link in image_links]
        normal_image_links = list(set(normal_image_links))

        return normal_image_links


    def obtaion_image_url(
        self, redirect_url: str, request_id: str, url_encoded_prompt: str
    ) -> list[str]:
        """
        Polls for image generation results and returns the image URLs.
        This method is now unified and works similarly to the DALL-E polling.
        """
        polling_url = (
            f"https://www.bing.com/images/create/async/results/{request_id}"
            f"?q={url_encoded_prompt}"
        )


        self.max_wait_time = 240 # 4 минуты принудительно

        start_wait = time.time()
        while True:
            if int(time.time() - start_wait) > self.max_wait_time:
                raise Exception(self.error_message_dict["error_timeout"])

            response = self.session.get(polling_url, timeout=self.max_wait_time)

            if response.status_code != 200:
                raise Exception(self.error_message_dict["error_noresults"])

            # The 'strm' class indicates that the image is still being rendered progressively.
            # We wait until this class is no longer present in the response.
            if "strm" in response.text or not response.text:
                time.sleep(1)
                continue
            else:
                break

        image_links = regex.findall(r'src="([^"]+)"', response.text)
        normal_image_links = [link.split("?w=")[0] for link in image_links]

        return list(set(normal_image_links))

    def send_request(self, prompt, model="gpt4o", rt_type=4, ar: Optional[str] = None):
        # Маппинг имени модели на ее ID
        model_id = "1" if model == "gpt4o" else "0"

        url_encoded_prompt = requests.utils.quote(prompt)
        payload = f"q={url_encoded_prompt}&qs=ds"

        # Используем model_id вместо имени
        url = f"https://www.bing.com/images/create?q={url_encoded_prompt}&rt={rt_type}&mdl={model_id}&FORM=GENCRE"
        if ar is not None:
            url += f"&ar={ar}"

        response = self.session.post(
            url,
            allow_redirects=False,
            data=payload,
            timeout=self.max_wait_time,
        )
        return response, url_encoded_prompt

    def process(self, prompt, model="dalle", ar: Optional[str] = None):
        """
        Основной метод для генерации изображений.
        model: "dalle" или "gpt4o"
        ar: optional int for aspect ratio. For example, 1 for square.
        """
        try:
            # Сначала пробуем быстрый канал (rt=4)
            response, url_encoded_prompt = self.send_request(prompt, model=model, rt_type=4, ar=ar)

            if response.status_code != 302:
                self.process_error(response)

            my_log.log_bing_api(f'bing_genimg_v3:process: {prompt}')
            redirect_url, request_id = self.request_result_urls(
                response, url_encoded_prompt
            )

            # Если бусты кончились, пробуем медленный (rt=3)
            if redirect_url is None:
                my_log.log_bing_api('bing_genimg_v3:process: ==> Your boosts have run out, using the slow generating pipeline, please wait...')
                response, url_encoded_prompt = self.send_request(prompt, model=model, rt_type=3, ar=ar)
                redirect_url, request_id = self.request_result_urls(
                    response, url_encoded_prompt
                )
                if redirect_url is None:
                    my_log.log_bing_api('bing_genimg_v3:process: ==> Error occurs, please submit an issue at https://github.com/vra/bing_brush, I will fix it as soon as possible.')
                    return []

            if model == 'gpt4o':
                img_urls = self.obtaion_image_url(redirect_url, request_id, url_encoded_prompt)
                if len(img_urls) > 1:
                    img_urls = [x for x in img_urls if x.startswith('http') and 'bing.net/th/id/' in x or 'bing.com/th/id/' in x]
                my_log.log_bing_api(f'bing_genimg_v3:process: {img_urls}')
                return img_urls
            else:
                img_urls = self.obtaion_image_url_dalle(redirect_url, request_id, url_encoded_prompt)
                img_urls = [x for x in img_urls if x.startswith('http') and 'bing.net/th/id/' in x or 'bing.com/th/id/' in x]
                my_log.log_bing_api(f'bing_genimg_v3:process: {img_urls}')
                return img_urls

        except Exception as unknown_error:
            traceback_error = traceback.format_exc()
            my_log.log_bing_api(f'bing_genimg_v3:process: {unknown_error}\n\n{traceback_error}')
            return []


def gen_images(prompt: str, model: str = 'dalle', ar: Optional[str] = '1') -> list:
    '''
    ar = None - 1024x1024
    ar = 1 - 1024x1024
    ar = 2 - 1792x1024
    ar = 3 - 1024x1792
    '''
    brush = BingBrush(cookie='cookie.txt')
    r = brush.process(prompt, model=model, ar=ar)
    cleaned_urls = [url.split('?')[0] if '?' in url else url for url in r]
    return cleaned_urls


if __name__ == "__main__":
    # images = gen_images('кепка, на кепке написано кирилицей - Удача', model='gpt4o', ar='3')
    images = gen_images('кепка, на кепке написано кирилицей - Удача', model='dalle', ar='1')

    if images:
        for image in images:
            print(image)
