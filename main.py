import os
from dotenv import load_dotenv
import random
import psycopg2
import logging
from telebot import types, TeleBot, custom_filters
from telebot.storage import StateMemoryStorage
from telebot.handler_backends import State, StatesGroup

load_dotenv()

TELDBNAME = os.getenv("TELDBNAME")
USER = os.getenv("USER")
PASSWORD = os.getenv("PASSWORD")
HOST = os.getenv("HOST")
PORT = os.getenv("PORT")

API_TOKEN = os.getenv("API_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
LOGS_FILENAME = os.getenv("LOGS_FILENAME")


logger = logging.getLogger(__name__)
logging.basicConfig(
    filename=LOGS_FILENAME,
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
                WHERE uhw.word_id = w.id AND uhw.telegram_id = %s
            )
            AND (w.added_by IS NULL OR w.added_by = %s)
            ORDER BY RANDOM() LIMIT 1;
        """, (telegram_id, telegram_id))
        return cur.fetchone()


def fetch_random_options(telegram_id):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT w.english, w.russian
            FROM words w
            LEFT JOIN user_hidden_words h ON w.id = h.word_id
                    AND h.telegram_id = %s
            WHERE h.word_id IS NULL
              AND (w.added_by IS NULL OR w.added_by = %s)
            ORDER BY RANDOM()
            LIMIT 4;
        """, (telegram_id, telegram_id))
        result = [(row[0], row[1]) for row in cur.fetchall()]
        logger.info(result)
        return result


@bot.message_handler(commands=['start'])
def start(message):
    user = message.from_user
    logger.info(f"{user.id = }, {user.username = }")
    ensure_user_exists(user.id, user.username, user.first_name, user.last_name)
    text = """Привет! Давай учить английские слова!
    Hello! Let's learn english words!"""
    bot.send_message(message.chat.id, text)
    create_cards(message)


@bot.message_handler(commands=['cards'])
def create_cards(message):
    telegram_id = message.from_user.id

    options = fetch_random_options(telegram_id)
    if options:
        # random.shuffle(options)
        target_word, translate = random.choice(options)

        # Save before send
        bot.set_state(telegram_id, MyStates.target_word, message.chat.id)
        with bot.retrieve_data(telegram_id, message.chat.id) as data:
            data['target_word'] = target_word
            data['translate_word'] = translate

        markup = types.ReplyKeyboardMarkup(row_width=2)
        buttons = [types.KeyboardButton(option[0]) for option in options]
        buttons.extend([types.KeyboardButton(Command.NEXT),
                        types.KeyboardButton(Command.ADD_WORD),
                        types.KeyboardButton(Command.DELETE_WORD)])
        markup.add(*buttons)

        # Send only after recording the data
        bot.send_message(message.chat.id,
                         f"Выбери перевод слова:\n🇷🇺 {translate}",
                         reply_markup=markup)
    else:
        bot.set_state(telegram_id, MyStates.target_word, message.chat.id)

        markup = types.ReplyKeyboardMarkup(row_width=2)
        buttons = [types.KeyboardButton(Command.NEXT),
                   types.KeyboardButton(Command.ADD_WORD),
                   types.KeyboardButton(Command.DELETE_WORD)]
        markup.add(*buttons)

        # Send only after recording the data
        bot.send_message(message.chat.id,
                         f"Добавь слова в свой справочник",
                         reply_markup=markup)


@bot.message_handler(func=lambda message: message.text == Command.NEXT)
def next_cards(message):
    create_cards(message)


