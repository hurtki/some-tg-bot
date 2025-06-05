FROM python:3.11-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем зависимости и устанавливаем
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем все, кроме venv и __pycache__
COPY . .

# Указываем команду запуска
CMD ["python", "-m", "bot.main"]
