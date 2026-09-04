import os
import asyncio
import textwrap
import requests
from fastapi import FastAPI, Request, Response, HTTPException
from google import genai
from google.genai import types

app = FastAPI()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "menim_gizli_kodum_123")
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Gemini Müştərisinin başladılması
client = None
if GEMINI_API_KEY:
    client = genai.Client(api_key=GEMINI_API_KEY.strip())

# İstifadəçilərin dalbadal gələn DM mesajlarını toplamaq üçün bufer
USER_BUFFERS = {}
USER_TASKS = {}

# 1. DM ÜÇÜN ƏTRAFLI SATIŞ VƏ MENYU TƏLİMATI
DM_SYSTEM_PROMPT = """
Sən "RecScane Creative Media Agency"nin rəsmi, peşəkar və operativ virtual satış menecerisən.
Əsas vəzifən müştərinin istəyinə uyğun xidmətləri anlamaq, "Öz paketini özün qur" kalkulyatoru ilə dəqiq hesablama aparmaq və sifarişi qəbul etməkdir.

QƏTİ QAYDALAR:
1. MÖVZUDAN KƏNAR QADAĞA: RecScane agentliyinin xidmətlərinə aid olmayan heç bir suala cavab vermə.
2. DAXİLİ ANALİZ QADAĞASI: Müştəriyə yalnız hazır və səliqəli Azərbaycan dilindəki cavabı göndər.
3. HƏR DƏFƏ SALAM VERMƏ: Dialoq davam edirsə, hər mesaja təkrar salamla başlama.
4. MOBİL + VİRAL EDİT QADAĞASI: Müştəri Mobil çəkiliş seçdikdə, Viral Edit xidməti təklif olunmur.
5. FORMAT: Cavabları qısa, maddəli saxla. Hər hesablamanın sonunda müştərini WhatsApp-a yönləndir.

"ÖZ PAKETİNİ ÖZÜN QUR" HESABLAMA BAZASI:
1. Bir Dəfəlik Saatlıq Çəkilişlər:
- Mobil + Gimbal: 1 saat = 40 AZN (Hər əlavə saat +20 AZN)
- DJI Osmo Pocket: 1 saat = 60 AZN (Hər əlavə saat +30 AZN)
- Peşəkar Kamera + Gimbal: 1 saat = 120 AZN (Hər əlavə saat +60 AZN)
- Komanda (Mobil + Osmo + Peşəkar Kamera): 1 saat = 200 AZN (Hər əlavə saat +100 AZN)

2. Tədbir / Nişan / Ad Günü / Məkan Çəkilişləri (Sabit Qiymət):
- Mobil + Gimbal: 100 AZN | DJI Osmo Pocket: 120 AZN | Peşəkar Kamera + Gimbal: 200 AZN | Tam Komanda: 500 AZN

3. Video Montaj (Edit) Qiymətləri:
- Sadə Montaj: 45 san = 25 AZN | Pro SFX Montaj: 45 san = 50 AZN | Viral Montaj: 45 san = 70 AZN (Yalnız Kamera/Osmo üçün)

4. Aylıq SMM Paketləri:
- START SMM: 550 - 650 AZN / ay
- PRO SMM: 950 - 1 100 AZN / ay
- PREMIUM SCALE: 1 500 - 1 800 AZN / ay
- ENTERPRISE CUSTOM: 2 000 - 2 500 AZN / ay

5. Rəqəmsal Həllər & Veb Xidmətlər:
- Sadə Chatbot: 50 AZN | AI Agent: 100 AZN / aylıq | QR Davamiyyət: 100 AZN

ƏLAQƏ VƏ SİFARİŞ:
- WhatsApp: +994 10 528 26 32 | Instagram: @recscane
"""

