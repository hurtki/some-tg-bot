from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Dict, Any
import yaml
import os



class Settings(BaseSettings):
    # из .env 
    bot_token: str
    

    channel_username: str
    bot_username: str
    group_username: str 
    admin_ids: list[int]
    
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(__file__), ".env"),
        env_file_encoding='utf-8'
    )

# из messages.yaml
class Messages:
    def __init__(self, yaml_file: str = 'messages.yaml'):
        config_path = os.path.join(os.path.dirname(__file__), yaml_file)
        with open(config_path, 'r', encoding='utf-8') as f:
            self.data = yaml.safe_load(f)
    
    def get(self, path: str, **kwargs) -> str:
        """Получить сообщение по пути, например: 'subscription.check_required'"""
        keys = path.split('.')
        value = self.data

        try:
            for key in keys:
                value = value[key]
        except (KeyError, TypeError):
            raise KeyError(f"Path '{path}' not found in messages YAML.")

        # Форматирование с переданными параметрами
        if kwargs:
            return value.format(**kwargs)
        return value

try:  
    settings = Settings()
    print("Конфиг настроек был получен удачно!")
except Exception as e:
    print(f"Ошибка при читании из .env файла: {e}")
    raise

try:
    messages = Messages(yaml_file="messages.yaml")
    print("Конфиг сообщений был получен удачно!")
except Exception as e:
    print(f"Ошибка при читании из messages.yaml файла: {e}")
    raise

# Экспортируем объекты для использования в других модулях
__all__ = ['settings', 'messages']