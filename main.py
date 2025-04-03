import os
import random
import psycopg2
import logging
from telebot import types, TeleBot, custom_filters
from telebot.storage import StateMemoryStorage
from telebot.handler_backends import State, StatesGroup

TELDBNAME = os.getenv("TELDBNAME")
USER = os.getenv("USER")
PASSWORD = os.getenv("PASSWORD")
HOST = os.getenv("HOST")
PORT = os.getenv("PORT")

API_TOKEN = os.getenv("API_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
LOGS_FILENAME = os.getenv("LOGS_FILENAME")


logger = logging.getLogger(__name__)
logging.basicConfig(filename=LOGS_FILENAME,
                    level=logging.INFO,
                    format="%(message)s | %(levelname)s | %(asctime)s"
                    )

logger.info('Start telegram bot...')
logger.info(f"{TELDBNAME = }")

state_storage = StateMemoryStorage()
bot = TeleBot(API_TOKEN, state_storage=state_storage)

DB_CONFIG = {
    'dbname': TELDBNAME,
    'user': USER,
    'password': PASSWORD,
    'host': HOST,
    'port': PORT
}


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def ensure_user_exists(telegram_id, username, first_name, last_name):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("""
            INSERT INTO users (telegram_id, username, first_name, last_name)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (telegram_id) DO NOTHING;
        """, (telegram_id, username, first_name, last_name))


class Command:
    ADD_WORD = 'Добавить слово ➕'
    DELETE_WORD = 'Удалить слово 🔙'
    NEXT = 'Дальше ⏭'


class MyStates(StatesGroup):
    target_word = State()
    translate_word = State()


def fetch_random_word(telegram_id):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT w.english, w.russian 
            FROM words w 
            WHERE NOT EXISTS (
                SELECT 1 FROM user_hidden_words uhw 
                WHERE uhw.word_id = w.id AND uhw.user_id = (SELECT id FROM users WHERE telegram_id = %s)
            )
            ORDER BY RANDOM() LIMIT 1;
        """, (telegram_id,))
        return cur.fetchone()


def fetch_random_options(correct_word):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT english FROM words WHERE english != %s ORDER BY RANDOM() LIMIT 3;
        """, (correct_word,))
        return [row[0] for row in cur.fetchall()]


@bot.message_handler(commands=['start'])
def start(message):
    user = message.from_user
    logger.info(f"{user.id = }, {user.username = }")
    ensure_user_exists(user.id, user.username, user.first_name, user.last_name)
    bot.send_message(message.chat.id, "Привет! Давай учить английские слова!")
    create_cards(message)


@bot.message_handler(commands=['cards'])
def create_cards(message):
    telegram_id = message.from_user.id
    word = fetch_random_word(telegram_id)
    if not word:
        bot.send_message(message.chat.id, "Нет доступных слов!")
        return

    target_word, translate = word
    options = fetch_random_options(target_word) + [target_word]
    random.shuffle(options)

    # Save before send
    bot.set_state(telegram_id, MyStates.target_word, message.chat.id)
    with bot.retrieve_data(telegram_id, message.chat.id) as data:
        data['target_word'] = target_word
        data['translate_word'] = translate

    markup = types.ReplyKeyboardMarkup(row_width=2)
    buttons = [types.KeyboardButton(option) for option in options]
    buttons.extend([types.KeyboardButton(Command.NEXT),
                    types.KeyboardButton(Command.ADD_WORD),
                    types.KeyboardButton(Command.DELETE_WORD)])
    markup.add(*buttons)

    # Send only after recording the data
    bot.send_message(message.chat.id, f"Выбери перевод слова:\n🇷🇺 {translate}", reply_markup=markup)


@bot.message_handler(func=lambda message: message.text == Command.NEXT)
def next_cards(message):
    create_cards(message)


@bot.message_handler(func=lambda message: message.text == Command.DELETE_WORD)
def delete_word(message):
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        word = data.get('target_word')
        if word:
            with get_connection() as conn, conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO user_hidden_words (user_id, word_id)
                    SELECT id, (SELECT id FROM words WHERE english = %s) FROM users WHERE telegram_id = %s;
                """, (word, message.from_user.id))
            bot.send_message(message.chat.id, f"Слово '{word}' скрыто для вас!")
    create_cards(message)


@bot.message_handler(func=lambda message: message.text == Command.ADD_WORD)
def add_word(message):
    bot.send_message(message.chat.id, "Введите новое слово (английское и русское через тире):")
    bot.register_next_step_handler(message, save_word)


def save_word(message):
    try:
        english, russian = message.text.split('-')
        english, russian = english.strip(), russian.strip()
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("""
                INSERT INTO words (english, russian) VALUES (%s, %s) ON CONFLICT DO NOTHING RETURNING id;
            """, (english, russian))
            word_id = cur.fetchone()
            if word_id:
                cur.execute("""
                    INSERT INTO user_favorites (user_id, word_id) 
                    SELECT id, %s FROM users WHERE telegram_id = %s;
                """, (word_id[0], message.from_user.id))
                bot.send_message(message.chat.id, "Слово добавлено!")
            else:
                bot.send_message(message.chat.id, "Слово уже существует!")
    except ValueError:
        bot.send_message(message.chat.id, "Неправильный формат! Введите как 'apple - яблоко'")


@bot.message_handler(func=lambda message: True, content_types=['text'])
def message_reply(message):
    text = message.text
    telegram_id = message.from_user.id
    with bot.retrieve_data(telegram_id, message.chat.id) as data:
        target_word = data.get('target_word')
        translate_word = data.get('translate_word')

        if target_word is None or translate_word is None:
            bot.send_message(message.chat.id, "Что-то пошло не так. Нажмите /cards для новой карточки.")
            return

        if text == target_word:
            bot.send_message(message.chat.id, f"Отлично!❤ {target_word} -> {translate_word}\n\n⏭ Нажми «{Command.NEXT}» для следующего слова")
            bot.delete_state(telegram_id, message.chat.id)  # Clearing the state
        else:
            bot.send_message(message.chat.id, f"Ошибка! Попробуй снова перевести 🇷🇺 {translate_word}")


bot.add_custom_filter(custom_filters.StateFilter(bot))
bot.infinity_polling(skip_pending=True)
