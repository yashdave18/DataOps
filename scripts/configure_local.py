"""Generate local Compose credentials without printing secrets or replacing .env."""

import base64
from pathlib import Path
import secrets


def configure(path):
    values = {
        'PGHOST': '127.0.0.1', 'PGPORT': '5432', 'PGDATABASE': 'olist', 'PGUSER': 'olist',
        'PGPASSWORD': secrets.token_hex(24), 'AIRFLOW_DB_PASSWORD': secrets.token_hex(24),
        'AIRFLOW_FERNET_KEY': base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
        'AIRFLOW_JWT_SECRET': secrets.token_hex(32), 'AIRFLOW_ADMIN_USER': 'admin',
        'AIRFLOW_ADMIN_PASSWORD': secrets.token_hex(16),
    }
    with Path(path).open('x', encoding='utf-8') as output:
        output.write('\n'.join(f'{key}={value}' for key, value in values.items()) + '\n')


if __name__ == '__main__':
    target = Path(__file__).resolve().parents[1] / '.env'
    if target.exists():
        raise SystemExit('.env already exists; existing credentials were preserved.')
    configure(target)
    print('Created ignored .env with local Compose credentials. No secrets were printed.')
