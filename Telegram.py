import re
import configparser
import asyncio
from _thread import start_new_thread

from telebot import types
from telebot.async_telebot import AsyncTeleBot

from TooGoodToGo import TooGoodToGo

import tgtg.exceptions

config = configparser.ConfigParser(interpolation=None)
config.read('config.ini')
token = config['Telegram']['token']
bot = AsyncTeleBot(token)
tooGoodToGo = TooGoodToGo(token, config['Configuration'])

def log_command(chat_id: int, command: str, log: str = ''):
    print(f"[{chat_id}] /{command}{f': {log}' if log else ''}")

# Handle '/start' and '/help'
@bot.message_handler(commands=['help', 'start'])
async def send_welcome(message):
    chat_id = str(message.chat.id)
    log_command(chat_id, 'help')
    await bot.send_message(chat_id,
                           """
*Hi welcome to the TGTG Bot:*

The bot will notify you as soon as new bags from your favorites are available.

*❗️️This is necessary if you want to use the bot❗️*
🔑 To login into your TooGoodToGo account enter 
*/login email@example.com*
_You will then receive an email with a confirmation link.
You do not need to enter a password._

⚙️ With */settings* you can set when you want to be notified. 

ℹ️ With */info* you can display all stores from your favorites where bags are currently available.

_🌐 You can find more information about Too Good To Go_ [here](https://www.toogoodtogo.com/).

*🌍 LET'S FIGHT food waste TOGETHER 🌎*
""", parse_mode="Markdown")


@bot.message_handler(commands=['info'])
async def send_info(message):
    chat_id = str(message.chat.id)
    log_command(chat_id, 'info')
    credentials = tooGoodToGo.find_credentials_by_telegramUserID(chat_id)
    if credentials is None:
        await bot.send_message(chat_id=chat_id,
                               text="🔑 You have to log in with your mail first!\nPlease enter */login email@example.com*\n*❗️️This is necessary if you want to use the bot❗️*",
                               parse_mode="Markdown")
        return None
    tooGoodToGo.send_available_favourite_items_for_one_user(chat_id)


@bot.message_handler(commands=['login'])
async def send_login(message):
    chat_id = str(message.chat.id)

    try:
        if tooGoodToGo.update_credentials(chat_id, refresh=True):
            log_command(chat_id, 'login', 'Logged in')
            await bot.send_message(chat_id=chat_id, text="👍 You are logged in!")
            return None
    except tgtg.exceptions.TgtgAPIError as err:
        tooGoodToGo.handle_api_error(err, chat_id)
        bot.send_message(chat_id, "❌ Cannot log in. Please try again later.")
        return None
        
    email = message.text.replace('/login', '').strip()

    if re.match(r"[^@]+@[^@]+\.[^@]+", email):
        log_command(chat_id, 'login', email)
        telegram_username = message.from_user.username
        start_new_thread(tooGoodToGo.new_user, (chat_id, telegram_username, email))
    else:
        log_command(chat_id, 'login', f'{email} (Invalid)')
        await bot.send_message(chat_id=chat_id,
                               text="*⚠️ No valid mail address ⚠️*"
                                    "\nPlease enter */login email@example.com*"
                                    "\n_You will then receive an email with a confirmation link."
                                    "\nYou do not need to enter a password._",
                               parse_mode="Markdown")


def inline_keyboard_markup(chat_id):
    inline_keyboard = types.InlineKeyboardMarkup(
        keyboard=[
            [
                types.InlineKeyboardButton(
                    text=('🟢' if tooGoodToGo.users_settings_data[chat_id]['sold_out'] else '🔴') + ' ' + tooGoodToGo.format_status('sold_out'),
                    callback_data='sold_out'
                ),
                types.InlineKeyboardButton(
                    text=('🟢' if tooGoodToGo.users_settings_data[chat_id]['new_stock'] else '🔴') + ' ' + tooGoodToGo.format_status('new_stock'),
                    callback_data='new_stock'
                )
            ],
            [
                types.InlineKeyboardButton(
                    text=("🟢" if tooGoodToGo.users_settings_data[chat_id]['stock_reduced'] else '🔴') + ' ' + tooGoodToGo.format_status('stock_reduced'),
                    callback_data='stock_reduced'
                ),
                types.InlineKeyboardButton(
                    text=("🟢" if tooGoodToGo.users_settings_data[chat_id]['stock_increased'] else '🔴') + ' ' + tooGoodToGo.format_status('stock_increased'),
                    callback_data='stock_increased'
                )
            ],
            [
                types.InlineKeyboardButton(
                    text='✅ Activate all ✅',
                    callback_data='activate_all'
                )
            ],

            [
                types.InlineKeyboardButton(
                    text='❌ Disable all ❌',
                    callback_data='disable_all'
                )
            ]
        ])
    return inline_keyboard


