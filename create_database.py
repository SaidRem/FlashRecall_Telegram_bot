import os
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv
import logging
import copy

load_dotenv()

LOGGING = os.getenv("LOGGING")
LOGS_FILENAME = os.getenv("LOGS_FILENAME")
DBNAME = os.getenv("DBNAME")
USER = os.getenv("USER")
PASSWORD = os.getenv("PASSWORD")
HOST = os.getenv("HOST")
PORT = os.getenv("PORT")

if LOGGING:
    logger = logging.getLogger(__name__)
    logging.basicConfig(
        filename=LOGS_FILENAME,
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )


def create_database(dbname, conn_params):
    """Create a new PostgreSQL database if it does not exist."""
    try:
        conn = psycopg2.connect(**conn_params)
        conn.autocommit = True  # Enable autocommit - required to create a DB.
        with conn.cursor() as cur:
            cur.execute(
                sql.SQL("SELECT 1 FROM pg_database WHERE datname = {}").format(sql.Literal(dbname))
            )

            if not cur.fetchone():
                cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname)))
                logging.info(f"Databse '{dbname}' was created successfully.")
            else:
                logging.info(f"Database '{dbname}' already exists.")
    except psycopg2.Error as err:
        logging.error(f"Error creating database: {err}")
    finally:
        if conn:
            conn.close()


def create_telegram_db(dbname="FlashRecall_db", conn_params=None):
    """Function to create a database."""
    if conn_params is None:
        logging.error("Connection parameters not specified. Database not created.")
        return

    # Create database if not exists.
    create_database(dbname, conn_params)


class PostgreSQLDatabase:
    def __init__(self, dbname, user, password, host='localhost', port=5432):
        self.dbname = dbname
        self.user = user
        self.password = password
        self.host = host
        self.port = port
        self.connection = None

    def __del__(self):
        if self.connection:
            self.connection.close()
            logging.info(f"Closed connection to the database '{self.dbname}'")

    def connect(self):
        try:
            self.connection = psycopg2.connect(
                dbname=self.dbname,
                user=self.user,
                password=self.password,
                host=self.host,
                port=self.port
            )
        except psycopg2.Error as err:
            logging.error(f"Database connection error: {err}")

    def close(self):
        if self.connection:
            self.connection.close()
            self.connection = None

    def create_tables(self):
        """Create tables if they do not exist."""
        self._execute_query("""
                        CREATE TABLE IF NOT EXISTS users (
                                id SERIAL PRIMARY KEY,
                                telegram_id BIGINT UNIQUE NOT NULL,
                                username TEXT,
                                first_name TEXT,
                                last_name TEXT,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
        """)
        self._execute_query("""
                        CREATE TABLE IF NOT EXISTS words (
                                id SERIAL PRIMARY KEY,
                                english TEXT NOT NULL UNIQUE,
                                russian TEXT NOT NULL UNIQUE
                        );
        """)
        self._execute_query("""
                        CREATE TABLE IF NOT EXISTS user_favorites (
                                user_id INT REFERENCES users(id) ON DELETE CASCADE,
                                word_id INT REFERENCES words(id) ON DELETE CASCADE,
                                PRIMARY KEY (user_id, word_id)
                        );
        """)
        self._execute_query("""
                        CREATE TABLE IF NOT EXISTS user_hidden_words (
                                user_id INT REFERENCES users(id) ON DELETE CASCADE,
                                word_id INT REFERENCES words(id) ON DELETE CASCADE,
                                PRIMARY KEY (user_id, word_id)
                        );
        """)

    def _execute_query(self, query, params=None):
        if self.connection is None:
            self.connect()
        try:
            with self.connection.cursor() as cur:
                cur.execute(query, params or ())
                self.connection.commit()
        except psycopg2.Error as err:
            self.connection.rollback()
            logging.error(f"Error executing query: {err}")

    def _fetch_all(self, query, params=None):
        if self.connection is None:
            self.connect()
        try:
            with self.connection.cursor() as cur:
                cur.execute(query, params or ())
                return cur.fetchall()
        except psycopg2.Error as err:
            self.connection.rollback()
            logging.error(f"Error executing query: {err}")
            return None

    def _fetch_one(self, query, params=None):
        if self.connection is None:
            self.connect()
        try:
            with self.connection.cursor() as cur:
                cur.execute(query, params or ())
                return cur.fetchone()
        except psycopg2.Error as err:
            self.connection.rollback()
            logging.error(f"Error executing query: {err}")
            return None

    def add_user(self, telegram_id, username, first_name, last_name):
        query = sql.SQL("""
            INSERT INTO users (telegram_id, username, first_name, last_name)
            VALUES (%s, %s, %s, %s);
        """)
        self._execute_query(query, (telegram_id, username, first_name, last_name))

    def add_word(self, english, russian):
        query = sql.SQL("""
            INSERT INTO words (english, russian)
            VALUES (%s, %s);
        """)
        self._execute_query(query, (english, russian))


if __name__ == "__main__":
    conn_params = {
        "dbname": DBNAME,
        "user": USER,
        "password": PASSWORD,
        "host": HOST,
        "port": PORT
    }

    create_telegram_db(dbname="FlashRecall_db", conn_params=conn_params)

    conn_params_newdb = copy.deepcopy(conn_params)
    conn_params_newdb["dbname"] = "FlashRecall_db"
    db = PostgreSQLDatabase(**conn_params_newdb)
    db.connect()
    db.create_tables()

    words = [
        # Существительные (Nouns)
        ['table', 'стол'],
        ['computer', 'компьютер'],
        ['book', 'книга'],
        ['water', 'вода'],
        ['tree', 'дерево'],
        ['phone', 'телефон'],
        ['car', 'машина'],
        ['house', 'дом'],
        ['sun', 'солнце'],
        ['dog', 'собака'],

        # Прилагательные (Adjectives)
        ['big', 'большой'],
        ['small', 'маленький'],
        ['fast', 'быстрый'],
        ['slow', 'медленный'],
        ['beautiful', 'красивый'],
        ['ugly', 'уродливый'],
        ['smart', 'умный'],
        ['stupid', 'глупый'],
        ['hot', 'горячий'],
        ['cold', 'холодный'],

        # Глаголы (Verbs)
        ['run', 'бежать'],
        ['eat', 'есть'],
        ['sleep', 'спать'],
        ['read', 'читать'],
        ['write', 'писать'],
        ['speak', 'говорить'],
        ['listen', 'слушать'],
        ['learn', 'учить'],
        ['work', 'работать'],
        ['play', 'играть'],

        # Наречия (Adverbs)
        ['quickly', 'быстро'],
        ['slowly', 'медленно'],
        ['loudly', 'громко'],
        ['quietly', 'тихо'],
        ['well', 'хорошо']
    ]

    for eng, rus in words:
        db.add_word(eng, rus)
