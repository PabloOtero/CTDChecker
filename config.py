"""Flask configuration."""

DEBUG = True
FLASK_ENV = 'development'
SECRET_KEY = 'your_secret_key'
UPLOAD_FOLDER = ''
MAX_CONTENT_LENGTH = 64 * 1024 * 1024

MAIL_SERVER = 'smtp-mail.outlook.com'
MAIL_PORT = 587
MAIL_USERNAME = 'your_email_address'
MAIL_PASSWORD = 'your_email_password'
MAIL_USE_TLS = True
MAIL_USE_SSL = False

