"""
generate_hash.py

One-off helper script — run this locally to generate a bcrypt hash for
a password, then paste the output into the `password_hash` column in
the Employees sheet for that person.

Usage:
    python generate_hash.py YourPasswordHere
"""

import sys
import bcrypt

if len(sys.argv) != 2:
    print("Usage: python generate_hash.py YourPasswordHere")
    sys.exit(1)

password = sys.argv[1]
hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
print("\nCopy this whole string into the password_hash column:\n")
print(hashed)
print()
