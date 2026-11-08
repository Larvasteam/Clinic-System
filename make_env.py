"""Creates a .env file for running the system on your own computer. Run it once:  python make_env.py"""
import secrets
from pathlib import Path

env = Path(__file__).resolve().parent / '.env'
if env.exists():
    print('.env already exists, leaving it alone.')
else:
    env.write_text(
        f"DJANGO_SECRET_KEY={secrets.token_urlsafe(50)}\n"
        "DJANGO_DEBUG=True\n"
        "# Free key from allratestoday.com for the RBZ official USD to ZiG rate (optional, see README)\n"
        "ALLRATES_API_KEY=\n"
    )
    print('Created .env with a new secret key (local settings).')
