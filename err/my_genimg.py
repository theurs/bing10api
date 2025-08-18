#!/usr/-bin/env python3


import re
import time
import threading
from typing import List

import bing_genimg_v3
import my_log


# Lock to prevent parallel calls to the Bing API
BING_LOCK = threading.Lock()


def bing(prompt: str, model: str = 'dalle') -> List[str]:
    """
    Generates images using Bing, ensuring only one request is processed at a time
    and adding a short delay between requests.

    Assumes the prompt has already been moderated.

    :param prompt: The text prompt for image generation.
    :param model: The model to use ('dalle' or 'gpt4o').
    :return: A list of image URLs or an empty list on failure.
    """
    try:
        with BING_LOCK:
            # Pass the prompt and model to the underlying generation function
            images = bing_genimg_v3.gen_images(prompt, model=model)

            # This check for non-URL strings seems specific; keeping it as is.
            if any(not x.startswith('https://') for x in images):
                return images

        if isinstance(images, list):
            # A short pause to avoid overwhelming the service
            time.sleep(4)
            # Return unique image URLs
            return list(set(images))

    except Exception as error_bing_img:
        my_log.log_bing_img(f'my_genimg:bing: {error_bing_img}')

    return []


def gen_images_bing_only(prompt: str, iterations: int = 1, model: str = 'dalle') -> List[str]:
    """
    High-level function to generate images, with support for multiple iterations.

    :param prompt: The text prompt.
    :param iterations: The number of times to repeat the generation process.
    :param model: The model to use ('dalle' or 'gpt4o').
    :return: A consolidated list of unique image URLs.
    """
    if iterations == 0:
        iterations = 1

    prompt = prompt.strip()
    if not prompt:
        return []

    # This seems to be a custom syntax for some commands, removing it.
    prompt = re.sub(r'^!+', '', prompt).strip()

    all_images: List[str] = []

    for _ in range(iterations):
        generated_images = bing(prompt, model=model)
        if generated_images:
            all_images.extend(generated_images)
        else:
            # If any iteration fails, stop the process for this request.
            break

    return list(set(all_images))


if __name__ == '__main__':
    # Example for direct testing of this module
    test_prompt = 'вкусный торт с медом и орехами'
    print(f"Testing with prompt: '{test_prompt}'")
    result = gen_images_bing_only(test_prompt)
    if result:
        print("Result:")
        for img_url in result:
            print(img_url)
    else:
        print("No images were generated.")