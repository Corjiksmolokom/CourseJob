"""Конфигурация приложения"""
import os
from dotenv import load_dotenv
load_dotenv()

class Settings:
    """Настройки приложения"""

    def __init__(self):
        self.db_user: str = os.getenv('DB_USER', 'postgres')
        self.db_password: str = os.getenv('DB_PASSWORD', 'postgres')
        self.db_host: str = os.getenv('DB_HOST', 'localhost')
        self.db_port: str = os.getenv('DB_PORT', '5432')
        self.db_name: str = os.getenv('DB_NAME', 'rukami_db')

        self.host: str = os.getenv('HOST', '127.0.0.1')
        self.port: int = int(os.getenv('PORT', '8000'))
        self.debug: bool = os.getenv('DEBUG', 'false').lower() == 'true'
        # Настройки файлов
        self.upload_folder: str = os.getenv('UPLOAD_FOLDER', 'uploads')
        self.max_file_size: int = int(os.getenv('MAX_FILE_SIZE', '10485760'))

    @property
    def database_url(self) -> str:
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

settings = Settings()