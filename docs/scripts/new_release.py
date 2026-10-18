#!/usr/bin/env python3
"""Create a reviewable release template; never invent deployed features."""
from pathlib import Path
import re,sys,datetime
D=Path(__file__).resolve().parents[1]
if len(sys.argv)!=3:
 print('Usage: python3 docs/scripts/new_release.py <version> <system>',file=sys.stderr);sys.exit(2)
ver,system=sys.argv[1:]
if not re.fullmatch(r'[A-Za-z0-9._-]{2,48}',ver) or not re.fullmatch(r'[A-Za-z0-9._-]{2,48}',system):
 raise SystemExit('version/system must be simple safe filename tokens')
release=D/'releases'/f'{system}-{ver}.md'
release.parent.mkdir(exist_ok=True)
if release.exists():raise SystemExit('Release file exists: '+str(release))
today=datetime.date.today().isoformat()
release.write_text(f"""# Release {system} {ver} — ЧЕРНОВИК

- Дата планирования: {today}
- Состояние: **НЕ ВНЕДРЁН**, заполнить после фактической проверки
- Git commit/tag: ТРЕБУЕТ ПРОВЕРКИ
- Alembic/пакет/образ: ТРЕБУЕТ ПРОВЕРКИ
- Новый функционал: ОПИСАТЬ ПО ИСХОДНИКАМ
- Схема, API, сеть, безопасность, роли: ОПИСАТЬ
- Как обновить и откатить: ОПИСАТЬ
- Бэкап и SHA256: ТРЕБУЕТ ПРОВЕРКИ
- Тесты, результаты DR: ТРЕБУЕТ ПРОВЕРКИ
- Изменённые docs/диаграммы: ПЕРЕЧИСЛИТЬ
""",encoding='utf-8')
with (D/'CHANGELOG.md').open('a',encoding='utf-8') as f:
 f.write(f'\n## {system} {ver} — {today} (ЧЕРНОВИК, НЕ ВНЕДРЁН)\n\n- См. [шаблон релиза](releases/{release.name}); заполнить по факту.\n')
with (D/'RELEASES.md').open('a',encoding='utf-8') as f:
 f.write(f'\n- {system} {ver}: **ЧЕРНОВИК, НЕ ВНЕДРЁН**. [Досье релиза](releases/{release.name}).\n')
print(f'Created {release}; fill facts then review/update system docs, topology and procedures.')
