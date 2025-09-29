
import os
import environ
from pathlib import Path
from datetime import timedelta, datetime
from urllib.parse import urlparse, parse_qsl


BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False)
)

environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

SECRET_KEY = env('SECRET_KEY', default='django-insecure-8!2zge&awu2!!)mf=f^mkg%e4&)@k_c)grk0sb)t++t((_u*#6')

DEBUG = env.bool('DEBUG', default=False)

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['localhost', '127.0.0.1', '*.railway.app', 'dev.api.diagrams.ficct.com'])

DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'drf_spectacular',
    'corsheaders',
    'channels',
]

LOCAL_APPS = [
    'apps.uml_diagrams',
    'apps.websockets',
    'apps.code_generation',
    'apps.ai_assistant',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'base.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'base.wsgi.application'
ASGI_APPLICATION = 'base.asgi.application'

# Handle DATABASE_URL - use default for build time, real URL for runtime
try:
    database_url = env("DATABASE_URL")
    tmpPostgres = urlparse(database_url)
    
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': tmpPostgres.path.replace('/', ''),
            'USER': tmpPostgres.username,
            'PASSWORD': tmpPostgres.password,
            'HOST': tmpPostgres.hostname,
            'PORT': 5432,
            'OPTIONS': dict(parse_qsl(tmpPostgres.query)),
            'TEST': {
                'NAME': 'test_DONOTUSE_ficct',
            },
        }
    }
except:
    # Fallback for build time when DATABASE_URL isn't available
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'build_temp.db',
        }
    }

REDIS_URL = env('REDIS_URL', default='redis://localhost:6379/0')

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': REDIS_URL,
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

if DEBUG:
    try:
        import redis
        redis.Redis.from_url(REDIS_URL).ping()
    except Exception:
        CACHES = {
            'default': {
                'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
                'LOCATION': 'unique-dev-cache',
            }
        }
        SESSION_ENGINE = 'django.contrib.sessions.backends.db'

if 'SESSION_ENGINE' not in globals():
    SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'
SESSION_COOKIE_AGE = 86400  # 24 hours
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'


REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '200/hour',
    },
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}


CELERY_BROKER_URL = env('CELERY_BROKER_URL', default=REDIS_URL)
CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND', default=REDIS_URL)
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

EMAIL_BACKEND = env('EMAIL_BACKEND', default='django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = env('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = env.int('EMAIL_PORT', default=587)
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=True)
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')

SENDGRID_API_KEY = env('SENDGRID_API_KEY', default='')
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='noreply@ficct-enterprise.com')
SENDGRID_SANDBOX_MODE_IN_DEBUG = DEBUG

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_HSTS_SECONDS = 31536000
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
X_FRAME_OPTIONS = 'DENY'

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True

CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=[
    'http://localhost:5173',
    'http://127.0.0.1:5173',
])

CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
    'x-nickname',
    'x-session-id',
]

CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^http://localhost:[0-9]+$",
    r"^http://127.0.0.1:[0-9]+$",
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
        'detailed': {
            'format': '{levelname} {asctime} {name} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'formatter': 'verbose',
        },
        'security_file': {
            'level': 'WARNING',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'security.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'detailed',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'django.request': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'security': {
            'handlers': ['security_file', 'console'],
            'level': 'WARNING',
            'propagate': True,
        },
        'authentication': {
            'handlers': ['security_file', 'console'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'audit': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

ENTERPRISE_DOMAIN_VALIDATION = True
ENABLE_2FA_ENFORCEMENT = True
PASSWORD_EXPIRY_DAYS = 90
MAX_LOGIN_ATTEMPTS = 5
ACCOUNT_LOCKOUT_DURATION_MINUTES = 15

ADMIN_IP_WHITELIST = env.list('ADMIN_IP_WHITELIST', default=['127.0.0.1', 'localhost'])

RATELIMIT_USE_CACHE = 'default'

SPECTACULAR_SETTINGS = {
    'TITLE': 'FICCT UML Diagram Collaborative API',
    'DESCRIPTION': 'UML diagramming platform with anonymous real-time collaboration, instant access, and no registration.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'SCHEMA_PATH_PREFIX': '/api/',
    'COMPONENT_SPLIT_REQUEST': True,
    'COMPONENT_NO_READ_ONLY_REQUIRED': False,
    'POSTPROCESSING_HOOKS': [],
    'SWAGGER_UI_SETTINGS': {
        'deepLinking': True,
        'persistAuthorization': False,  # No auth needed
        'displayOperationId': True,
        'displayRequestDuration': True,
        'filter': True,
        'syntaxHighlight.theme': 'monokai',
        'tryItOutEnabled': True,
        'supportedSubmitMethods': ['get', 'post', 'put', 'patch', 'delete'],
        'docExpansion': 'list',
        'operationsSorter': 'alpha',
        'tagsSorter': 'alpha',
        'defaultModelsExpandDepth': 2,
        'defaultModelExpandDepth': 2,
    },
    'REDOC_UI_SETTINGS': {
        'hideDownloadButton': False,
        'theme': {
            'colors': {
                'primary': {
                    'main': '#667eea'
                }
            },
            'typography': {
                'fontSize': '14px',
                'fontFamily': 'Inter, system-ui, sans-serif'
            }
        }
    },
    'TAGS': [
        {
            'name': 'System',
            'description': 'System health checks and API information'
        },
        {
            'name': 'UML Diagrams',
            'description': 'Anonymous UML diagram creation, editing, and export functionality'
        },
        {
            'name': 'WebSocket Collaboration',
            'description': 'Real-time anonymous collaboration, chat with guest nicknames'
        },
        {
            'name': 'AI Assistant',
            'description': 'Contextual AI help for UML diagrams and system functionality'
        }
    ],
    'EXTERNAL_DOCS': {
        'description': 'Project Documentation',
        'url': 'https://github.com/Victoroide/ficct-springcode-backend'
    },
    'CONTACT': {
        'name': 'UML Tool Support',
        'email': 'contact@example.com'
    },
    'LICENSE': {
        'name': 'MIT License',
    }
}

try:
    redis_url = env('REDIS_URL', default='redis://localhost:6379/0')
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {
                'hosts': [redis_url],
            },
        },
    }
except:
    # Fallback for environments without Redis
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer',
        },
    }

ASGI_APPLICATION = 'base.asgi.application'

THROTTLE_RATES = {
    'public_diagram': '30/min',
    'anon': '100/hour',
    'user': '1000/hour'
}

# OpenAI Configuration
OPENAI_AZURE_API_KEY = env('OPENAI_AZURE_API_KEY', default='')
OPENAI_AZURE_API_VERSION = env('OPENAI_AZURE_API_VERSION', default='2024-02-15-preview')
OPENAI_AZURE_API_BASE = env('OPENAI_AZURE_API_BASE', default='')

# AI Assistant Configuration
AI_ASSISTANT_ENABLED = env.bool('AI_ASSISTANT_ENABLED', default=True)
AI_ASSISTANT_RATE_LIMIT = env('AI_ASSISTANT_RATE_LIMIT', default='30/hour')
AI_ASSISTANT_DEFAULT_MODEL = env('AI_ASSISTANT_DEFAULT_MODEL', default='paralex-gpt-4o')
