from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Dict, Any
import yaml

class Settings(BaseSettings):
    # из .env 
    bot_token: str
    
    # из config.yaml
    channel_username: str
    bot_username: str
    group_username: str 
    
    model_config = SettingsConfigDict(
        env_file='.env',
        yaml_file='config.yaml',
        env_file_encoding='utf-8'
    )

# из messages.yaml
class Messages:
    def __init__(self, yaml_file: str = 'messages.yaml'):
        with open(yaml_file, 'r', encoding='utf-8') as f:
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
except Exception as e:
    print(f"ошибка при читании из .env файла или config.yaml: {e}")
try:
    messages = Messages(yaml_file="messages.yaml")
except Exception as e:
    print(f"ошибка при читании из messages.yaml файла: {e}")
    

print(messages.get(path="buttons.write_post"))
print(settings.bot_token, settings.bot_username, settings.channel_username, settings.group_username)

"""
примеры использования

BOT_TOKEN = settings.bot_token 
post_approved = messages.get('user_notifications.approved', post_id=123)

"""