@bot.message_handler(commands=['settings'])
async def send_settings(message):
    chat_id = str(message.chat.id)
    log_command(chat_id, 'settings')
    credentials = tooGoodToGo.find_credentials_by_telegramUserID(chat_id)
    if credentials is None:
        await bot.send_message(chat_id=chat_id,
                               text="🔑 You have to log in with your mail first!\nPlease enter */login email@example.com*\n*❗️️This is necessary if you want to use the bot❗️*",
                               parse_mode="Markdown")
        return None

    await bot.send_message(chat_id, "🟢 = enabled | 🔴 = disabled  \n*Activate alert if:*", parse_mode="markdown",
                           reply_markup=inline_keyboard_markup(chat_id))


@bot.callback_query_handler(func=lambda c: c.data == 'sold_out')
async def back_callback(call: types.CallbackQuery):
    chat_id = str(call.message.chat.id)
    settings = tooGoodToGo.users_settings_data[chat_id]["sold_out"]
    tooGoodToGo.users_settings_data[chat_id]["sold_out"] = 0 if settings else 1
    await bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                        reply_markup=inline_keyboard_markup(chat_id))
    tooGoodToGo.save_users_settings_data_to_txt()


@bot.callback_query_handler(func=lambda c: c.data == 'new_stock')
async def back_callback(call: types.CallbackQuery):
    chat_id = str(call.message.chat.id)
    settings = tooGoodToGo.users_settings_data[chat_id]["new_stock"]
    tooGoodToGo.users_settings_data[chat_id]["new_stock"] = 0 if settings else 1
    await bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                        reply_markup=inline_keyboard_markup(chat_id))
    tooGoodToGo.save_users_settings_data_to_txt()


@bot.callback_query_handler(func=lambda c: c.data == 'stock_reduced')
async def back_callback(call: types.CallbackQuery):
    chat_id = str(call.message.chat.id)
    settings = tooGoodToGo.users_settings_data[chat_id]["stock_reduced"]
    tooGoodToGo.users_settings_data[chat_id]["stock_reduced"] = 0 if settings else 1
    await bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                        reply_markup=inline_keyboard_markup(chat_id))
    tooGoodToGo.save_users_settings_data_to_txt()


@bot.callback_query_handler(func=lambda c: c.data == 'stock_increased')
async def back_callback(call: types.CallbackQuery):
    chat_id = str(call.message.chat.id)
    settings = tooGoodToGo.users_settings_data[chat_id]["stock_increased"]
    tooGoodToGo.users_settings_data[chat_id]["stock_increased"] = 0 if settings else 1
    await bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                        reply_markup=inline_keyboard_markup(chat_id))
    tooGoodToGo.save_users_settings_data_to_txt()


@bot.callback_query_handler(func=lambda c: c.data == 'activate_all')
async def back_callback(call: types.CallbackQuery):
    chat_id = str(call.message.chat.id)
    for key in tooGoodToGo.users_settings_data[chat_id].keys():
        tooGoodToGo.users_settings_data[chat_id][key] = 1
    tooGoodToGo.save_users_settings_data_to_txt()
    await bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                        reply_markup=inline_keyboard_markup(chat_id))


@bot.callback_query_handler(func=lambda c: c.data == 'disable_all')
async def back_callback(call: types.CallbackQuery):
    chat_id = str(call.message.chat.id)
    for key in tooGoodToGo.users_settings_data[chat_id].keys():
        tooGoodToGo.users_settings_data[chat_id][key] = 0
    tooGoodToGo.save_users_settings_data_to_txt()
    await bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                        reply_markup=inline_keyboard_markup(chat_id))

print('TooGoodToGo bot started')

asyncio.run(bot.polling())
