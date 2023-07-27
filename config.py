"""General settings"""

RUN_LOCALLY = False
PATH_LOCAL = ''
TO_NETCDF = True
MERGED_NCFILE = True

"""Flask configuration"""

DEBUG = True
FLASK_ENV = 'development'
SECRET_KEY = ''
UPLOAD_FOLDER = ''
MAX_CONTENT_LENGTH = 128 * 1024 * 1024

"""Configuration to send a mail after each execution"""
MAIL_SERVER = 'smtp-mail.outlook.com'
MAIL_PORT = 587
MAIL_USERNAME = ''
MAIL_PASSWORD = ''
MAIL_RECIPIENTS = ''
MAIL_USE_TLS = True
MAIL_USE_SSL = False

