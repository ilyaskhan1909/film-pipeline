# Код и данные

На исходной машине, из корня проекта:

```powershell
python tools/project_transfer.py audit
python tools/project_transfer.py pack
git bundle create transfers/film-pipeline.bundle main HEAD
git bundle verify transfers/film-pipeline.bundle
```

`transfers/film-assets.zip` содержит выбранные чекпоинты, кадры, референсы,
dry narration, стемы и master, старый полный фильм, монтажные public-ассеты,
метаданные и ComfyUI-входы. SHA256 каждого файла — в манифесте внутри архива;
SHA256 архива — рядом. Кеши, окружения, node_modules, учётные данные и Docker
user-база не переносятся. Готовые вложенные ZIP не дублируются.
В Git-пакет включается только main/HEAD, без служебных refs приложения.

Веса можно скачать заново (`python tools/bootstrap.py models`) либо перенести:

```powershell
python tools/project_transfer.py pack --models
# На новой машине после восстановления film-assets.zip:
python tools/project_transfer.py restore /путь/film-models.zip
```

Модельный пакет содержит только три веса из v8 model-lock, с проверкой SHA256.
Дополнительная недистиллированная base-модель не нужна для воспроизведения пилота.
Восстановление не перезаписывает отличающиеся файлы. Совпадающие пропускаются.
Пакеты содержат приватные творческие материалы; передавать их доверенным способом.

## GitHub

Создавать приватный репозиторий, не публичный. После входа в свой GitHub:

```powershell
gh auth login --hostname github.com
python tools/publish.py
```

Если `origin` уже существует — сначала проверить `git remote -v`, не менять его
и не выполнять force push. Ключи/токены не передавать в чат и не добавлять в Git.
На другой машине клонировать показанный GitHub URL и восстановить пакет ассетов.
Без GitHub перенести `.bundle` и `.zip`, затем клонировать bundle как обычный URL.
