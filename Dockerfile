FROM python:3.11-slim

# SETTING WORK DIRECTORY
WORKDIR /app

# DEPENDENSIES
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


COPY . .

# START COMMAND
CMD ["python", "-m", "bot.main"]