@bot.message_handler(func=lambda message: message.text == Command.DELETE_WORD)
def delete_word(message):
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        telegram_id = message.from_user.id
        word = data.get('target_word')
        if word:
            with get_connection() as conn, conn.cursor() as cur:
                # Get the word and ownership
                cur.execute("""
                    SELECT id, added_by FROM words
                    WHERE english = %s
                """, (word,))
                result = cur.fetchone()

                if not result:
                    logger.info(f"Word '{word}' not found.")
                else:
                    word_id, added_by = result
                    if added_by == telegram_id:
                        # User added it: delete the word from db
                        cur.execute(
                            "DELETE FROM words WHERE id = %s", (word_id,)
                            )
                    else:
                        # Global word: hide it for the user
                        cur.execute("""
                            INSERT INTO user_hidden_words (telegram_id, word_id)
                            VALUES (%s, %s)
                            ON CONFLICT DO NOTHING
                        """, (telegram_id, word_id))
            bot.send_message(message.chat.id, 
                             f"Слово '{word}' удалено для вас!")
    create_cards(message)


@bot.message_handler(func=lambda message: message.text == Command.ADD_WORD)
def add_word(message):
    bot.send_message(message.chat.id,
                     "Введите новое слово (английское и русское через тире):"
                     )
    bot.register_next_step_handler(message, save_word)


def save_word(message):
    telegram_id = message.from_user.id
    try:
        english, russian = message.text.split('-')
        english, russian = english.strip(), russian.strip()
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("""
                INSERT INTO words (english, russian, added_by)
                VALUES (%s, %s, %s) ON CONFLICT DO NOTHING RETURNING id;
            """, (english, russian, telegram_id))
            word_id = cur.fetchone()
            logger.info(f"save_word: {english = } {russian = } {telegram_id = }")
            logger.info(f"{word_id = }")
            if word_id:
                bot.send_message(
                    message.chat.id,
                    "Слово добавлено!\nThe word added!"
                )
            else:
                # Word exists, check if it's hidden for this user
                cur.execute("""
                    SELECT id FROM words WHERE english = %s;
                """, (english,))
                existing_row = cur.fetchone()

                if existing_row:
                    word_id = existing_row[0]

                    # Check if this user has hidden the word
                    cur.execute("""
                        SELECT 1 FROM user_hidden_words
                        WHERE telegram_id = %s AND word_id = %s;
                    """, (telegram_id, word_id))
                    is_hidden = cur.fetchone()

                    if is_hidden:
                        # Unhide the word for this user
                        cur.execute("""
                            DELETE FROM user_hidden_words
                            WHERE telegram_id = %s AND word_id = %s;
                        """, (telegram_id, word_id))

                        bot.send_message(
                            message.chat.id,
                            "Слово добавлено.\n"
                            "The word was restored from hidden."
                        )
                    else:
                        # Word exists and is visible - no need to re-add
                        bot.send_message(
                            message.chat.id,
                            "Слово уже существует!\nThe word already exists!"
                        )
                else:
                    bot.send_message(
                        message.chat.id,
                        "Ошибка при сохранении слова.\n"
                        "An error uccured while saving the word."
                    )
    except ValueError:
        bot.send_message(message.chat.id,
                         "Неправильный формат! Введите как 'apple - яблоко'"
                         )


@bot.message_handler(func=lambda message: True, content_types=['text'])
def message_reply(message):
    text = message.text
    telegram_id = message.from_user.id
    with bot.retrieve_data(telegram_id, message.chat.id) as data:
        target_word = data.get('target_word')
        translate_word = data.get('translate_word')

        if target_word is None or translate_word is None:
            bot.send_message(
                message.chat.id,
                "Нажмите /cards или Дальше для нового слова."
            )
            return

        if text == target_word:
            info_msg1 = f"Отлично!❤ {target_word} -> {translate_word}"
            bot.delete_state(telegram_id, message.chat.id)  # Clearing the state

            markup = types.ReplyKeyboardMarkup(row_width=2)
            buttons = [types.KeyboardButton(Command.NEXT),
                       types.KeyboardButton(Command.ADD_WORD),
                       types.KeyboardButton(Command.DELETE_WORD)]
            markup.add(*buttons)
            bot.send_message(message.chat.id, info_msg1, reply_markup=markup)

        else:
            bot.send_message(
                message.chat.id,
                f"Ошибка! Попробуй снова перевести 🇷🇺 {translate_word}"
            )


bot.add_custom_filter(custom_filters.StateFilter(bot))
bot.infinity_polling(skip_pending=True)
