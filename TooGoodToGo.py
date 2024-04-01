import json
import time

from pathlib import Path
from _thread import start_new_thread
from datetime import datetime
from pytz import timezone

import tgtg

from tgtg import TgtgClient
from telebot import TeleBot, types

class TooGoodToGo:

    ITEM_STATUS = {
        'sold_out': 'Sold out',
        'new_stock': 'New stock',
        'stock_reduced': 'Stock reduced',
        'stock_increased': 'Stock increased',
    }

    users_login_data = {}
    users_settings_data = {}
    available_items_favorites = {}
    connected_clients = {}
    client = TgtgClient

    def __init__(self, bot_token: str, config: dict = {}):
        self.bot = TeleBot(bot_token)
        self.__set_config(config)
        self.read_users_login_data_from_txt()
        self.read_users_settings_data_from_txt()
        self.read_available_items_favorites_from_txt()
        start_new_thread(self.get_available_items_per_user, ())
        self.bot.set_my_commands([
            types.BotCommand("/info", "favorite bags currently available"),
            types.BotCommand("/login", "log in with your email"),
            types.BotCommand("/settings", "set when you want to be notified"),
            types.BotCommand("/help", "short explanation"),
        ])
    
    def __set_config(self, config: dict):
        self.timezone = timezone(config.get('timezone', 'UTC'))
        print('timezone', self.timezone)

        self.language = config.get('language', 'en-GB')
        print('language', self.language)

        # min 2 default 5
        self.login_timeout_minutes = max(2, int(config.get('login_timeout_minutes', 5)))
        print('login_timeout_minutes', self.login_timeout_minutes)

        tgtg.MAX_POLLING_TRIES = (self.login_timeout_minutes * 60) // tgtg.POLLING_WAIT_TIME

        # min 5 default 60
        self.interval_seconds = max(5, int(config.get('interval_seconds', 60)))
        print('interval_seconds', self.interval_seconds)

        # min self.interval_seconds default 1800
        self.low_hours_interval_seconds = max(self.interval_seconds, int(config.get('low_hours_interval_seconds', 1800)))
        print('low_hours_interval_seconds', self.low_hours_interval_seconds)

        # min 0 max 23 default 23
        self.low_hours_start = max(0, min(23, int(config.get('low_hours_start', 23))))
        
        # min 0 max 23 default 6
        self.low_hours_end = max(0, min(23, int(config.get('low_hours_end', 6))))
        print('Low hours', self.low_hours_start, '-', self.low_hours_end)

    def send_message(self, telegram_user_id, message, parse_mode=None):
        self.bot.send_message(telegram_user_id, text=message, parse_mode=parse_mode)

    def send_message_with_link(self, telegram_user_id, message, item_id):
        self.bot.send_message(telegram_user_id, text=message, reply_markup=types.InlineKeyboardMarkup(
            keyboard=[
                [
                    types.InlineKeyboardButton(
                        text="Open in app 📱",
                        callback_data="open_app",
                        url="https://share.toogoodtogo.com/item/" + item_id
                    )
                ],
            ])
        )

    def read_users_login_data_from_txt(self):
        with open(data_file('users_login_data'), 'r') as file:
            data = file.read()
            self.users_login_data = json.loads(data)

    def save_users_login_data_to_txt(self):
        with open(data_file('users_login_data'), 'w') as file:
            file.write(json.dumps(self.users_login_data))

    def read_users_settings_data_from_txt(self):
        with open(data_file('users_settings_data'), 'r') as file:
            data = file.read()
            self.users_settings_data = json.loads(data)

    def save_users_settings_data_to_txt(self):
        with open(data_file('users_settings_data'), 'w') as file:
            file.write(json.dumps(self.users_settings_data))

    def read_available_items_favorites_from_txt(self):
        with open(data_file('available_items_favorites'), 'r') as file:
            data = file.read()
            self.available_items_favorites = json.loads(data)

    def save_available_items_favorites_to_txt(self):
        with open(data_file('available_items_favorites'), 'w') as file:
            file.write(json.dumps(self.available_items_favorites))

    def add_user(self, telegram_user_id, credentials):
        self.users_login_data[telegram_user_id] = credentials
        self.save_users_login_data_to_txt()

        if telegram_user_id not in self.users_settings_data:
            self.users_settings_data[telegram_user_id] = {'sold_out': 0,
                                                        'new_stock': 1,
                                                        'stock_reduced': 0,
                                                        'stock_increased': 0}
            self.save_users_settings_data_to_txt()

    # Get the credentials
    def new_user(self, telegram_user_id, telegram_username, email):
        client = TgtgClient(email=email, language=self.language)

        self.send_message(telegram_user_id, "📩 Please open your mail account."
                                    "\nYou will receive an email with a confirmation link."
                                    "\n_Opening email on mobile won't work if you have installed TooGoodToGo app._\n"
                                    "\n*You must open the link in your PC browser.*"
                                    "\n_You do not need to enter a password._", parse_mode="markdown")

        try:
            credentials = client.get_credentials()
            credentials['email'] = email
            credentials['telegram_username'] = telegram_username
            self.add_user(telegram_user_id, credentials)
            self.send_message(telegram_user_id, "✅ You are now logged in!")
        except tgtg.exceptions.TgtgPollingError as err:
            if 'Max retries' in str(err):
                self.send_message(telegram_user_id, "⏱ *Time expired. Please log in again.*")
            else:
                raise err
        except tgtg.exceptions.TgtgAPIError as err:
            self.log_api_error(err)
            self.send_message(telegram_user_id, "❌ Cannot log in. Please try again later.")
        except Exception as err:
            print(f"Unexpected {err=}, {type(err)=}")
            self.send_message(telegram_user_id, "❌ An error happened while logging in. Please try again.")

    # Look if the user is already logged in
    def find_credentials_by_telegramUserID(self, user_id):
        return self.users_login_data.get(user_id)

    # Checks if a connection already exists, or if it has to be created initially.
    def connect(self, user_id):
        if user_id in self.connected_clients:
            self.client = self.connected_clients[user_id]
        else:
            user_credentials = self.find_credentials_by_telegramUserID(user_id)

            if user_credentials is None:
                return False
            
            print(f"Connect {user_id}")
            self.client = TgtgClient(access_token=user_credentials["access_token"],
                                    refresh_token=user_credentials["refresh_token"],
                                    user_id=user_credentials["user_id"],
                                    cookie=user_credentials["cookie"],
                                    language=self.language)
            self.connected_clients[user_id] = self.client
            time.sleep(2)
        return True

    def get_favourite_items(self):
        favourite_items = self.client.get_items()
        return favourite_items

    # /info command
    def send_available_favourite_items_for_one_user(self, user_id):
        try:
            self.connect(user_id)
            available_items = []
            favourite_items = self.get_favourite_items()
            for item in favourite_items:
                if item['items_available'] > 0:
                    item_id = item['item']['item_id']
                    item_text = self.format_item(item)
                    self.send_message_with_link(user_id, item_text, item_id)
                    available_items.append(item_id)
            if not favourite_items:
                self.send_message(user_id, "You do not have any favorites to track yet")
            elif not available_items:
                self.send_message(user_id, "Currently all your favorites are sold out 😕")
        except tgtg.exceptions.TgtgAPIError as err:
            self.log_api_error(err)
            self.send_message(user_id, "❌ Cannot retrieve your items. Please try again later.")
        except Exception as err:
            print(f"Unexpected {err=}, {type(err)=}")
            self.send_message(user_id, "❌ An error happened trying to retrieve your items. Please try again.")
    
    def log_api_error(self, err):
        if err.args and 403 == err.args[0]:
            print(f"Unauthorized {err=}")
        else:
            print(f"Unexpected API Error: {err=}")
    
    def format_item(self, item, status = None, user_id = None) -> str:
        store_name = item['store']['store_name'].strip()
        store_name_text = f"🍽 {store_name}"
        store_address_line = f"🧭 {item['store']['store_location']['address']['address_line']}"
        store_items_available = item['items_available']
        store_items_available_text = f"🥡 {item['items_available']}"
        item_price_code = self.__format_price_code(item['item']['item_price']['code'])
        item_price = f"💰 {int(item['item']['price_including_taxes']['minor_units']) / 100} {item_price_code}"

        item_text = f"{store_name_text}\n{store_address_line}\n{item_price}\n{store_items_available_text}"

        if store_items_available > 0:
            store_pickup_start = self.__format_datetime(item['pickup_interval']['start'])
            store_pickup_end = self.__format_datetime(item['pickup_interval']['end'])
            store_pickup_text = f"⏰ {store_pickup_start} - {store_pickup_end}"
            item_text += '\n' + store_pickup_text
        
        if status:
            status = self.format_status(status)
            item_text += '\n' + status
            if user_id:
                item_id = item['item']['item_id']
                print(f"[{user_id}] {status} {store_items_available_text} 🍽  {store_name} ({item_id})")
        
        return item_text
    
    def __format_price_code(self, price_code: str) -> str:
        if price_code == 'EUR':
            return '€'
        if price_code == 'USD':
            return '$'
        return price_code

    def format_status(self, status: str) -> str:
        return TooGoodToGo.ITEM_STATUS[status]

    def get_available_items_per_user(self):
        """Loop through all users and see if the number of their favorite bags has changed"""
        while True:
            try:
                changed_items_status = {}
                available_items_before = len(self.available_items_favorites)
                
                for user_id in self.users_login_data:
                    user_settings = self.users_settings_data[user_id]

                    # if any alert is enabled for this user
                    if any(setting == 1 for setting in user_settings.values()):
                        self.connect(user_id)
                        
                        favourite_items = self.get_favourite_items()

                        for item in favourite_items:
                            item_id = item['item']['item_id']
                            status = changed_items_status.get(item_id)

                            if status is None and item_id in self.available_items_favorites:
                                old_items_available = int(self.available_items_favorites[item_id]['items_available'])
                                new_items_available = int(item['items_available'])
                                if new_items_available == 0 and old_items_available > 0:  # Sold out (x -> 0)
                                    status = 'sold_out'
                                elif old_items_available == 0 and new_items_available > 0:  # New Bag available (0 -> x)
                                    status = 'new_stock'
                                elif new_items_available < old_items_available:  # Reduced stock available (x -> x-1)
                                    status = 'stock_reduced'
                                elif new_items_available > old_items_available:  # Increased stock available (x -> x+1)
                                    status = 'stock_increased'

                            if status:
                                changed_items_status[item_id] = status

                                if user_settings[status]:
                                    item_text = self.format_item(item, status, user_id)
                                    self.send_message_with_link(user_id, item_text, item_id)
                            
                            self.available_items_favorites[item_id] = item
                
                if changed_items_status or len(self.available_items_favorites) != available_items_before:
                    self.save_available_items_favorites_to_txt()
            
            except tgtg.exceptions.TgtgAPIError as err:
                self.log_api_error(err)

            except Exception as err:
                print(f"Unexpected {err=}, {type(err)=}")
            
            # wait until next check
            time.sleep(self.get_interval_seconds())
    
    def get_interval_seconds(self):
        low_hours = False
        now = datetime.now(self.timezone)
        current_hour = now.hour
        # e.g. 0 - 6
        if self.low_hours_start <= self.low_hours_end:
            low_hours = self.low_hours_start <= current_hour < self.low_hours_end
        # e.g. 23 - 6
        elif current_hour >= self.low_hours_start or current_hour < self.low_hours_end:
            low_hours = True
        if low_hours:
            next_hour = (current_hour + 1) % 24
            if next_hour >= self.low_hours_end:
                # adjust interval to the minimum required when low hours are ending
                remaining_minutes = 59 - now.minute
                remaining_seconds = 60 - now.second
                time_to_end_low_hours = remaining_minutes * 60 + remaining_seconds
                if time_to_end_low_hours < self.low_hours_interval_seconds:
                    return max(time_to_end_low_hours, self.interval_seconds)
            return self.low_hours_interval_seconds
        return self.interval_seconds
    
    def __format_datetime(self, datetime_str: str) -> str:
        return str(datetime.strptime(datetime_str, '%Y-%m-%dT%H:%M:%SZ').astimezone(self.timezone).strftime("%a %d.%m at %H:%M"))

def data_file(data_file_name: str, data_folder='data', extension='json') -> Path:
    data_path = Path(f'{data_folder}/{data_file_name}.{extension}')
    if not data_path.exists():
        data_path.parent.mkdir(exist_ok=True, parents=True)
        data_path.write_text('{}')
        print(f'Created {data_path}')
    return data_path
