#!/usr/bin/env python3
"""Non-destructive, exact-match hotfix for IB Platform v0.5 and GovSec corpus v1."""
from __future__ import annotations
import ast
import datetime as dt
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile

ROOT = Path('/home/admsec/ZGT/AI')
CORPUS = ROOT / 'ib-govsec-rag-corpus-v1/govsec.py'
RAG = ROOT / 'ib-platform/backend/app/rag.py'

OLD_PDF = '''def pdf_pages(src):
    raw = run(['pdftotext', '-layout', '-enc', 'UTF-8', str(src), '-'], 180)
    pages = raw.split('\\f')
    while pages and not pages[-1].strip():
        pages.pop()
    return pages
'''
NEW_PDF = '''def pdf_pages(src):
    raw = run(['pdftotext', '-layout', '-enc', 'UTF-8', str(src), '-'], 180)
    pages = raw.split('\\f')
    # Only the last empty element is the trailing form-feed sentinel.
    # Earlier empty elements represent scanned pages and MUST be preserved for OCR.
    if pages and not pages[-1].strip():
        pages.pop()
    # Some image-only PDFs return no text/form-feed at all. Recover the real page count.
    metadata = run(['pdfinfo', str(src)], 60)
    match = re.search(r'^Pages:\\s+(\\d+)\\s*$', metadata, re.MULTILINE)
    if not match:
        raise ValueError('Не удалось определить количество страниц PDF через pdfinfo')
    page_count = int(match.group(1))
    if page_count < 1 or page_count > 4000:
        raise ValueError('Недопустимое число страниц PDF')
    if len(pages) < page_count:
        pages.extend([''] * (page_count - len(pages)))
    return pages[:page_count]
'''
OLD_CAND = 'MAX_CANDIDATES = 2000\n'
NEW_CAND = '''# Temporary pilot limit: 2905+ chunks must be searchable, including early imported laws.
# SQL-side indexed lexical search/pgvector will replace this bounded scan in the next release.
MAX_CANDIDATES = min(10000, max(2000, int(os.getenv('IB_RAG_MAX_CANDIDATES', '5000'))))
'''


def prepare_patch(path: Path, old: str, new: str) -> tuple[str, str] | None:
    if not path.is_file():
        raise RuntimeError(f'Не найден исходный файл: {path}')
    data = path.read_text(encoding='utf-8')
    if new in data:
        print('Уже исправлен:', path)
        return None
    if data.count(old) != 1:
        raise RuntimeError(f'Неподдерживаемая версия {path}: ожидаемый фрагмент не найден. Ничего не меняем.')
    result = data.replace(old, new, 1)
    ast.parse(result, filename=str(path))
    return data, result


def apply():
    try:
        # Validate BOTH files before changing either.
        todo = []
        for path, old, new in [(CORPUS, OLD_PDF, NEW_PDF), (RAG, OLD_CAND, NEW_CAND)]:
            pair = prepare_patch(path, old, new)
            if pair is not None:
                todo.append((path, pair[1]))
        stamp = dt.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        for path, content in todo:
            backup = path.with_name(path.name + f'.pre-hotfix-{stamp}.bak')
            shutil.copy2(path, backup)
            fd, name = tempfile.mkstemp(prefix='.ibhotfix-', dir=path.parent)
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as file:
                    file.write(content)
                os.chmod(name, stat.S_IMODE(path.stat().st_mode))
                os.replace(name, path)
            finally:
                if os.path.exists(name):
                    os.unlink(name)
            print('Исправлен:', path)
            print('Резервная копия:', backup)
        print('Готово. Миграция БД не требуется; после обновления RAG пересобери ib-api.')
    except Exception as e:
        sys.exit('ОШИБКА: ' + str(e))

if __name__ == '__main__':
    apply()
