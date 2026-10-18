# 02. Замена SSL-сертификата

Сейчас используется **самоподписанный** сертификат:

- сертификат: `/etc/ssl/certs/openproject.crt`
- ключ: `/etc/ssl/private/openproject.key`
- SAN: `srv-debian`, `localhost`, `127.0.0.1`, `192.168.0.198`, `195.170.198.48`
- срок действия: 825 дней

Браузер будет показывать предупреждение, пока не появится сертификат, выпущенный
публичным удостоверяющим центром на реальный домен.

---

## Вариант A: заменить файлы по тем же путям (быстро)

Подходит, если сертификат уже выдан (например, от Let's Encrypt или
корпоративного УЦ) и ты просто кладёшь его на место старого.

```bash
sudo cp new.crt        /etc/ssl/certs/openproject.crt
sudo cp new.key        /etc/ssl/private/openproject.key

# Если есть цепочка промежуточных сертификатов — склей CRT + chain:
# sudo cat new.crt chain.crt | sudo tee /etc/ssl/certs/openproject.crt >/dev/null

sudo chmod 640 /etc/ssl/private/openproject.key
sudo chown root:ssl-cert /etc/ssl/private/openproject.key
sudo apache2ctl configtest && sudo systemctl reload apache2
```

Apache читает сертификат мастер-процессом от root, поэтому группы `ssl-cert`
достаточно.

---

## Вариант B: указать другие пути через reconfigure

Если сертификат лежит в другом месте (например `/etc/letsencrypt/live/...`):

```bash
sudo openproject reconfigure
```

В вопросах SSL укажи:

- `server/ssl_cert` → путь к `.crt` (или `fullchain.pem`)
- `server/ssl_key`  → путь к `.key` (`privkey.pem`)
- `server/ssl_ca`   → цепочка промежуточных CA (обычно пусто для fullchain)

Либо неинтерактивно — скриптом:

```bash
sudo /home/admsec/ZGT/open-project/scripts/set-hostname.sh \
  project.example.com \
  /etc/letsencrypt/live/project.example.com/fullchain.pem \
  /etc/letsencrypt/live/project.example.com/privkey.pem
```

Пути попадут в `/etc/openproject/addons/apache2/includes/vhost/ssl.conf`:

```apache
SSLCertificateFile    /etc/ssl/certs/openproject.crt
SSLCertificateKeyFile /etc/ssl/private/openproject.key
```

Проверь после применения:

```bash
sudo apache2ctl -t -D DUMP_VHOSTS | grep -A2 443
sudo ss -ltnp | grep :443
```

---

## Вариант C: Let's Encrypt (бесплатный сертификат на домен)

Требуется реальный домен, указывающий на сервер, и открытый порт 80.

```bash
sudo apt install -y certbot
sudo systemctl stop apache2
sudo certbot certonly --standalone -d project.example.com
sudo systemctl start apache2
```

Затем переведи OpenProject на эти пути (вариант B). Для автообновления создай
post-hook, перезагружающий Apache:

```bash
echo -e '#!/bin/sh\nsystemctl reload apache2' | sudo tee /etc/letsencrypt/renewal-hooks/deploy/openproject.sh
sudo chmod +x /etc/letsencrypt/renewal-hooks/deploy/openproject.sh
sudo certbot renew --dry-run
```

> Важно: при смене домена не забудь также обновить имя хоста — см. мануал 01.

---

## Самоподписанный сертификат заново (если нужно)

```bash
sudo openssl req -x509 -nodes -newkey rsa:2048 -days 825 \
  -keyout /etc/ssl/private/openproject.key \
  -out /etc/ssl/certs/openproject.crt \
  -subj "/CN=project.example.com" \
  -addext "subjectAltName=DNS:project.example.com,IP:10.0.0.5"
sudo systemctl reload apache2
```
