
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

    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'build_temp.db',
        }
    }

REDIS_URL = env('REDIS_URL', default=None)

IS_RAILWAY = env.bool('RAILWAY_ENVIRONMENT', default=False)

if REDIS_URL and IS_RAILWAY:

    try:
        import redis
        redis_client = redis.Redis.from_url(REDIS_URL)
        redis_client.ping()
        
        CACHES = {
            'default': {
                'BACKEND': 'django_redis.cache.RedisCache',
                'LOCATION': REDIS_URL,
                'OPTIONS': {
                    'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                }
            }
        }
        SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
        REDIS_AVAILABLE = True
        
    except Exception as e:
        import logging
        logging.warning(f"Railway Redis failed ({e}), using database cache")
        REDIS_AVAILABLE = False
else:

    REDIS_AVAILABLE = False

if not REDIS_AVAILABLE:

    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
            'LOCATION': 'django_cache_table',
        }
    }
    SESSION_ENGINE = 'django.contrib.sessions.backends.db'
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
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

if REDIS_AVAILABLE:
    REST_FRAMEWORK.update({
        'DEFAULT_THROTTLE_CLASSES': [
            'rest_framework.throttling.AnonRateThrottle',
        ],
        'DEFAULT_THROTTLE_RATES': {
            'anon': '200/hour',
        },
    })
else:

    import logging
    logging.warning("Throttling disabled - Redis not available")




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
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

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

if REDIS_AVAILABLE and REDIS_URL:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {
                'hosts': [REDIS_URL],
                'capacity': 1500,
                'expiry': 60,
            },
        },
    }
    import logging
    logging.info("Using Redis for WebSocket channels")
else:

    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer',
            'CAPACITY': 100,
            'EXPIRY': 60,
        },
    }
    import logging
    logging.warning("Using InMemory channels - WebSockets may not work across multiple instances")

ASGI_APPLICATION = 'base.asgi.application'

OPENAI_AZURE_API_KEY = env('OPENAI_AZURE_API_KEY', default='')
OPENAI_AZURE_API_VERSION = env('OPENAI_AZURE_API_VERSION', default='2024-02-15-preview')
OPENAI_AZURE_API_BASE = env('OPENAI_AZURE_API_BASE', default='')

AI_ASSISTANT_ENABLED = env.bool('AI_ASSISTANT_ENABLED', default=True)
AI_ASSISTANT_RATE_LIMIT = env('AI_ASSISTANT_RATE_LIMIT', default='30/hour')
AI_ASSISTANT_DEFAULT_MODEL = env('AI_ASSISTANT_DEFAULT_MODEL')

THROTTLE_RATES = {
    'public_diagram': AI_ASSISTANT_RATE_LIMIT,
    'anon': AI_ASSISTANT_RATE_LIMIT,
    'user': AI_ASSISTANT_RATE_LIMIT
}