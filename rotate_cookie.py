#!/usr/bin/env python3

import os
import traceback
from typing import List

from natsort import natsorted

import my_log


# The common pool of source cookie files, loaded once
SOURCE_FILES: List[str] = []
# Index to keep track of the next cookie to use from the pool
NEXT_COOKIE_INDEX: int = 0


def rotate_cookie(model: str) -> None:
    """
    Rotates the cookie for a specific model using a shared, circular pool of cookie files.

    It scans for source files (e.g., 'cookie1.txt', 'cookie_user.txt') on the first run.
    On each call, it assigns the next available cookie from this pool to the requesting model,
    copying its content to 'cookie_{model}.txt'. The pool is traversed in a circle.

    :param model: The name of the model (e.g., 'dalle', 'gpt4o') requesting a new cookie.
    """
    global SOURCE_FILES, NEXT_COOKIE_INDEX

    try:
        # Initialize the source file pool if it's empty (one-time scan)
        if not SOURCE_FILES:
            # Find all files starting with 'cookie' and ending with '.txt'
            all_cookie_files = [
                f for f in os.listdir('.') 
                if f.startswith('cookie') and f.endswith('.txt') and os.path.isfile(f)
            ]
            
            # Filter out the destination files managed by this script
            # This set can be expanded if more models are added in bing10api.py
            managed_files = {'cookie_dalle.txt', 'cookie_gpt4o.txt'}
            
            # The source pool is everything except the managed files
            user_provided_cookies = [f for f in all_cookie_files if f not in managed_files]
            
            SOURCE_FILES = natsorted(user_provided_cookies)
            NEXT_COOKIE_INDEX = 0
            if SOURCE_FILES:
                my_log.log2(f'rotate_cookie: Found source cookie pool:\n' + '\n'.join(SOURCE_FILES))

        # If we have source files, proceed with rotation
        if SOURCE_FILES:
            # Get the next cookie file from the pool in a circular manner
            source_name = SOURCE_FILES[NEXT_COOKIE_INDEX]
            dest_name = f'cookie_{model}.txt'

            my_log.log2(f'rotate_cookie (for model "{model}"): Assigning next cookie from pool.')
            
            # Copy content from source to destination
            with open(source_name, 'r', encoding='utf-8') as source:
                with open(dest_name, 'w', encoding='utf-8') as target:
                    target.write(source.read())
                    my_log.log2(f'rotate_cookie: Copied "{source_name}" -> "{dest_name}"')

            # Move to the next index for the next rotation, wrapping around if necessary
            NEXT_COOKIE_INDEX = (NEXT_COOKIE_INDEX + 1) % len(SOURCE_FILES)
        else:
            my_log.log2(f'rotate_cookie (for model "{model}"): No source cookie files found. Please create files like "cookie1.txt", "cookie_abc.txt", etc.')

    except Exception as error:
        traceback_error = traceback.format_exc()
        my_log.log_bing_api(f'tb:rotate_cookie ({model}): {error}\n\n{traceback_error}')


if __name__ == '__main__':
    # --- Example usage for testing ---
    # To test, create files like: cookie1.txt, cookie2.txt, cookie10.txt
    
    print("1. Assigning cookie for DALLE...")
    rotate_cookie(model='dalle')  # Should pick cookie1.txt
    
    print("\n2. Assigning cookie for GPT-4o...")
    rotate_cookie(model='gpt4o') # Should pick cookie2.txt
    
    print("\n3. Re-assigning cookie for DALLE...")
    rotate_cookie(model='dalle') # Should pick cookie10.txt
    
    print("\n4. Assigning another cookie for GPT-4o...")
    rotate_cookie(model='gpt4o') # Should circle back and pick cookie1.txt again