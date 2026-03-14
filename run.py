"""
Entry points:
  Telegram bot (paused):  python run.py --bot
  Web API:                python run.py          (default)
"""
import sys
from dotenv import load_dotenv

load_dotenv()

if __name__ == "__main__":
    if "--bot" in sys.argv:
        # Telegram bot — kept for reference, not the active product
        from bot.main import main
        main()
    else:
        import uvicorn
        uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
