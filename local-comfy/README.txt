Локальная фабрика ассетов: Docker + ComfyUI

Сервис: http://127.0.0.1:8188
ComfyUI v0.38.0, официальный commit 6b747c0428c343e1417219641db93a4fb7cb69ae.
База: официальный PyTorch 2.13 / CUDA 13.0, закреплённый digest образа.
Зависимости ComfyUI установлены в отдельное окружение внутри контейнера;
ensurepip не используется. CUDA-стек базового образа сохранён.
Python/Torch на компьютере и другие Docker-проекты не меняются.
Из нашего образа удалён только ненужный инструмент разработки spin: его старое
ограничение Click конфликтовало с современным Hugging Face. Проверка pip check обязательна.

Запуск: ./local-comfy/manage.ps1 start
Состояние: ./local-comfy/manage.ps1 status
Проверка GPU: ./local-comfy/manage.ps1 gpu-check
Остановка только этого сервиса: ./local-comfy/manage.ps1 stop
restart=no: сервис не запускается сам при каждом включении Docker.

data/models: общая библиотека весов, для контейнера только чтение.
data/input: референсы, маски и выбранные исходные изображения.
data/output: результаты ComfyUI. Не считаются одобренными автоматически.
data/user: настройки, база и UI-workflows.
data/cache: служебные кеши; не содержит учётных данных Kaggle.
Папки сохранены на компьютере отдельно от образа и контейнера.

Доступ только через localhost. Платные API-узлы и custom nodes отключены.
Менеджер расширений пока не устанавливается: добавляем только нужные проверенные узлы.
Для TTS с несовместимыми зависимостями позже нужен отдельный контейнер, не случайная
установка пакетов в image-сервис. Исходники/версии каждого дополнения закрепляем.

FLUX.2 Klein 4B Distilled/Base FP8, Qwen3 4B FP4 и FLUX2 VAE загружены;
ревизии и SHA256 закреплены в outputs/local-production-v6/research/model-lock.json.
Distilled уже прошёл реальную генерацию 1536×864 на локальной GPU.
Наличие сервиса/GPU не подтверждает качество отдельного кадра: нужен отбор.
Профиль для 8 GiB VRAM/16 GiB RAM: dynamic VRAM, fast-disk, отключены pinned memory
и кеш результатов. Это уменьшает давление на память, но повторные задания могут идти медленнее.
В Docker сейчас всего около 7.6 GiB RAM, она общая с другими запущенными сервисами.
Увеличение памяти/перезапуск Docker не выполняются автоматически: это затронет другие проекты.

API без браузера:
python -X utf8 local-comfy/comfy_client.py status
python -X utf8 local-comfy/comfy_client.py run --workflow local-comfy/workflows/transport-smoke-api.json
Повторная полная проверка сервиса: python -X utf8 local-comfy/verify_setup.py
Отчёты проверки: local-comfy/reports; сводка: local-comfy/VALIDATION.json.
Транспортный тест LoadImage -> SaveImage только копирует кадр, не делает AI-генерацию.

Связь с видео-пайплайном:
ComfyUI -> локальный отбор и проверка кадров -> video-inputs.zip -> Kaggle silent I2V
-> results.zip -> локальная проверка -> монтаж Remotion/HyperFrames.
Голос, музыка, титры и финальный монтаж остаются локальными.
