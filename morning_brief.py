import os
import requests
import yfinance as yf
from anthropic import Anthropic
from twilio.rest import Client
from datetime import datetime
import pytz

anthropic = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
twilio = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])

NEWS_API_KEY   = os.environ["NEWS_API_KEY"]
WHATSAPP_TO    = os.environ["WHATSAPP_TO"]
WHATSAPP_FROM  = os.environ["WHATSAPP_FROM"]

SP = pytz.timezone("America/Sao_Paulo")

def fetch_news():
    base = "https://newsapi.org/v2/top-headlines"
    headers = {"X-Api-Key": NEWS_API_KEY}
    mundo = requests.get(base, headers=headers, params={
        "category": "business", "language": "en", "pageSize": 10,
    }).json().get("articles", [])
    brasil = requests.get(base, headers=headers, params={
        "sources": "google-news-br",
        "q": "economia OR mercado OR Selic OR Lula OR Banco Central",
        "language": "pt", "pageSize": 5,
    }).json().get("articles", [])
    def fmt(articles):
        return "\n".join(f"- {a['title']} ({a.get('source', {}).get('name', '')})" for a in articles if a.get("title"))
    return fmt(mundo), fmt(brasil)

def fetch_indices():
    tickers = {
        "S&P 500": "^GSPC", "Nasdaq": "^IXIC", "Dow Jones": "^DJI",
        "Ibovespa": "^BVSP", "DXY": "DX-Y.NYB", "Bitcoin": "BTC-USD",
        "Petróleo": "CL=F", "Ouro": "GC=F",
    }
    lines = []
    for name, ticker in tickers.items():
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="2d")
            if len(hist) >= 2:
                prev = hist["Close"].iloc[-2]
                last = hist["Close"].iloc[-1]
                chg  = ((last - prev) / prev) * 100
                arrow = "▲" if chg >= 0 else "▼"
                lines.append(f"{name}: {last:,.2f} {arrow} {abs(chg):.2f}%")
            else:
                lines.append(f"{name}: dados indisponíveis")
        except Exception:
            lines.append(f"{name}: dados indisponíveis")
    return "\n".join(lines)

def curate(noticias_mundo, noticias_brasil, indices):
    hoje = datetime.now(SP).strftime("%d/%m/%Y")
    prompt = f"""Você é um curador financeiro sênior. Com base nas headlines abaixo, escreva um morning brief econômico para {hoje} em português brasileiro, no seguinte formato EXATO:

📰 *Mundo*
[2-3 parágrafos curtos e densos sobre o que está movendo os mercados globais. Tom analítico, estilo Bloomberg/FT. Sem bullet points.]

📊 *Mercados*
{indices}

🇧🇷 *Brasil*
[1 parágrafo sobre o cenário econômico brasileiro.]

---
HEADLINES MUNDO:
{noticias_mundo}

HEADLINES BRASIL:
{noticias_brasil}

IMPORTANTE: Escreva diretamente o brief. Sem introdução, sem comentários extras. Mantenha os índices EXATAMENTE como fornecidos acima."""

    response = anthropic.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text.strip()

def send_whatsapp(text):
    max_len = 1500
    chunks = [text[i:i+max_len] for i in range(0, len(text), max_len)]
    for chunk in chunks:
        twilio.messages.create(from_=WHATSAPP_FROM, to=WHATSAPP_TO, body=chunk)

def main():
    try:
        print(f"[{datetime.now(SP)}] Buscando notícias...")
        noticias_mundo, noticias_brasil = fetch_news()
        print(f"[{datetime.now(SP)}] Notícias OK")

        print(f"[{datetime.now(SP)}] Buscando índices...")
        indices = fetch_indices()
        print(f"[{datetime.now(SP)}] Índices OK")

        print(f"[{datetime.now(SP)}] Gerando curadoria com Claude...")
        brief = curate(noticias_mundo, noticias_brasil, indices)
        print(f"[{datetime.now(SP)}] Claude OK")

        print(f"[{datetime.now(SP)}] Enviando WhatsApp...")
        send_whatsapp(brief)
        print(f"[{datetime.now(SP)}] Morning brief enviado com sucesso.")
    except Exception as e:
        import traceback
        print(f"[ERRO] {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
