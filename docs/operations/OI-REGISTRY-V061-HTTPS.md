# OI Registry v0.6.1-alpha — HTTPS на Debian/VirtualBox

**Состояние:** проект конфигурации, не внедрён. Сохраняет отдельный тестовый Compose-проект `oi-registry-v06-test`; v0.5 не изменяет.

## 1. Защита и сертификат

- Сертификат и приватный ключ выпускаются для адреса, который реально открывают пользователи. Предпочтительна корпоративная CA / PKI с SAN-DNS для имени сервиса. Не хранить закрытые ключи в Git или общей папке VirtualBox.
- Самоподписанный сертификат для эксперимента не доверен браузеру автоматически. Нельзя просто отключить проверку сертификата: импортируйте доверенный корневой сертификат либо используйте сертификат корпоративного УЦ.
- TLS завершается контейнером `oi-tls` (443); трафик `oi-tls → oi-web → oi-api` остаётся внутри одной Docker bridge-сети. Cookie `Secure` задаётся `OI_COOKIE_SECURE=true` в Compose override.
- Оставшийся порт HTTP (8085/18085) должен слушать только `127.0.0.1` и не пробрасываться наружу. Для строгого HTTPS-only требуется также блокировка доступа к нему пользователям/операторам извне. HSTS отправляется только HTTPS-прокси; не включайте его на рабочих доменах до проверки сертификатов.

## 2. Проверка стенда

Для локального теста на Debian (при наличии `openssl`), без передачи ключей пользователю или Git:

```bash
sudo install -d -m 700 /etc/oi-registry-tls
sudo openssl req -x509 -newkey rsa:3072 -nodes -days 30 \
  -keyout /etc/oi-registry-tls/server.key \
  -out /etc/oi-registry-tls/server.crt \
  -subj '/CN=localhost' \
  -addext 'subjectAltName=DNS:localhost,IP:127.0.0.1'
sudo chmod 600 /etc/oi-registry-tls/server.key
cd /home/admsec/ZGT-v06-test/CMDB/oi-registry-v0.1
export OI_TLS_CERT_DIR=/etc/oi-registry-tls
export OI_TLS_BIND=127.0.0.1
export OI_TLS_PORT=18443
docker compose -p oi-registry-v06-test -f compose.yaml -f compose.https.yaml config -q
docker compose -p oi-registry-v06-test -f compose.yaml -f compose.https.yaml up -d oi-tls oi-api oi-web
curl --cacert /etc/oi-registry-tls/server.crt -I https://localhost:18443/
```

`openssl -nodes` нужен лишь для того, чтобы контейнер смог запуститься без интерактивного ввода пароля. Поэтому права файла и доступ к серверу критичны. В нормальной эксплуатации предпочтительны PKI и управляемая ротация сертификатов.

## 3. VirtualBox NAT и проброс портов

Если Windows-хост пробрасывает TCP 8443 → Debian guest TCP 18443, TLS **не снимается VirtualBox**: браузер устанавливает TLS до `oi-tls` внутри Debian. Сертификат должен содержать SAN для адреса/имени, которое вводится в Windows-браузере.

Для NAT port forwarding привязка внутри гостя должна принимать пакеты на гостевом сетевом интерфейсе (например, `OI_TLS_BIND=0.0.0.0`) с firewall-ограничением источников до доверенного хоста. Это **другое** значение, чем для безопасного доступа через SSH-туннель, где используйте `127.0.0.1`.

В VirtualBox NAT добавьте правило (пример, не готовая команда без знания имени ВМ и настроек сети): Host IP `127.0.0.1`, Host Port `8443`, Guest Port `18443`, Guest IP — фактический адрес гостевой ВМ, Protocol TCP. Не пробрасывайте `oi-api:8000` или PostgreSQL 5432.

Для HTTPS через SSH-туннель не требуется публичная публикация гостевого порта:

```bash
ssh -L 18443:127.0.0.1:18443 admsec@DEBIAN_SSH_HOST
```

Затем откройте в браузере `https://localhost:18443`, предварительно доверив сертификату. Не используйте `curl -k` как проверку защищённого соединения.

## 4. Откат тестового TLS

```bash
cd /home/admsec/ZGT-v06-test/CMDB/oi-registry-v0.1
OI_TLS_CERT_DIR=/etc/oi-registry-tls docker compose -p oi-registry-v06-test \
  -f compose.yaml -f compose.https.yaml stop oi-tls
```

Не используйте `down -v`: это удалит данные PostgreSQL/документы. TLS-слой отдельный, рабочую v0.5 останавливать не нужно.
