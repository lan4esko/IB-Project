# 04. Активация Enterprise — только легально

Сейчас установлена **Community Edition**. Она бесплатна и включает почти всё
для управления проектами. Часть функций (например, несколько активных
пользователей сверх лимита, SSO/LDAP, SCIM, custom fields повышенного уровня,
BIM и т. п.) доступна только в **Enterprise**.

## Как включить Enterprise правильно

1. Оформить **бесплатную пробную лицензию** (или купить): <https://start.openproject.com/>
2. Скопировать полученный **токен**.
3. Прописать токен и перезапустить:

```bash
sudo openproject config:set OPENPROJECT_ENTERPRISE_TOKEN="<ВСТАВЬ_ТОКЕН>"
sudo openproject reconfigure      # либо: sudo systemctl restart openproject
```

4. Проверить статус: **Администрирование → Enterprise Edition**
   (`Administration → Enterprise edition`) — должно быть «Enterprise token valid».

Проверка из консоли:

```bash
sudo openproject run env | grep ENTERPRISE_TOKEN
sudo openproject run rails runner 'puts OpenProject::Token.subscriber rescue nil'
```

Убрать токен:

```bash
sudo openproject config:unset OPENPROJECT_ENTERPRISE_TOKEN
sudo systemctl restart openproject
```

---

## Почему «активатор лицензии» (кряк) использовать нельзя

- Это обход платного лицензирования — нарушение лицензии OpenProject
  (GPL применяется к Community, но Enterprise-функции лицензируются отдельно)
  и законодательства об авторском праве.
- Кряки обычно требуют выполнения стороннего кода от root на сервере — это
  прямой путь к компрометации команды и данных.
- Такой установке нельзя доверять обновления и поддержку: при первом же
  обновлении пакета всё сломается.

Поэтому такой инструмент в этой документации и в этой установке не применяется
и применяться не будет. Нужен Enterprise — оформи пробный/платный токен, это
бесплатно на время теста и занимает пару минут.
