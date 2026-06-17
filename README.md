# aeon

`aeon` is a Telegram Mini App for the AI mentor "Marcus Aurelius": a dark premium interface with philosophical agents, a Memento Mori diary, goals, and a personal cabinet.

The app is designed as a personal cabinet for goals, Memento Mori notes, and AI mentor dialogues.

## Stack

- Frontend: HTML, CSS, vanilla JavaScript
- Telegram Mini App SDK: `https://telegram.org/js/telegram-web-app.js`
- Bot: Python 3, Telegram Bot HTTP API
- AI: Gemini API through a Python backend endpoint
- Storage: browser `localStorage` for Mini App state, local JSON files for bot registration data
- Local HTTPS testing: `ngrok` proxy for port `5173`
- Repository: `https://github.com/caaahaaaaa/aeon.git`

## Features

- Home page with three AI agents:
  - Marcus Aurelius: personal wise mentor and psychologist
  - Machiavelli: coach and tactical business trainer
  - Carl Jung: shadow-focused psychoanalyst
- Gemini-powered Marcus Aurelius:
  - Mini App sends questions to `/api/agent/aurelius`
  - Python backend calls Gemini with `GEMINI_API_KEY`
  - the key is never stored in frontend files
- Agent dialogues inside Telegram bot:
  - user can choose an agent in the Mini App and press "Start dialogue"
  - Mini App sends Telegram `initData` to `/api/start-agent-dialog`
  - backend validates `initData`, activates the chosen agent, and opens the bot chat with `openTelegramLink`
  - `/agents` opens agent selection
  - `/app` or `/menu` opens dialogue controls
  - after choosing Marcus Aurelius, Machiavelli, or Carl Jung, normal Telegram messages go to that agent
  - each agent keeps a small separate dialogue history
  - `/stop` closes the active agent mode
  - agent replies are sent as clean chat messages without inline buttons after every answer
- Memento Mori diary:
  - 90 years displayed as 4,680 life weeks
  - birth date from bot registration or manual input
  - weeks lived, weeks left, and life progress percentage
  - daily reflection notes
  - goal setting for the current life period
- Goal reminders:
  - Mini App sends active goals to the bot through `Telegram.WebApp.sendData()`
  - bot reminds the user every day until the goal is closed
- Personal cabinet:
  - profile settings
  - user memory card
  - profile completion progress
  - subscription block
- Bot registration flow:
  - compact one-message onboarding: button steps edit the same Telegram message instead of flooding the chat
  - language selection
  - Marcus Aurelius welcome message
  - name
  - staged birth date picker for the Memento Mori calendar: period -> year -> month -> day, all inside one edited Telegram message
  - age is calculated automatically from the selected birth date
  - country list
  - Mini App launch URL with `lang`, `name`, `age`, `birthDate`, `country`, and `view=profile`
  - personal cabinet opens already filled, and Memento Mori calendar receives the birth date

## Project Notes

- Remote push authorization is configured on this computer.
- Local Telegram Mini App testing uses `ngrok` proxying port `5173`.
- Local app URL before proxy: `http://127.0.0.1:5173/`
- Public ngrok URL should be used as `WEBAPP_URL` during local Telegram testing.

## Local Mini App Run

```powershell
cd C:\Users\diaaa\Documents\Codex\2026-05-18\new-chat
$env:GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
$env:WEB_PORT="5173"
C:\Users\diaaa\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe bot.py
```

Open locally:

```text
http://127.0.0.1:5173/
```

For Telegram testing, start ngrok on the same port:

```powershell
ngrok http 5173
```

Then use the generated HTTPS ngrok URL as `WEBAPP_URL`.

Note: `python -m http.server` can serve the static interface, but Marcus Aurelius Gemini answers require `bot.py`, because `/api/agent/aurelius` lives in the Python backend.

## Bot Run

```powershell
$env:TELEGRAM_BOT_TOKEN="YOUR_TOKEN"
$env:BOT_USERNAME="YOUR_BOT_USERNAME"
$env:WEBAPP_URL="https://your-public-mini-app-url"
$env:REMINDER_HOUR="9"
$env:GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
C:\Users\diaaa\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe bot.py
```

Environment variables:

- `TELEGRAM_BOT_TOKEN`: Telegram bot token from BotFather
- `BOT_USERNAME`: bot username without `@`; optional, backend can resolve it through `getMe`
- `WEBAPP_URL`: public HTTPS URL for the Mini App
- `REMINDER_HOUR`: daily reminder hour, default is `9`
- `GEMINI_API_KEY`: Gemini API key for Marcus Aurelius answers
- `GEMINI_MODEL`: Gemini model name, default is `gemini-3.5-flash`
- `GEMINI_MAX_OUTPUT_TOKENS`: max Gemini answer tokens, default is `2400`
- `WEB_PORT`: local backend/static server port, default is `5173`

## Gemini Diagnostics

Check Gemini API separately from the bot:

```powershell
$env:GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
C:\Users\diaaa\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe check_gemini.py
```

The script prints the HTTP status and Gemini error body without printing the API key.

## Git

Remote:

```text
origin https://github.com/caaahaaaaa/aeon.git
```

Push:

```powershell
git push -u origin main
```
