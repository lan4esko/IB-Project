# Git, LazyGit и выпускаемые версии

## Историческое состояние

Репозиторий инициализирован в `/home/admsec/ZGT` через LazyGit. В одном из предыдущих журналов Git вернул `Author identity unknown` и первый коммит не состоялся; затем ветка переименовывалась и создавалась feature-ветка. **Наличие стабильного коммита `main` не подтверждено**. Перед развитием проекта проверить `git log --oneline`, `git branch -vv`, `git status`.

## Инициализация конфигурации автора только локально

```bash
cd /home/admsec/ZGT
git status --short
git log --oneline -3
git branch -vv
git config --local user.name
git config --local user.email
```

Если имя/email пусты, настроить локально фактические значения с согласия автора, затем создать первый коммит после проверок. Нельзя утверждать, что первый commit уже существует, если `git log` возвращает ошибку.

## Коммит проекта

1. Перед `git add` проверить `.gitignore` и исключения реальных секретов: `git check-ignore CMDB/oi-registry-v0.1/.env CMDB/BACKUPS/имя.tar.gz`.
2. Не выполнять слепое `git add .` на корне, где лежат `AI/`, `CMDB/`, `open-project/`; добавлять только проверенные пути и `docs/`.
3. Проверять `git diff --cached --check`, `git diff --cached --stat` и содержимое staged diff, а не только количество файлов.
4. Создавать ветку от `main` **после** наличия стабильного коммита. `feature/openproject-integration` не считать уже объединённой/готовой интеграцией.
5. В коммит с изменением версии обязательно включать соответствующую документацию (см. [DOCUMENTATION-POLICY](../DOCUMENTATION-POLICY.md)); перед merge проверить локальные smoke tests.
6. Для релиза в isolated VM переносить commit/тег через approved Git bundle или защищённый офлайн-носитель, проверяя SHA256 и происхождение.

## Подключение guard документации

```bash
cd /home/admsec/ZGT
bash docs/scripts/install_git_hook.sh
python3 docs/scripts/verify_docs.py
```

Hook блокирует коммит изменений критичных путей backend/frontend/compose без одновременного обновления `docs/CHANGELOG.md` и `docs/RELEASES.md`. Это не автоматическое угадывание архитектуры: автор обязан описать фактическое изменение. Существующий Git hook не перезаписывается.

## Новый релиз

```bash
cd /home/admsec/ZGT
python3 docs/scripts/new_release.py v0.5 oi-registry
# Внесите правдивые сведения в шаблон, CHANGELOG.md и RELEASES.md.
python3 docs/scripts/verify_docs.py
git add docs/
git diff --cached --check
```

**Никогда не применять `git reset --hard` на рабочей папке без сохранения незакоммиченных изменений.** Git rollback не откатывает Alembic и реальные данные PostgreSQL. Rollback приложения с изменённой схемой должен опираться на совместимую миграцию и бэкап.
