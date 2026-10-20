# Как опубликовать OI Registry v0.7.0-rc1 вместе с docs/

**Цель:** ветка `feature/oi-registry-v0.7.0-rc1` в `git@github.com:lan4esko/IB-Project.git`. `main` не изменяется, история баз PostgreSQL не переносится в Git.

**Рабочая копия на Debian:** `/home/admsec/ZGT-v06-test`. Это Git worktree; рабочий репозиторий `/home/admsec/ZGT` и его изменённый Compose не трогаем.

## 1. Проверить рабочую копию и создать ветку

```bash
cd /home/admsec/ZGT-v06-test
git status --short
git branch --show-current
git remote -v
# Если ветка отсутствует, создать её до применения пакета:
git switch -c feature/oi-registry-v0.7.0-rc1
```

Если ветка уже существует, воспользоваться `git switch feature/oi-registry-v0.7.0-rc1` только после сверки имеющихся незакоммиченных изменений. **Не выполнять** `git reset --hard`, `git clean -fd`, `git add .` или `git push --force`.

## 2. Распаковать проверенный пакет

```bash
ARCHIVE=/media/sf_/OI-Registry-v0.7.0-rc1-github-ready.tar.gz
sha256sum "$ARCHIVE"
tar -tzf "$ARCHIVE" | less
tar -xzf "$ARCHIVE" -C /home/admsec/ZGT-v06-test
```

Предварительно сравнить SHA256 с опубликованным рядом с архивом хешем; отсутствие неожиданной версии БД и конфигурации `.env` обязательно. В архиве только отобранные исходники и публичная документация, никаких SQL dump/ключей.

## 3. Проверка документации и исходников

```bash
cd /home/admsec/ZGT-v06-test
python3 docs/scripts/verify_docs.py
python3 -m compileall -q CMDB/oi-registry-v0.1/backend/app
# Зависимости pytest могут быть установлены только в контейнере API.
# Локально: cd CMDB/oi-registry-v0.1 && python3 -m pytest -q tests
```

`git add` делать **только** по файлам манифеста архива, после проверки их путей:

```bash
cd /home/admsec/ZGT-v06-test
# Убедиться, что в индексе нет посторонних файлов:
git diff --cached --name-only
# Если индекс пуст и список архива проверен:
tar -tzf /media/sf_/OI-Registry-v0.7.0-rc1-github-ready.tar.gz | while IFS= read -r f; do git add -- "$f"; done
git diff --cached --check
git diff --cached --stat
git diff --cached --name-only
```

Если в рабочей копии есть **другие** несохранённые изменения, команда по списку архива добавит только его файлы, но может включить локальные изменения внутри этих же файлов; обязательно просмотреть `git diff --cached`. Не загружать личные данные, реальные сетевые паспорта, дампы, `*.env`, ключи или архивы.

## 4. История Git с секретами

Ранее в материалах `open-project/` встречались настоящие учётные данные. Новый коммит **не очищает** секреты из истории ветки: смените используемые пароли/токены и проверьте историю перед опубликованием. Если секреты ещё действуют, остановите push и согласуйте очистку истории. Не копируйте результаты поиска со значениями паролей в публичные логи. См. [регламент](PRE-PUSH-SECURITY.md).

## 5. Commit и push

После проверки индекса, в отдельной ветке:

```bash
cd /home/admsec/ZGT-v06-test
git commit -m "feat: OI Registry v0.7.0-rc1 and complete ER documentation"
git push -u origin feature/oi-registry-v0.7.0-rc1
git log -1 --oneline
git status --short
```

**GitHub:** `https://github.com/lan4esko/IB-Project/tree/feature/oi-registry-v0.7.0-rc1` после успешного push. Не отмечайте v0.7.0 как production и не объединяйте ветку в main до приёмки PostgreSQL/TLS и исправления блокирующих рисков.
