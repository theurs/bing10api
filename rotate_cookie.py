#!/usr/bin/env python3

import os
import traceback
from typing import Dict, List

from natsort import natsorted

import my_log


# Dictionary to hold lists of cookie files for each model
MODEL_COOKIE_FILES: Dict[str, List[str]] = {}


def rotate_cookie(model: str) -> None:
    """
    Finds and rotates cookie files for a specific model.

    It searches for .txt files named like 'cookie_{model}_*.txt',
    takes the first one from a naturally sorted list, and copies its
    content to 'cookie_{model}.txt'.

    If the list for a model becomes empty, it rescans the directory.

    :param model: The name of the model (e.g., 'dalle', 'gpt4o') to rotate cookies for.
    """
    try:
        global MODEL_COOKIE_FILES

        # Check if the list for the current model is empty or not yet initialized
        if not MODEL_COOKIE_FILES.get(model):
            dest_file_name = f'cookie_{model}.txt'
            prefix = f'cookie_{model}_'
            
            # Scan for cookie files specific to the model
            found_files = [
                f for f in os.listdir('.') 
                if f.startswith(prefix) and f.endswith('.txt') and os.path.isfile(f)
            ]
            
            # Store the sorted list in our global dictionary
            MODEL_COOKIE_FILES[model] = natsorted(found_files)

        # Proceed if we have files for the current model
        if MODEL_COOKIE_FILES.get(model):
            # Log the current list of available cookies for this model
            my_log.log2(f'rotate_cookie ({model}): available files:\n' + '\n'.join(MODEL_COOKIE_FILES[model]))
            
            # Take the first file from the list
            source_name = MODEL_COOKIE_FILES[model].pop(0)
            dest_name = f'cookie_{model}.txt'
            
            # Copy content from source to destination
            with open(source_name, 'r', encoding='utf-8') as source:
                with open(dest_name, 'w', encoding='utf-8') as target:
                    target.write(source.read())
                    my_log.log2(f'rotate_cookie ({model}): {source_name} -> {dest_name}')
        else:
            my_log.log2(f'rotate_cookie ({model}): no cookie files found')

    except Exception as error:
        traceback_error = traceback.format_exc()
        my_log.log_bing_api(f'tb:rotate_cookie ({model}): {error}\n\n{traceback_error}')


if __name__ == '__main__':
    # Example usage for testing
    # create dummy files like cookie_dalle_1.txt, cookie_dalle_2.txt, cookie_gpt4o_a.txt
    print("Testing DALLE cookie rotation...")
    rotate_cookie(model='dalle')
    print("\nTesting GPT-4o cookie rotation...")
    rotate_cookie(model='gpt4o')