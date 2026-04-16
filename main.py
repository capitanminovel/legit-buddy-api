import os
import requests
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

MENU_PAGES = [
    "https://shop.mnlegitcannabis.com/south-metro/menu",
    "https://shop.mnlegitcannabis.com/south-metro/menu?page=2",
    "https://shop.mnlegitcannabis.com/south-metro/menu?page=3",
]

@app.get("/")
def root():
    return {"status": "Legit Buddy API running"}

@app.post("/api/claude")
async def claude_proxy(request: Request):
    body = await request.json()
    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        json=body,
        timeout=30,
    )
    return response.json()

@app.get("/api/menu")
def fetch_menu():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
    }
    pages = []
    for url in MENU_PAGES:
        try:
            r = requests.get(url, headers=headers, timeout=15)
            pages.append(r.text)
        except Exception as e:
            pages.append("")
    return {"pages": pages}
