#!/usr/bin/env python3


import re
import time
import threading


import bing_genimg_v3
import my_log


# попробовать заблокировать параллельные вызовы бинга
BING_LOCK = threading.Lock()


def bing(prompt: str, model: str = 'dalle') -> list:
    """
    Рисует бингом, не больше 1 потока и 20 секунд пауза между запросами
    Ограничение на размер промпта 950, хз почему

    Предполагается что промпт уже прошел модерацию
    """

    # prompt = prompt[:950] # нельзя больше 950?

    try:
        with BING_LOCK:
            images = bing_genimg_v3.gen_images(prompt, model=model)

            # если нет картинок (есть только ошибки) то сразу вернуть отказ
            if any([x for x in images if not x.startswith('https://')]):
                return images

        if type(images) == list:
            # пауза между запросами
            time.sleep(4)
            return list(set(images))

    except Exception as error_bing_img:
        my_log.log_bing_img(f'my_genimg:bing: {error_bing_img}')

    return []


def gen_images_bing_only(prompt: str, iterations: int = 1, model: str = 'dalle') -> list:
    if iterations == 0:
        iterations = 1

    if prompt.strip() == '':
        return []

    prompt = re.sub(r'^!+', '', prompt).strip()

    images = []

    for _ in range(iterations):
        r = bing(prompt, model=model)
        if r:
            images += r
        else:
            break

    return images


if __name__ == '__main__':
    print(gen_images_bing_only('вкусный торт с медом и орехами'))
