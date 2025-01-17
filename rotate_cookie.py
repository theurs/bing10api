#!/usr/bin/env python3


import os
import traceback

from natsort import natsorted

import my_log


# список найденных куки файлов
FILES = []


def rotate_cookie():
    '''
    Ищет .txt файлы с именем начинающимся на cookie и добавляет их все в список FILES
    из списка берет первый и копирует в cookie.txt
    Если список пустеет то снова ищет все файлы
    '''
    try:
        global FILES

        if not FILES:
            FILES = [f for f in os.listdir('.') if f.startswith('cookie') and f.endswith('.txt') and os.path.isfile(f) and f != 'cookie.txt']
            natsorted(FILES)

        if FILES:
            my_log.log2('rotate_cookie: \n\n' + '\n'.join(FILES))
            source_name = FILES.pop(0)
            with open(source_name, 'r') as source:
                with open('cookie.txt', 'w') as target:
                    target.write(source.read())
                    my_log.log2(f'rotate_cookie: {source_name} -> cookie.txt')
        else:
            my_log.log2('rotate_cookie: no cookie files found')

    except Exception as error:
        traceback_error = traceback.format_exc()
        my_log.log_bing_api(f'tb:rotate_cookie: {error}\n\n{traceback_error}')


if __name__ == '__main__':
    pass

    rotate_cookie()
