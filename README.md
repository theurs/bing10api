# Bing Image Generator API for https://github.com/theurs/tb1

Этот проект предоставляет API для генерации изображений с использованием Bing Image Creator.

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
    -   `MAX_LOG_FILE_SIZE`: Максимальный размер файла журнала в байтах (по умолчанию 20MB).
    -   `ADDR`: IP-адрес, на котором будет запущен Flask-сервер (по умолчанию `172.28.1.6`).
    -   `PORT`: Порт, на котором будет запущен Flask-сервер (по умолчанию `58796`).

    Измените эти переменные в соответствии с вашими потребностями.

2.  **Файл `cookie.txt`:**
    -   Этот файл должен содержать cookie для аутентификации в Bing. Получить cookie можно, например, из инструментов разработчика вашего браузера. Расширение для браузера - cookie editor(export header string)
    -   Поместите ваш cookie в файл `cookie.txt`

3.  **Настройка службы Systemd (опционально):**
    - Если вы хотите запускать сервер как службу systemd, создайте файл службы systemd:
        ```bash
        sudo nano /etc/systemd/system/bing_image_generator.service
        ```
    - Вставьте следующий текст, измените пути на ваши.
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

    - Замените:
        - `<your_user>` на вашего пользователя.
        - `<your_group>` на вашу группу.
        - `<path_to_your_project>` на абсолютный путь к вашему проекту.
        - `<path_to_your_venv>` на абсолютный путь к вашему виртуальному окружению.

    - Сохраните файл и включите службу:
        ```bash
        sudo systemctl daemon-reload
        sudo systemctl enable bing_image_generator.service
        sudo systemctl start bing_image_generator.service
        sudo systemctl status bing_image_generator.service
        ```

## Использование API

### API Endpoint
*   `POST /bing`: Генерирует изображения на основе предоставленного запроса. Возвращает JSON с ключом `urls` (массив URL-адресов изображений).
*   `POST /bing2`: Повторяет запрос к Bing 2 раза.
*   `POST /bing10`: Повторяет запрос к Bing 10 раз.
*   `POST /bing20`: Повторяет запрос к Bing 20 раз.

Запрос должен быть предварительно отмодерирован. 10х и 20х принудительно останавливаются если запрос был неудачным, бинг не любит когда его заставляют рисовать то что ему не нравится.

### Запрос

Отправьте POST-запрос к одному из endpoints с JSON телом:

```json
{
  "prompt": "a beautiful cat in space"
}
```

### Ответ
В случае успеха, вернется JSON:

```json
{
    "urls": [
        "https://....bing.net/th/id/....jpg",
        "https://....bing.net/th/id/....jpg",
        "https://....bing.net/th/id/....jpg",
        "https://....bing.net/th/id/....jpg"
    ]
}
```
В случае ошибки, вернется JSON с ошибкой:
```json
{
    "error": "No images generated"
}
```

### Пример запроса с `curl`:

```bash
curl -X POST \
    -H "Content-Type: application/json" \
    -d '{
        "prompt": "a beautiful cat in space"
    }' \
    http://<your_address>:<your_port>/bing10
```

Замените `<your_address>` и `<your_port>` на фактические значения из файла `cfg.py`.

## Описание файлов

*   `.gitignore`: Игнорирует файлы, которые не нужно отслеживать в Git.
*   `bing_genimg_v3.py`:  Содержит основной класс `BingBrush` для взаимодействия с API Bing. Отвечает за генерацию изображений через Bing Image Creator.
*   `bing10api.py`: Flask API для доступа к генерации изображений Bing.
*   `cfg.py`: Файл конфигурации для проекта.
*   `my_genimg.py`: Содержит функции для управления процессом генерации изображений (логика повторения запросов, ограничение на число одновременных запросов).
*   `my_log.py`: Функции для логирования событий.
*   `requirements.txt`: Список зависимостей Python.
*   `utils.py`: Вспомогательные функции.

## Примечания

*   При первом запуске, сервер может какое-то время не отвечать. Это связано с загрузкой необходимых данных.
*   Если возникают проблемы при генерации изображений, убедитесь, что cookie в файле `cookie.txt` валидный и не истек.
*   Авторизации нет, адрес сервера должен быть или на локалхосте или в защищенной сети (локальная или впн)
