# Too Good To Go Python Bot

*Hi welcome to the TGTG Bot:*

The bot will notify you as soon as new bags from your favorites are available.

*❗️️This is necessary if you want to use the bot❗️*
🔑 To login into your TooGoodToGo account enter 
*/login email@example.com*, in your Telegram client, in the chat with your bot.
_You will then receive an email with a confirmation link.
You do not need to enter a password._

⚙️ With */settings* you can set when you want to be notified. 

ℹ️ With */info* you can display all stores from your favorites where bags are currently available.

_🌐 You can find more information about Too Good To Go_ [here](https://www.toogoodtogo.com/).

*🌍 LET'S FIGHT food waste TOGETHER 🌎*

## Getting Started
1. Clone this project to your local PC.
   
2. Copy `config.template.ini` to `config.ini`.
   
   `cp config.template.ini config.ini`

3. Replace `<YOUR-TOKEN>` in `config.ini` with your own bot access token that you obtained from Telegram. You can create a bot and obtain a token by following the steps outlined [here](https://core.telegram.org/bots/tutorial#getting-ready).

### Requires
Python version: 3.8+

### Use it
Install all libraries that are needed:
   ```
   pip install -r requirements.txt
   ```
Start the Python script:
   ```
   python3 Telegram.py
   ```

### Docker usage
If using Docker, install requirements and start the bot with:

```
docker compose up --build -d
```

If needed, see logs with:

```
docker logs toogoodtogobot -t -f --tail 1000
```

To stop the bot:

```
docker compose down
```

## Credits goes to
[@TGTG](https://www.toogoodtogo.com/)
[@ahivert](https://github.com/ahivert/tgtg-python)