# 2. ŞƏRHLƏR (REELS VƏ POST) ÜÇÜN İCTİMAİ VƏ SƏMİMİ TƏLİMAT
COMMENT_SYSTEM_PROMPT = """
Sən "RecScane Creative Media Agency"nin Instagram səhifəsindəki post və Reels şərhlərini cavablandıran nümayəndəsisən.

QAYDALAR:
1. Şərh yazan şəxsin fikrinə uyğun, səmimi, maraqlı və cəlbedici cavab ver.
2. Əgər tərif və ya xoş söz yazıblarsa, təşəkkür et.
3. Əgər qiymət və ya xidmət soruşurlarsa, qısa və ümumi məlumat verib detallı hesablama üçün "Zəhmət olmasa bizə Direct-dən yazın və ya WhatsApp ilə əlaqə saxlayın (+994 10 528 26 32)" de.
4. Çox uzun yazma (maksimum 1-2 cümlə), emoji istifadə et və təbii danış.
5. Yalnız Azərbaycan dilində cavab ver.
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

def generate_ai_reply(user_message: str, is_comment: bool = False) -> str:
    if not client:
        return "Salam! Zəhmət olmasa bir az sonra yazın, sistem yenilənir."
    try:
        chosen_prompt = COMMENT_SYSTEM_PROMPT if is_comment else DM_SYSTEM_PROMPT
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=chosen_prompt,
                temperature=0.4 if is_comment else 0.2
            )
        )
        return response.text.strip()
    except Exception as e:
        print("GEMINI XƏTASI:", e)
        return "Təşəkkürlər! Ətraflı məlumat üçün bizə Direct-dən yaza bilərsiniz." if is_comment else "Mesajınız qeydə alındı, tezliklə cavablandırılacaq."

# Direct Mesajı göndərmək
def process_and_reply(page_id: str, recipient_id: str, text: str):
    ai_reply = generate_ai_reply(text, is_comment=False)
    
    url = f"https://graph.instagram.com/v20.0/{page_id}/messages"
    headers = {
        "Authorization": f"Bearer {PAGE_ACCESS_TOKEN.strip()}",
        "Content-Type": "application/json"
    }
    
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
        print("DM GÖNDƏRMƏ STATU:", res.status_code, res.text)

# Şərhə cavab vermək (Comments Reply)
def reply_to_comment(comment_id: str, comment_text: str):
    ai_reply = generate_ai_reply(comment_text, is_comment=True)
    
    url = f"https://graph.instagram.com/v20.0/{comment_id}/replies"
    headers = {
        "Authorization": f"Bearer {PAGE_ACCESS_TOKEN.strip()}",
        "Content-Type": "application/json"
    }
    payload = {
        "message": ai_reply
    }
    
    res = requests.post(url, headers=headers, json=payload)
    print("ŞƏRH CAVABLANDIRMA STATU:", res.status_code, res.text)

async def delayed_process_messages(page_id: str, recipient_id: str):
    await asyncio.sleep(5.0)
    
    messages = USER_BUFFERS.pop(recipient_id, [])
    USER_TASKS.pop(recipient_id, None)
    
    if not messages:
        return
        
    full_text = "\n".join(messages)
    await asyncio.to_thread(process_and_reply, page_id, recipient_id, full_text)

@app.post("/webhook")
async def handle_events(request: Request):
    data = await request.json()
    
    if data.get("object") == "instagram":
        for entry in data.get("entry", []):
            page_id = entry.get("id")
            
            # 1. DIRECT MESAJLARI EMAL ETMƏK
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
                        
                    USER_TASKS[sender_id] = asyncio.create_task(
                        delayed_process_messages(page_id, sender_id)
                    )
            
            # 2. POST VƏ REELS ŞƏRHLƏRİNİ (COMMENTS) EMAL ETMƏK
            for change in entry.get("changes", []):
                if change.get("field") == "comments":
                    value = change.get("value", {})
                    comment_id = value.get("id")
                    comment_text = value.get("text")
                    sender_id = value.get("from", {}).get("id")

                    # Səhifənin öz şərhlərinə təkrar cavab verməməsi üçün yoxlama
                    if comment_text and sender_id and sender_id != page_id:
                        asyncio.create_task(
                            asyncio.to_thread(reply_to_comment, comment_id, comment_text)
                        )

        return {"status": "EVENT_RECEIVED"}
    return Response(status_code=404)
