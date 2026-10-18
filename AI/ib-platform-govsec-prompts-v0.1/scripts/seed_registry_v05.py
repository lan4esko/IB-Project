#!/usr/bin/env python3
"""Вносит только справочник НПА в существующий RAG v0.5 (НЕ ПОЛНЫЕ ТЕКСТЫ)."""
import getpass, json, urllib.request, urllib.error, secrets, sys
from pathlib import Path
base='http://127.0.0.1:8001'
path=Path(__file__).resolve().parent.parent/'registry'/'directory_for_rag.txt'
def request(method,endpoint,data,ctype,token=None):
    headers={'Content-Type':ctype}
    if token: headers['Authorization']='Bearer '+token
    req=urllib.request.Request(base+endpoint, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req,timeout=80) as res: return json.loads(res.read().decode())
    except urllib.error.HTTPError as exc:
        body=exc.read(2048).decode(errors='replace')
        raise SystemExit(f'HTTP {exc.code} на {endpoint}: {body}')
    except urllib.error.URLError as exc: raise SystemExit(str(exc))
password=getpass.getpass('Пароль admin IB Platform: ')
login=json.dumps({'username':'admin','password':password}).encode()
del password
r=request('POST','/api/v1/auth/login',login,'application/json')
token=r['access_token']
data=path.read_bytes()
boundary='----ibgovsec'+secrets.token_hex(10)
body=(f'--{boundary}\r\nContent-Disposition: form-data; name="title"\r\n\r\n'
      'Указатель НПА госсектора — НЕ полный текст\r\n'
      f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="govsec-directory.txt"\r\n'
      'Content-Type: text/plain; charset=utf-8\r\n\r\n').encode()+data+(f'\r\n--{boundary}--\r\n').encode()
res=request('POST','/api/v1/documents',body,'multipart/form-data; boundary='+boundary,token)
docid=res['id']
indexed=request('POST',f'/api/v1/rag/documents/{docid}/index',b'{"mode":"lexical"}','application/json',token)
print(f'Справочник (только метаданные) загружен: document_id={docid}, indexed_chunks={indexed["indexed_chunks"]}')
result=request('POST','/api/v1/rag/search',json.dumps({'query':'приказ ФСТЭК 117','mode':'lexical','top_k':3},ensure_ascii=False).encode('utf-8'),'application/json',token)
if result.get('count',0)<1:
    raise SystemExit('Не найден тестовый фрагмент ФСТЭК №117 после индексации')
print(f'Поиск по справочнику: найдено {result["count"]} совпадений (не полнотекстовая НПА).')
print('Для содержательных выводов отдельно загрузите полные актуальные тексты нормативных актов.')
