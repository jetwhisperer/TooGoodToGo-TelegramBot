FROM python:3.12-slim

WORKDIR /usr/src/TooGoodToGo-TelegramBot

# Copy build dependencies to workdir
COPY requirements.txt .

# Install dependencies
RUN pip install --root-user-action=ignore --upgrade pip
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Run bot on container start
ENTRYPOINT [ "python", "-u", "Telegram.py" ]