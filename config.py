import os
import pymysql

# 🔹 Make PyMySQL act like MySQLdb (Windows fix)
pymysql.install_as_MySQLdb()

class Config:
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:root123@localhost/inventory'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # File upload configuration
    UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'docx', 'xlsx'}
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size