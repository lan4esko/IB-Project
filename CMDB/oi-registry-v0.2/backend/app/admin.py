"""Create admin or viewer account from stdin without putting passwords in shell history."""
import getpass
import sys
from argon2 import PasswordHasher
from sqlalchemy import select
from app.db import SessionLocal
from app.models import User


def main():
    if len(sys.argv) not in (2, 3):
        sys.exit("Usage: python -m app.admin USERNAME [admin|viewer]")
    username = sys.argv[1].strip()
    role = sys.argv[2] if len(sys.argv) == 3 else "admin"
    if not username or len(username) > 100 or role not in {"admin", "viewer"}:
        sys.exit("Invalid username or role")
    password = sys.stdin.readline().rstrip("\n") if not sys.stdin.isatty() else getpass.getpass("Password: ")
    if len(password) < 12:
        sys.exit("Password must contain at least 12 characters")
    with SessionLocal.begin() as db:
        existing = db.scalar(select(User).where(User.username == username))
        if existing:
            sys.exit("Account already exists. No changes made.")
        db.add(User(username=username, password_hash=PasswordHasher().hash(password), role=role))
    print(f"User {username} ({role}) created")


if __name__ == "__main__":
    main()
