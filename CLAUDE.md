# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Telegram bot for Tehran Linux User Group (TehLUG) that enables users to register and ask questions to event presenters. Admins can view and filter questions by presenter or user.

## Development Setup

Python version: >=3.10

Install dependencies:
```bash
pip install -r requirements.txt
# or
uv pip install -e .
```

Set environment variables:
```bash
export BOT_TOKEN='your_bot_token_from_botfather'
export FIRST_ADMIN_ID='your_telegram_id'  # Optional, for initial admin setup
```

## Running the Application

```bash
python main.py
```

## Architecture

### Core Components

- **main.py**: Entry point that initializes the bot with the token and sets up handlers
- **bot.py**: Contains all Telegram bot handlers using ConversationHandler for multi-step flows
- **database.py**: SQLite database interface with methods for users, questions, and presenters

### Conversation Flows

1. **Registration Flow** (REGISTRATION_NAME → REGISTRATION_EMAIL)
   - Triggered by `/start` for new users
   - Collects name and email, stores in users table
   - Automatically grants admin if telegram_id matches FIRST_ADMIN_ID env var

2. **Question Flow** (SELECT_PRESENTER → ASK_QUESTION)
   - User selects presenter from keyboard
   - Submits question which is stored with user info

3. **Admin Filters** (ADMIN_FILTER_PRESENTER / ADMIN_FILTER_USER)
   - Separate conversations for filtering questions
   - Return filtered results from database queries

4. **Admin User Management** (ADMIN_SELECT_USER)
   - Promote users to admin or demote admins to regular users
   - Shows list of users and accepts telegram_id for promotion/demotion

### Database Schema

- **users**: telegram_id (PK), name, email, is_admin (INTEGER 0/1), registered_at
- **questions**: id (PK), telegram_id (FK), user_name, presenter_name, question, created_at
- **presenters**: id (PK), name (UNIQUE)

### Admin Access

Admin privileges are stored in the database `users.is_admin` field. The `is_admin()` function in bot.py checks this field via `db.is_admin(telegram_id)`. Admin methods in database.py:
- `is_admin(telegram_id)`: Check if user is admin
- `set_admin(telegram_id, is_admin)`: Promote/demote user
- `get_all_users()`: List all users with admin status
