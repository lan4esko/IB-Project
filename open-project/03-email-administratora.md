# 03. Смена email администратора

При установке создаётся учётная запись **`admin`** с почтой-заглушкой
`admin@example.net` (логин и пароль — в отчёте об установке `README` в этом же
каталоге). Почта нужна для писем (уведомления, сброс пароля), поэтому её стоит
заменить на реальную.

Правило: `openproject/admin_email` в мастере задаёт адрес **только при первой
создании** пользователя. Уже существующего администратора так не переименовать.

---

## Способ 1: через веб-интерфейс (проще всего)

1. Войди как `admin`.
2. **Администрирование → Пользователи** (`Administration → Users`).
3. Открой пользователя `admin` → **Изменить**.
4. Поле **Email** → новый адрес → **Сохранить**.

---

## Способ 2: через консоль (без входа в UI)

```bash
sudo openproject run rails runner '
  u = User.find_by(login: "admin")
  u.update!(mail: "admin@example.com")
  puts "mail = #{u.mail}"
'
```

Проверка:

```bash
sudo openproject run rails runner 'puts User.find_by(login: "admin").mail'
```

---

## Сменить email для будущих установок

Если разворачиваешь OpenProject с нуля повторно и хочешь другой адрес по
умолчанию — поменяй ответ мастера:

```bash
sudo openproject reconfigure      # в вопросе про email укажи новый
# либо
sudo sed -i 's|^openproject/admin_email .*|openproject/admin_email admin@example.com|' \
  /etc/openproject/installer.dat
sudo openproject configure
```

---

## Сброс пароля администратора

```bash
sudo openproject run rails runner '
  u = User.find_by(login: "admin")
  pwd = SecureRandom.alphanumeric(20)
  u.password = u.password_confirmation = pwd
  u.save!
  puts "Новый пароль: #{pwd}"
'
```

Пароль также можно сменить в UI: **Администрирование → Пользователи → admin →
Изменить** (раздел «Аутентификация»).
