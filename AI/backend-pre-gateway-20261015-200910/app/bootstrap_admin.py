"""Run once from a terminal: python -m app.bootstrap_admin"""
import getpass
import re
from sqlalchemy import select
from app import auth, database as dbm


def main():
    if dbm.engine.dialect.name != "postgresql":
        raise SystemExit("Первичная учётная запись разрешена только на PostgreSQL")
    with dbm.SessionLocal() as db:
        if db.scalar(select(dbm.User.id).limit(1)) is not None:
            raise SystemExit("Пользователи уже существуют. Создайте нового администратора через API.")
        name = input("Имя первого администратора [admin]: ").strip() or "admin"
        if not re.fullmatch(r"[a-zA-Z0-9_.-]{3,80}", name):
            raise SystemExit("Недопустимое имя пользователя")
        pwd = getpass.getpass("Новый пароль (12–128 символов): ")
        confirm = getpass.getpass("Повтор пароля: ")
        if pwd != confirm:
            raise SystemExit("Пароли не совпадают")
        try:
            hashed = auth.hash_password(pwd)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        user = dbm.User(username=name, password_hash=hashed, role="admin", is_active=True)
        db.add(user); db.commit()
        print(f"Администратор {name} создан. Пароль не отображается и не записан в файл.")

if __name__ == "__main__":
    main()
