CREATE TABLE users (
    telegram_id BIGINT PRIMARY KEY
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE words (
    id SERIAL PRIMARY KEY,
    english TEXT NOT NULL UNIQUE,
    russian TEXT NOT NULL UNIQUE,
    added_by BIGINT REFERENCES users(telegram_id) ON DELETE CASCADE
);

CREATE TABLE user_hidden_words (
    telegram_id BIGINT REFERENCES users(telegram_id) ON DELETE CASCADE,
    word_id INTEGER REFERENCES words(id) ON DELETE CASCADE,
    PRIMARY KEY (telegram_id, word_id)
);
