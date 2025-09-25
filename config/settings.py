"""
Django settings for config project.
Production-ready for Render (HTTPS, Postgres via DATABASE_URL, WhiteNoise).
"""

from pathlib import Path
from datetime import timedelta
from decouple import config
import os
import dj_database_url

from decouple import config

LLM_PROVIDER   = config("LLM_PROVIDER",   default="ollama")
HF_MODEL       = config("HF_MODEL",       default="aaditya/Llama3-OpenBioLLM-8B")
HF_TOKEN       = config("HF_TOKEN",       default="")
OLLAMA_BASE_URL= config("OLLAMA_BASE_URL",default="http://127.0.0.1:11434")
OLLAMA_MODEL   = config("OLLAMA_MODEL",   default="hf.co/bartowski/OpenBioLLM-Llama3-8B-GGUF:latest")

# ────────────────────────────────────────────────────────────────────────────────
# Base
# ────────────────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config("SECRET_KEY")
DEBUG = config("DEBUG", default=False, cast=bool)

# Laisse * au début; restreins plus tard à ton domaine Render et ton front
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "*").split(",")

# ────────────────────────────────────────────────────────────────────────────────
# Applications
# ────────────────────────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Apps projet
    "accounts",
    "restaurants",
    "menu",
    "market",
    "pos",
    "fidelite",
    "orders",
    "vetbot",
    "purchasing",

    # Tiers
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    'drf_yasg',
]

# ────────────────────────────────────────────────────────────────────────────────
# Middleware
# ────────────────────────────────────────────────────────────────────────────────
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    # WhiteNoise doit venir tôt (après Security/CORS)
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",


    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],  # ajoute des chemins si tu as des templates custom
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ────────────────────────────────────────────────────────────────────────────────
# Base de données (Render ↔ DATABASE_URL recommandé)
# ────────────────────────────────────────────────────────────────────────────────
# 1) Par défaut, utilise DATABASE_URL (propre à Render/Postgres managé)
# 2) Sinon retombe sur les variables DB_* (compat locales)
DATABASES = {
    "default": dj_database_url.config(
        default=None,
        conn_max_age=600,
        ssl_require=True,
    )
}

if not DATABASES["default"]:
    # Fallback sur ta config environnement DB_*
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": config("DB_NAME"),
            "USER": config("DB_USER"),
            "PASSWORD": config("DB_PASSWORD"),
            "HOST": config("DB_HOST"),
            "PORT": config("DB_PORT"),
        }
    }

# ────────────────────────────────────────────────────────────────────────────────
# Auth / DRF / JWT
# ────────────────────────────────────────────────────────────────────────────────
AUTH_USER_MODEL = "accounts.CustomUser"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# ────────────────────────────────────────────────────────────────────────────────
# Password validation
# ────────────────────────────────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ────────────────────────────────────────────────────────────────────────────────
# Internationalisation
# ────────────────────────────────────────────────────────────────────────────────
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ────────────────────────────────────────────────────────────────────────────────
# Static & Media (WhiteNoise en prod)
# ────────────────────────────────────────────────────────────────────────────────
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ────────────────────────────────────────────────────────────────────────────────
# Email (depuis env; OK pour Gmail SMTP ou autre)
# ────────────────────────────────────────────────────────────────────────────────
EMAIL_BACKEND = config("EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = config("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = config("EMAIL_PORT", cast=int, default=587)
EMAIL_USE_TLS = config("EMAIL_USE_TLS", cast=bool, default=True)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="VegNBio <odogbevi@gmails.com>")

# ────────────────────────────────────────────────────────────────────────────────
# CORS / CSRF (à piloter via variables d'env sur Render)
# ────────────────────────────────────────────────────────────────────────────────
# Exemple d’ENV à poser sur Render :
# CORS_ALLOWED_ORIGINS="https://ton-front.com http://localhost:3000"
# CSRF_TRUSTED_ORIGINS="https://ton-service.onrender.com https://ton-front.com"
CORS_ALLOWED_ORIGINS = os.getenv("CORS_ALLOWED_ORIGINS", "").split()
CSRF_TRUSTED_ORIGINS = os.getenv("CSRF_TRUSTED_ORIGINS", "").split()

# ────────────────────────────────────────────────────────────────────────────────
# Sécurité & HTTPS (derrière proxy Render)
# ────────────────────────────────────────────────────────────────────────────────
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=True, cast=bool)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# ────────────────────────────────────────────────────────────────────────────────
# Logging (console-only pour Render; volume disque éphémère)
# ────────────────────────────────────────────────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "{levelname} {asctime} {name} - {message}", "style": "{"}
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO"},
    },
}

# Régions autorisées
REGIONS_ALLOWED = ["Île-de-France"]

# Limite de créations d'offres par fournisseur sur 7 jours glissants
SUPPLIER_WEEKLY_OFFER_LIMIT = 5
