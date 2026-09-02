import os
import asyncio
import textwrap
import requests
from fastapi import FastAPI, Request, Response, HTTPException
from groq import Groq

app = FastAPI()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "menim_gizli_kodum_123")
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

client = None
if GROQ_API_KEY:
    client = Groq(api_key=GROQ_API_KEY.strip())

USER_BUFFERS = {}
USER_TASKS = {}

SYSTEM_PROMPT = """
Sən "RecScane Creative Media Agency"nin rəsmi, peşəkar və operativ virtual satış menecerisən.
Əsas vəzifən müştərinin istəyinə uyğun xidmətləri anlamaq, "Öz paketini özün qur" kalkulyatoru ilə dəqiq hesablama aparmaq və sifarişi qəbul etməkdir.

QƏTİ QAYDALAR:
1. MÖVZUDAN KƏNAR QADAĞA: RecScane agentliyinin xidmətlərinə aid olmayan heç bir suala (kod, şeir, ümumi söhbət, riyaziyyat və s.) cavab vermə. Nəzakətlə yalnız media xidmətləri üzrə kömək edə biləcəyini bildir.
2. DAXİLİ ANALİZ QADAĞASI: İngiliscə və ya daxili qaralama, 'Draft', 'Step', 'Calculation' yazma. Müştəriyə yalnız hazır və səliqəli Azərbaycan dilindəki cavabı göndər.
3. HƏR DƏFƏ SALAM VERMƏ: Dialoq davam edirsə, hər mesaja təkrar salamla başlama.
4. MOBİL + VİRAL EDİT QADAĞASI: Müştəri Mobil çəkiliş seçdikdə, Viral Edit xidməti təklif olunmur.
5. FORMAT: Cavabları qısa, maddəli, konkret və Instagram DM formatına uyğun oxunaqlı saxla.

"ÖZ PAKETİNİ ÖZÜN QUR" HESABLAMA BAZASI:
1. Saatlıq Çəkiliş: Mobil 40 AZN/saat (+20), Osmo 60 AZN/saat (+30), Pro Kamera 120 AZN/saat (+60), Komanda 200 AZN/saat (+100)
2. Tədbir: Mobil 100 AZN, Osmo 120 AZN, Pro 200 AZN, Komanda 500 AZN
3. Edit: Sadə 45san=25 AZN, Pro SFX 45san=50 AZN, Viral 45san=70 AZN (Mobilə verilmir)
4. SMM: START 550-650 AZN, PRO 950-1100 AZN, PREMIUM 1500-1800 AZN, ENTERPRISE 2000-2500 AZN
5. Rəqəmsal: Chatbot 50 AZN, AI Agent 100 AZN/ay, QR 100 AZN

ƏLAQƏ: +994 10 528 26 32, @recscane, recscane@gmail.com
"""

@app.api_route("/", methods=["GET", "HEAD"])
def home():
    return {"status": "RecScane AI Agent 24/7 aktivdir"}

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
        return "Salam! Sistem yenilənir, bir az sonra yazın."
    try:
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ],
            temperature=0.3,
            max_tokens=1000
        )
        return completion.choices[0].message.content
    except Exception as e:
        print("GROQ XƏTASI:", e)
        return "Salam! Mesajınız qeydə alındı, tezliklə əməkdaşlarımız sizə geri dönüş edəcək."

def process_and_reply(page_id: str, recipient_id: str, text: str):
    ai_reply = generate_ai_reply(text)
    url = f"https://graph.instagram.com/v20.0/{page_id}/messages"
    headers = {
        "Authorization": f"Bearer {PAGE_ACCESS_TOKEN.strip()}",
        "Content-Type": "application/json"
    }
    chunks = textwrap.wrap(ai_reply, width=900, replace_whitespace=False, break_long_words=False) or [ai_reply]
    for chunk in chunks:
        payload = {"recipient": {"id": recipient_id}, "message": {"text": chunk}}
        res = requests.post(url, headers=headers, json=payload)
        print("META GÖNDƏRMƏ STATU:", res.status_code, res.text)

async def delayed_process_messages(page_id: str, recipient_id: str):
    await asyncio.sleep(15.0)
    messages = USER_BUFFERS.pop(recipient_id, [])
    USER_TASKS.pop(recipient_id, None)
    if not messages:
        return
    full_text = "\n".join(messages)
    await asyncio.to_thread(process_and_reply, page_id, recipient_id, full_text)

@app.post("/webhook")
async def handle_messages(request: Request):
    data = await request.json()
    if data.get("object") == "instagram":
        for entry in data.get("entry", []):
            page_id = entry.get("id")
            for messaging_event in entry.get("messaging", []):
                sender_id = messaging_event.get("sender", {}).get("id")
                message = messaging_event.get("message", {})
                text = message.get("text")
                if text and not message.get("is_echo"):
                    if sender_id not in USER_BUFFERS:
                        USER_BUFFERS[sender_id] = []
                    USER_BUFFERS[sender_id].append(text)
                    if sender_id in USER_TASKS and not USER_TASKS[sender_id].done():
                        USER_TASKS[sender_id].cancel()
                    USER_TASKS[sender_id] = asyncio.create_task(delayed_process_messages(page_id, sender_id))
        return {"status": "EVENT_RECEIVED"}
    return Response(status_code=404)
