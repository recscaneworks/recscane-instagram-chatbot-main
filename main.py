from fastapi import FastAPI, Request, Response, HTTPException, BackgroundTasks
from google import genai
from google.genai import types
import requests
import os

app = FastAPI()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "menim_gizli_kodum_123")
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Gemini Müştərisinin başladılması
client = None
if GEMINI_API_KEY:
    client = genai.Client(api_key=GEMINI_API_KEY.strip())

# RESTORANIN TƏLİMAT BAZASI VƏ MENYUSU (TRAIN HİSSƏSİ)
SYSTEM_PROMPT = """
Sən "RecScane Creative Media Agency"-nin rəsmi satış menecerisən.
Sual verən müştəriyə Azərbaycan dilində, təbii, səmimi və birbaşa cavab ver.

QƏTİ QADAĞALAR:
- İngiliscə heç bir daxili analiz, düşüncə, qaralama, 'Self-correction', 'Draft', 'Step', 'Option', 'Check' yazma.
- Yalnız və yalnız birbaşa müştəriyə deyiləcək son Azərbaycan dilindəki cavabı göndər.

Agentlik Faktları:
1. SMM Paketləri:
   - START SMM: 550 - 650 AZN / ay (8 Video Reels, 3 Post, 15 Story, 1 çəkiliş günü).
   - PRO SMM: 950 - 1 100 AZN / ay (12 Reels Sony a7IV + SFX, 4 Post, 30 Story, 2 çəkiliş günü, Baza Chatbot).
   - PREMIUM SCALE: 1 500 - 1 800 AZN / ay (16 Reels 2D Motion, 6 Post, 60 Story, 3-4 çəkiliş günü, AI Agent).
2. 1 Dəfəlik Saatlıq Çəkilişlər:
   - Mobil + Gimbal: 40 AZN / 1-ci saat (+20 AZN növbəti saatlar).
   - DJI Osmo Pocket 3: 60 AZN / 1-ci saat (+30 AZN növbəti saatlar).
   - Pro Kamera (Sony a7 IV): 120 AZN / 1-ci saat (+60 AZN növbəti saatlar).
   - Komanda ilə çəkiliş (3 kamera): 200 AZN / 1-ci saat (+100 AZN növbəti saatlar).
3. Tədbir / Nişan / Ad Günü / Ev / Məkan / Villa Çəkilişləri:
   - Mobil: 100 AZN | Osmo: 120 AZN | Pro Kamera (Sony α7 IV): 200 AZN | Komanda: 500 AZN.
4. Montaj: Sadə (25 AZN / 45san), Pro SFX (50 AZN / 45san), Viral (70 AZN / 45san).
5. Chatbot & Veb: Sadə Chatbot (50 AZN), AI Agent (100 AZN/ay), QR Davamiyyət (100 AZN).
6. Əlaqə & WhatsApp: +994 10 528 26 32 | Instagram: @recscane.  | Gmail: recscane@gmail.com
"""

@app.api_route("/", methods=["GET", "HEAD"])
def home():
    return {"status": "Mirvari Gemini Bot 24/7 aktivdir"}

@app.get("/webhook")
def verify_webhook(request: Request):
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode and token:
        if mode == "subscribe" and token == VERIFY_TOKEN:
            return Response(content=challenge, media_type="text/plain")
        raise HTTPException(status_code=403, detail="Təsdiq tokeni səhvdir")
    raise HTTPException(status_code=400, detail="Xətalı sorğu")

def generate_ai_reply(user_message: str) -> str:
    if not client:
        return "Salam! Zəhmət olmasa bir az sonra yazın, sistem yenilənir."
    try:
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.7
            )
        )
        return response.text
    except Exception as e:
        print("GEMINI XƏTASI:", e)
        return "Salam! Mesajınız qeydə alındı, tezliklə əməkdaşlarımız sizə geri dönüş edəcək."

import textwrap

def process_and_reply(page_id: str, recipient_id: str, text: str):
    ai_reply = generate_ai_reply(text)
    
    url = f"https://graph.instagram.com/v20.0/{page_id}/messages"
    headers = {
        "Authorization": f"Bearer {PAGE_ACCESS_TOKEN.strip()}",
        "Content-Type": "application/json"
    }
    
    # Sözləri parçalamadan, boşluqlara nəzərən maksimum 900 simvola bölür
    chunks = textwrap.wrap(
        ai_reply,
        width=900,
        replace_whitespace=False,
        break_long_words=False
    ) or [ai_reply]
    
    for chunk in chunks:
        payload = {
            "recipient": {"id": recipient_id},
            "message": {"text": chunk}
        }
        res = requests.post(url, headers=headers, json=payload)
        print("META GÖNDƏRMƏ STATU:", res.status_code, res.text)

@app.post("/webhook")
async def handle_messages(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    
    if data.get("object") == "instagram":
        for entry in data.get("entry", []):
            page_id = entry.get("id")
            for messaging_event in entry.get("messaging", []):
                sender_id = messaging_event.get("sender", {}).get("id")
                message = messaging_event.get("message", {})
                text = message.get("text")

                if text and not message.get("is_echo"):
                    background_tasks.add_task(process_and_reply, page_id, sender_id, text)

        return {"status": "EVENT_RECEIVED"}
    return Response(status_code=404)
