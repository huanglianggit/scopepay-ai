import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / '.env')


@dataclass
class Settings:
    db_path: str = os.getenv('SCOPEPAY_DB') or str(ROOT / 'data' / 'scopepay.sqlite3')
    public_url: str = os.getenv('PUBLIC_BASE_URL', 'http://127.0.0.1:8791').rstrip('/')
    paypal_id: str = os.getenv('PAYPAL_CLIENT_ID', '')
    paypal_secret: str = os.getenv('PAYPAL_CLIENT_SECRET', '')
    webhook_id: str = os.getenv('PAYPAL_WEBHOOK_ID', '')
    ai_provider: str = os.getenv('AI_PROVIDER', 'demo')
    ai_url: str = os.getenv('AI_BASE_URL', 'http://127.0.0.1:11434/v1').rstrip('/')
    ai_model: str = os.getenv('AI_MODEL', '')
    ai_key: str = os.getenv('AI_API_KEY', '')
    owner_code: str = os.getenv('OWNER_ACCESS_CODE', '')

    @property
    def paypal_ready(self):
        return bool(self.paypal_id and self.paypal_secret)

    @property
    def ai_ready(self):
        return self.ai_provider in ('openai', 'ollama') and bool(self.ai_model)
