# AZ-900 Tutor Bot — Setup

## 1. Install dependencies
```bash
cd az900-tutor-bot
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Configure environment
```bash
cp .env.example .env
# Fill in TELEGRAM_TOKEN and ANTHROPIC_API_KEY
```

- **TELEGRAM_TOKEN** — from [@BotFather](https://t.me/BotFather) → `/newbot`
- **ANTHROPIC_API_KEY** — from [console.anthropic.com](https://console.anthropic.com)

## 3. Add the PDF
Download the official AZ-900 study guide from Microsoft Learn and save it as:
```
data/az900_guide.pdf
```
URL: https://learn.microsoft.com/en-us/credentials/certifications/resources/study-guides/az-900

## 4. Build the vector store (one-time)
```bash
python -m core.ingest
```

## 5. Run the bot
```bash
python run.py
```

## File structure
```
az900-tutor-bot/
├── bot/
│   ├── main.py          # Telegram handlers + app bootstrap
│   ├── conversation.py  # User state machine
│   └── commands.py      # /start, /progress, /readiness, /reset, /help
├── core/
│   ├── ingest.py        # PDF → ChromaDB pipeline
│   ├── retriever.py     # Fetch chunks by domain/query
│   ├── tutor.py         # Question generation + Socratic evaluation
│   └── scorer.py        # Readiness score calculator
├── db/
│   ├── database.py      # SQLite connection + init
│   └── models.py        # Data access layer
├── data/                # az900_guide.pdf + chroma_db/ + tutor.db
├── run.py
├── requirements.txt
└── .env
```

## Cost estimate
- Model: `claude-haiku-4-5` (~$0.001/session)
- A full 10-question session costs less than $0.01
