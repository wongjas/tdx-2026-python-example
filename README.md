# Reaction Emails — Bolt for Python

A Slack app that adds a **Reaction Emails** message shortcut. When triggered on any message, it reads all emoji reactions, looks up each reactor's email address, and posts a summary back to the channel grouped by reaction.

If you are at TDX 2026, please do not use this README and use the provided instructions on through the minihacks website.

## What It Does

Right-click (or long-press) any message → **Message Shortcuts** → **Reaction Emails**.

The app posts a message to the channel in this format:

```
*Reaction emails:*

:thumbsup: @alice, @bob
`alice@example.com, bob@example.com`

:heart: @carol
`carol@example.com`
```

If there are no reactions on the message, it posts `"No reactions found on this message."` instead.

## Installation

#### Create a Slack App

1. Open [https://api.slack.com/apps/new](https://api.slack.com/apps/new) and choose "From an app manifest"
2. Choose the workspace you want to install the application to
3. Copy the contents of [manifest.json](./manifest.json) into the text box that says `*Paste your manifest code here*` (within the JSON tab) and click *Next*
4. Review the configuration and click *Create*
5. Click *Install to Workspace* and *Allow* on the screen that follows. You'll then be redirected to the App Configuration dashboard.

#### Environment Variables

Before you can run the app, you'll need two tokens set as environment variables.

1. Click **OAuth & Permissions** in the left hand menu, then copy the **Bot User OAuth Token**. Store this as `SLACK_BOT_TOKEN`.
2. Click **Basic Information**, scroll to **App-Level Tokens**, and create a token with the `connections:write` scope. Store this as `SLACK_APP_TOKEN`.

```zsh
cp .env.example .env
```

Edit `.env` with your tokens. The app loads this file automatically via `python-dotenv`.

#### Required Bot Scopes

| Scope | Purpose |
|---|---|
| `commands` | Register the message shortcut |
| `chat:write` | Post the reaction email summary |
| `users:read` | Look up user profiles |
| `users:read.email` | Read user email addresses |

### Setup Your Local Project

```zsh
# Change into this project directory
cd tdx-2026-template

# Set up your Python virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install the dependencies
pip install -r requirements.txt

# Start your local server
python3 app.py
```

The app runs over Socket Mode, so no public URL or ngrok tunnel is needed.

#### Linting

```zsh
# Check for linting issues
ruff check .

# Auto-format code
ruff format .
```

#### Testing

```zsh
pytest .
```

## Project Structure

### `manifest.json`

Defines the app's configuration: the `Reaction Emails` message shortcut (`reaction_emails_shortcut`), required OAuth scopes, and Socket Mode settings.

### `app.py`

Entry point. Initialises the Bolt app with `SLACK_BOT_TOKEN`, registers all listeners, and starts the Socket Mode handler with `SLACK_APP_TOKEN`.

### `listeners/shortcuts/reaction_emails.py`

Core logic for the shortcut:

1. Fetches all reactions on the target message via `reactions.get`
2. Looks up every unique reactor's profile via `users.info` (deduplicated across emoji)
3. Builds a message grouped by emoji — each section lists @-mentioned users and a copyable code block of their email addresses
4. Posts the result to the channel with `chat.postMessage`

### `tests/`

Unit tests covering the happy path, missing reactions, users without emails, failed user lookups, and deduplication behaviour.
