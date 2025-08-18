# Bing Image Generator API for https://github.com/theurs/tb1

Этот проект предоставляет API для генерации изображений с использованием Bing Image Creator с поддержкой нескольких моделей (`dalle`, `gpt4o`) и автоматической ротацией cookie-файлов.

## Установка

1.  **Клонируйте репозиторий:**

    ```bash
    git clone https://github.com/theurs/bing10api.git
    cd bing10api
    ```

2.  **Создайте и активируйте виртуальное окружение (venv):**

    ```bash
    python3 -m venv venv
    source venv/bin/activate  # Linux/macOS
    # venv\Scripts\activate  # Windows
    ```

3.  **Установите зависимости:**

    ```bash
    pip install -r requirements.txt
    ```

## Настройка

1.  **Файл `cfg.py`:**
    -   `MAX_LOG_FILE_SIZE`: Целое число, максимальный размер файла журнала в байтах (по умолчанию 20MB).
    -   `ADDR`: Строка, IP-адрес, на котором будет запущен Flask-сервер.
    -   `PORT`: Строка, порт, на котором будет запущен Flask-сервер.
    -   `CMD_ON_STOP`: (Опционально) Команда, которая будет выполняться, когда модель временно отключается из-за большого количества ошибок. Полезна для отправки уведомлений.

    Пример:
    ```python
    MAX_LOG_FILE_SIZE = 20*1024*1024
    ADDR = '127.0.0.1'
    PORT = '58796'
    #CMD_ON_STOP='sendmail admin@example.com -s "Bing cookies died"'
    ```

2.  **Файлы Cookie:**
    -   Система использует отдельные "пулы" cookie для каждой модели (`dalle`, `gpt4o`). Это позволяет продолжать работу одной модели, если куки для другой исчерпали себя.
    -   **Создайте файлы с куками** в корне проекта, следуя шаблону: `cookie_{model}_{identifier}.txt`.
        -   `{model}`: `dalle` или `gpt4o`.
        -   `{identifier}`: Любой уникальный идентификатор (например, `1`, `2`, `alpha`, `user1`).
    -   **Примеры имен файлов:**
        -   `cookie_dalle_1.txt`
        -   `cookie_dalle_2.txt`
        -   `cookie_gpt4o_main.txt`
        -   `cookie_gpt4o_backup.txt`
    -   Скрипт будет автоматически брать файлы из этих пулов по очереди (в отсортированном порядке), копировать их содержимое в рабочий файл (`cookie_dalle.txt` или `cookie_gpt4o.txt`) и использовать его. Если рабочий cookie перестает работать, он будет заменен следующим из списка.
    -   Получить cookie можно, например, из инструментов разработчика вашего браузера (рекомендуется расширение Cookie Editor, функция "export as header string").

3.  **Настройка службы Systemd (опционально):**
    - Если вы хотите запускать сервер как службу systemd, создайте файл:
        ```bash
        sudo nano /etc/systemd/system/bing_image_generator.service
        ```
    - Вставьте следующий текст, изменив пути на ваши.
       ```
        [Unit]
        Description=Bing Image Generator Service
        After=network.target

        [Service]
        User=<your_user>
        Group=<your_group>
        WorkingDirectory=<path_to_your_project>
        ExecStart=<path_to_your_venv>/bin/python <path_to_your_project>/bing10api.py
        Restart=on-failure
        
        [Install]
        WantedBy=multi-user.target
       ```
    - Замените placeholders (`<...>`) на ваши реальные пути и имена пользователя/группы.

    - Включите и запустите службу:
        ```bash
        sudo systemctl daemon-reload
        sudo systemctl enable bing_image_generator.service
        sudo systemctl start bing_image_generator.service
        sudo systemctl status bing_image_generator.service
        ```

## Использование API

### Эндпоинты для генерации изображений

*   `POST /bing`: Генерирует изображения с помощью модели **dalle**.
*   `POST /bing2`: Повторяет запрос 2 раза (модель **dalle**).
*   `POST /bing10`: Повторяет запрос 10 раз (модель **dalle**).
*   `POST /bing20`: Повторяет запрос 20 раз (модель **dalle**).
*   `POST /bing_gpt`: Генерирует изображение с помощью модели **gpt4o**.

### Эндпоинты для управления Cookie

*   `POST /reload_dalle`: Принудительно берет следующий cookie-файл для модели **dalle**.
*   `POST /reload_gpt4o`: Принудительно берет следующий cookie-файл для модели **gpt4o**.
*   `POST /reload_cookies`: Принудительно перезагружает cookie для **всех** моделей.

### Запрос

Отправьте POST-запрос к одному из эндпоинтов генерации с JSON телом:

```json
{
  "prompt": "a beautiful cat in space"
}
```

### Ответ

В случае успеха, вернется JSON с массивом URL-адресов:
```json
{
    "urls": [
        "https://....bing.net/th/id/....jpg",
        "https://....bing.net/th/id/....jpg"
    ]
}
```
В случае ошибки, вернется JSON с описанием проблемы:
```json
{
    "error": "No images generated"
}
```

### Примеры запросов с `curl`

**Генерация (dalle):**
```bash
curl -X POST \
    -H "Content-Type: application/json" \
    -d '{"prompt": "a beautiful cat in space"}' \
    http://127.0.0.1:58796/bing
```

**Генерация (gpt4o):**
```bash
curl -X POST \
    -H "Content-Type: application/json" \
    -d '{"prompt": "a dog on a skateboard"}' \
    http://127.0.0.1:58796/bing_gpt
```

**Принудительная перезагрузка cookie для dalle:**
```bash
curl -X POST http://127.0.0.1:58796/reload_dalle
```

## Описание файлов

*   `.gitignore`: Игнорирует файлы, которые не нужно отслеживать в Git.
*   `bing10api.py`: Flask API. Управляет эндпоинтами, обрабатывает запросы и следит за состоянием моделей (счетчики ошибок, временная блокировка).
*   `bing_genimg_v3.py`: Содержит основной класс `BingBrush` для взаимодействия с Bing. Адаптирован для использования cookie-файлов под конкретную модель (`cookie_dalle.txt`, `cookie_gpt4o.txt`).
*   `cfg.py`: Файл конфигурации.
*   `my_genimg.py`: Посредник между API и генератором. Управляет логикой повторений и блокировкой для предотвращения параллельных запросов к Bing.
*   `my_log.py`: Функции для логирования событий.
*   `requirements.txt`: Список зависимостей Python.
*   `rotate_cookie.py`: Отвечает за логику ротации cookie. Ищет файлы `cookie_{model}_*.txt` и копирует их в рабочие `cookie_{model}.txt`.
*   `utils.py`: Вспомогательные функции.

## Примечания

*   Авторизации нет. Предполагается, что API будет работать в защищенной сети (локальной, VPN) или на localhost.
*   Если возникают постоянные ошибки генерации, убедитесь, что ваши cookie-файлы в корне проекта валидны и не истекли.

