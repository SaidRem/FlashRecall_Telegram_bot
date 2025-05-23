# English Learning Telegram Bot

This is a Telegram bot designed to help users learn English words through a simple quiz format. The bot offers a Russian word, and the user has to select the correct English translation from a set of options. Users can add new words, delete words (for themselves), and track their progress.

## Features

- **Word Quiz**: The bot shows a Russian word and presents 4 possible English translations. The user has to choose the correct translation.
- **Add Word**: Users can add new words to the bot's dictionary, which will only appear to the user who added them.
- **Delete Word**: Users can hide words from appearing in future quizzes.
- **Multilingual Support**: The bot currently supports Russian and English words.

## Prerequisites

Before running the bot, you need to:

- Have a working PostgreSQL database. You can create a database named `flashrecall_db` manually and create tables and fill them using scripts `sql_queries.sql` and `inserts.sql` OR run the script `create_database.py` with the variables `DBNAME` and `USER` pre-set in the `.env` to the `postgres` value.


   ![Scheme of DB](https://github.com/SaidRem/FlashRecall_Telegram_bot/blob/master/Scheme_of_database.png)

- Get your own [Telegram Bot API token](https://core.telegram.org/bots#botfather).
- Set up Python 3 and the necessary dependencies.

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/SaidRem/FlashRecall_Telegram_bot.git
   cd telegram-bot
   ```

2. Install the required Python packages:

   ```
   pip install -r requirements.txt
   ```

3. Set up your database connection in the `.env`

   ```
   API_TOKEN=your_telegram_bot_token
   ADMIN_ID=123456789

   # PostgreSQL config
   DBNAME=postgres
   USER=postgres
   TELDBNAME=flashrecall_db
   PASSWORD=your_db_password
   HOST=localhost
   PORT=5432

   # Logging (optional)
   LOGGING=True
   LOGS_FILENAME=bot.log

   ```
5. Create tables in your database for the telegram bot

   ```
   python create_database.py
   ```
4. Run the bot
   ```
   python main.py
   ```
