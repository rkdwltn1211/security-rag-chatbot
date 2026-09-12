import os
from pathlib import Path
from urllib.parse import urlsplit
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
# Deployment platforms supply process variables; never load a developer file there.
if os.getenv('APP_ENV', 'development').lower() != 'production':
    load_dotenv(BACKEND_DIR.parent / '.env')


def chroma_directory():
    path = Path(os.getenv('CHROMA_DIR', 'vectorstore'))
    return str(path if path.is_absolute() else BACKEND_DIR / path)


def allowed_origins():
    production = os.getenv('APP_ENV', 'development').lower() == 'production'
    configured = os.getenv('CORS_ORIGINS', '')
    if not configured.strip():
        if production:
            raise RuntimeError('CORS_ORIGINS is required in production')
        configured = 'http://localhost:5173,http://localhost,http://localhost:80'
    origins = list(dict.fromkeys(x.strip() for x in configured.split(',') if x.strip()))
    if not origins:
        raise RuntimeError('CORS_ORIGINS must contain explicit origins')
    for origin in origins:
        url = urlsplit(origin)
        if ('*' in origin or url.scheme not in ('http', 'https') or not url.hostname
                or url.username or url.password or url.path or url.query or url.fragment):
            raise RuntimeError('CORS_ORIGINS must contain explicit HTTP(S) origins without paths')
        if production and url.scheme != 'https':
            raise RuntimeError('Production CORS origins must use HTTPS')
    return origins
