"""
user name: admin
password: admin@123

create_admin.py
Create the admin account, or reset its password.
The password is stored only as a secure hash, never as plain text.
"""
import getpass

from werkzeug.security import generate_password_hash

import database as db


def main():
    db.init_db()
    print("Create or update the admin account")

    username = input("Username: ").strip()
    if not username:
        print("Username cannot be empty.")
        return

    password = getpass.getpass("Password (hidden while typing): ")
    if len(password) < 6:
        print("Password must be at least 6 characters.")
        return

    if password != getpass.getpass("Confirm password: "):
        print("Passwords do not match. Nothing was saved.")
        return

    created = db.save_admin(username, generate_password_hash(password))
    print(("Admin created" if created else "Admin password updated") + f" for '{username}'.")


if __name__ == "__main__":
    main()