# Дополнение к документации ZGT: Windows Server 2019 / VirtualBox

Состав: эксплуатационное руководство 496+ строк, две схемы Mermaid, шаблон паспорта сети, read-only PowerShell-инвентаризация, инсталлятор без перезаписи существующих документов.

## Установка в существующий Git-каталог ZGT

1. Поместить `zgt-ws2019-addon-v1.1.zip` в `/media/sf_/` Debian.
2. Распаковать в `/home/admsec/ZGT/` и выполнить `install.sh`:

```bash
cd /home/admsec/ZGT
unzip -n /media/sf_/zgt-ws2019-addon-v1.1.zip -d /home/admsec/ZGT
bash /home/admsec/ZGT/zgt-ws2019-addon-v1.1/install.sh
```

3. Открыть `docs/operations/WS2019-VIRTUALBOX-MIGRATION.md`; выполнить `python3 docs/scripts/verify_docs.py` если установлен основной docs v1.0.
4. Проверить `git diff -- docs/`, затем коммит по локальной политике.

**Инсталлятор не изменяет приложения и сети.** Он добавляет только документы и ссылки на них. Если `docs/` из полного набора ZGT ещё не установлен, сначала установить базовый документационный пакет v1.0.
