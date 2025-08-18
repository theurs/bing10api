# Bing Image Generator API for https://github.com/theurs/tb1

Этот проект предоставляет API для генерации изображений с использованием Bing Image Creator с поддержкой нескольких моделей (`dalle`, `gpt4o`) и автоматической ротацией cookie-файлов из общего пула.

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
    -   `MAX_LOG_FILE_SIZE`: Максимальный размер файла журнала в байтах.
    -   `ADDR`: IP-адрес для Flask-сервера.
    -   `PORT`: Порт для Flask-сервера.
    -   `CMD_ON_STOP`: (Опционально) Команда для уведомлений, когда модель временно отключается из-за ошибок.

    Пример:
    ```python
    MAX_LOG_FILE_SIZE = 20*1024*1024
    ADDR = '127.0.0.1'
    PORT = '58796'
    #CMD_ON_STOP='sendmail admin@example.com -s "Bing cookies died"'
    ```

2.  **Создание общего пула Cookie:**
    -   Система использует **общий пул** cookie-файлов для всех моделей. Каждая модель (`dalle`, `gpt4o`) берет из этого пула следующий доступный cookie по очереди, независимо от других моделей.
    -   **Создайте один или несколько файлов с cookie** в корневой директории проекта. Называйте их просто, например: `cookie1.txt`, `cookie2.txt`, `cookie_extra.txt`, и т.д.
    -   **Не создавайте файлы `cookie_dalle.txt` или `cookie_gpt4o.txt` вручную!** Скрипт создаст и будет управлять ими автоматически.
    -   Скрипт найдет все ваши файлы `cookie*.txt` (кроме созданных им самим), отсортирует их и будет использовать по кругу.
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

*   `POST /reload_dalle`: Принудительно берет следующий cookie-файл из общего пула для модели **dalle**.
*   `POST /reload_gpt4o`: Принудительно берет следующий cookie-файл из общего пула для модели **gpt4o**.
*   `POST /reload_cookies`: Принудительно перезагружает cookie для **всех** моделей (каждая возьмет следующий по очереди cookie из пула).

### Запрос

Отправьте POST-запрос к одному из эндпоинтов генерации с JSON телом:

```json
{
  "prompt": "a beautiful cat in space"
}
```

### Примеры запросов с `curl`

**Генерация (dalle):**
```bash
curl -X POST -H "Content-Type: application/json" -d '{"prompt": "a beautiful cat in space"}' http://127.0.0.1:58796/bing
```

**Генерация (gpt4o):**
```bash
curl -X POST -H "Content-Type: application/json" -d '{"prompt": "a dog on a skateboard"}' http://127.0.0.1:58796/bing_gpt
```

**Принудительная перезагрузка cookie для dalle:**
```bash
curl -X POST http://127.0.0.1:58796/reload_dalle
```

## Описание файлов

*   `bing10api.py`: Flask API. Управляет эндпоинтами и состоянием моделей (счетчики ошибок, блокировки).
*   `bing_genimg_v3.py`: Основной класс `BingBrush` для взаимодействия с Bing. Использует для работы файлы `cookie_dalle.txt` или `cookie_gpt4o.txt`.
*   `cfg.py`: Файл конфигурации.
*   `my_genimg.py`: Посредник между API и генератором, управляет итерациями и блокировкой параллельных запросов.
*   `my_log.py`: Функции для логирования.
*   `requirements.txt`: Список зависимостей Python.
*   `rotate_cookie.py`: Отвечает за логику ротации cookie. Находит пользовательские куки (например, `cookie1.txt`), и по запросу копирует следующий из пула в рабочий файл модели (`cookie_dalle.txt` и т.д.).
*   `utils.py`: Вспомогательные функции.

## Примечания

*   Авторизации нет. Предполагается, что API будет работать в защищенной сети (локальной, VPN) или на localhost.
*   Если возникают постоянные ошибки генерации, убедитесь, что ваши cookie-файлы в корне проекта валидны и не истекли.
