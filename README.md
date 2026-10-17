# The Last Firework — local film pipeline

Локальные ассеты ComfyUI → при необходимости Kaggle I2V → звук и монтаж Remotion.
Точка продолжения и ограничения: [docs/HANDOFF.md](docs/HANDOFF.md).

## Перенос на другую машину

Git содержит код, промпты в исходниках, монтаж и notebooks. Кадры, звук,
референсы и отчёты находятся в отдельном `film-assets.zip`; веса в Git не входят.

```powershell
git clone https://github.com/ilyaskhan1909/film-pipeline.git film-pipeline
cd film-pipeline
# Без GitHub: git clone /путь/film-pipeline.bundle film-pipeline
python tools/project_transfer.py restore /путь/film-assets.zip
python tools/project_transfer.py verify /путь/film-assets.zip
python tools/bootstrap.py doctor
python tools/bootstrap.py install
python tools/bootstrap.py preview
```

Нужны Python 3.11/3.12, Node.js 22/24 с npm, Git. Для GPU-генерации:
NVIDIA с подходящим драйвером, Docker с доступом к GPU. На Windows — Docker Desktop/WSL2.
Клонируйте в обычную папку пользователя, не в OneDrive и не поверх прежних результатов.

Превью ink-пилота: `http://127.0.0.1:3018/InkPilot`.
Полный прежний монтаж: сначала `python tools/bootstrap.py install --project full`,
затем `python tools/bootstrap.py preview --project full --port 3019`.
Превью запускается без экспорта и без системного браузера, только на localhost.

```powershell
# Закреплённые веса: скачать заново или восстановить отдельный пакет models.
python tools/bootstrap.py models
python tools/bootstrap.py comfy-start
python local-comfy/comfy_client.py status
```

Базовый Docker-профиль сохранён, но новая GPU, память и скорость требуют проверки.
TTS/ASR-окружения не устанавливаются автоматически: сначала выбираем голос и проверяем пробы.

Создание пакетов и публикация: [docs/TRANSFER.md](docs/TRANSFER.md).
