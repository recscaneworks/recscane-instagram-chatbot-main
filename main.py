import os
import asyncio
import textwrap
import time
import requests
from fastapi import FastAPI, Request, Response, HTTPException
from google import genai
from google.genai import types

app = FastAPI()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "menim_gizli_kodum_123")
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

client = None
if GEMINI_API_KEY:
    client = genai.Client(api_key=GEMINI_API_KEY.strip())

USER_BUFFERS = {}
USER_TASKS = {}
USER_CHATS = {}

# ==========================================
# 1. QADAĞA VƏ NƏZARƏT TƏNZİMLƏMƏLƏRİ
# ==========================================
# Cavab verilməyəcək Instagram istifadəçi adları (kiçik hərflərlə, @ olmadan)
IGNORED_USERNAMES = {
    "mifantasty",
    "hesen_akbar",
    "hesen_rec",
}

# Müəyyən etdiyin konkret Instagram ID-lər (əgər ID bilirsənsə)
IGNORED_USER_IDS = set()

# Əllə cavab verdiyin insanları 24 saatlıq saxlamaq üçün: {user_id: susdurulma_bitmə_vaxtı}
MUTED_USERS = {}
MUTE_DURATION_SECONDS = 24 * 60 * 60  # 24 saat (saniyə ilə)

# Direct üçün prompt
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

# Şərhlər üçün prompt
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

def is_user_blocked(user_id: str) -> bool:
    """İstifadəçinin qara siyahıda və ya 24 saatlıq susdurulmada olmasını yoxlayır."""
    current_time = time.time()
    
    # 1. 24 saatlıq əllə idarə yoxlaması
    if user_id in MUTED_USERS:
        if current_time < MUTED_USERS[user_id]:
            print(f"[BLOK] {user_id} hazırda susdurulub (manual cavab verilib).")
            return True
        else:
            del MUTED_USERS[user_id]  # Vaxtı bitibsə sil

    # 2. Konkret ID qara siyahısı
    if user_id in IGNORED_USER_IDS:
        return True

    # 3. İstifadəçi adını yoxlamaq üçün Instagram Graph API sorğusu
    if IGNORED_USERNAMES:
        try:
            url = f"https://graph.instagram.com/v20.0/{user_id}?fields=username&access_token={PAGE_ACCESS_TOKEN.strip()}"
            res = requests.get(url).json()
            username = res.get("username", "").lower()
            if username in IGNORED_USERNAMES:
                IGNORED_USER_IDS.add(user_id)  # Təkrar sorğu atmamaq üçün ID-ni də əlavə edirik
                print(f"[QARA SİYAHI] @{username} botdan bloklandı.")
                return True
        except Exception as e:
            print("İstifadəçi adı yoxlanarkən xəta:", e)

    return False

def generate_ai_reply(user_message: str, is_comment: bool = False, sender_id: str = None) -> str:
    if not client:
        return "Salam! Zəhmət olmasa bir az sonra yazın, sistem yenilənir."
    try:
        if is_comment:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=user_message,
                config=types.GenerateContentConfig(
                    system_instruction=COMMENT_SYSTEM_PROMPT,
                    temperature=0.4
                )
            )
            return response.text.strip()
        else:
            if sender_id not in USER_CHATS:
                USER_CHATS[sender_id] = client.chats.create(
                    model="gemini-2.5-flash",
                    config=types.GenerateContentConfig(
                        system_instruction=DM_SYSTEM_PROMPT,
                        temperature=0.2
                    )
                )
            response = USER_CHATS[sender_id].send_message(user_message)
            return response.text.strip()
    except Exception as e:
        print("GEMINI XƏTASI:", e)
        if sender_id in USER_CHATS:
            del USER_CHATS[sender_id]
        return "Təşəkkürlər! Ətraflı məlumat üçün bizə Direct-dən yaza bilərsiniz." if is_comment else "Mesajınız qeydə alındı, tezliklə cavablandırılacaq."

def process_and_reply(page_id: str, recipient_id: str, text: str):
    if is_user_blocked(recipient_id):
        return

    ai_reply = generate_ai_reply(text, is_comment=False, sender_id=recipient_id)
    
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

def reply_to_comment(comment_id: str, comment_text: str, sender_id: str):
    if is_user_blocked(sender_id):
        return

    ai_reply = generate_ai_reply(comment_text, is_comment=True)
    
    url = f"https://graph.instagram.com/v20.0/{comment_id}/replies"
    headers = {
        "Authorization": f"Bearer {PAGE_ACCESS_TOKEN.strip()}",
        "Content-Type": "application/json"
    }
    payload = {"message": ai_reply}
    
    res = requests.post(url, headers=headers, json=payload)
    print("ŞƏRH CAVABLANDIRMA STATU:", res.status_code, res.text)

async def delayed_process_messages(page_id: str, recipient_id: str):
    await asyncio.sleep(5.0)
    
    messages = USER_BUFFERS.pop(recipient_id, [])
    USER_TASKS.pop(recipient_id, None)
    
    if not messages or is_user_blocked(recipient_id):
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
                recipient_id = messaging_event.get("recipient", {}).get("id")
                message = messaging_event.get("message", {})
                text = message.get("text")
                is_echo = message.get("is_echo", False)

                # ƏLLƏ CAVAB VERİLDİKDƏ BOTUN 24 SAAT SUSMASI:
                # Sən Direct-dən yazanda Instagram `is_echo: True` göndərir.
                # Bu halda mesajı alan şəxs (recipient_id) 24 saatlıq susdurulur.
                if is_echo:
                    MUTED_USERS[recipient_id] = time.time() + MUTE_DURATION_SECONDS
                    # Əgər həmin anda növbədə botun göndərəcəyi cavab vardısa, onu ləğv et
                    if recipient_id in USER_TASKS and not USER_TASKS[recipient_id].done():
                        USER_TASKS[recipient_id].cancel()
                    USER_BUFFERS.pop(recipient_id, None)
                    print(f"[MANUAL INTERVENTION] {recipient_id} 24 saatlıq susduruldu.")
                    continue

                # Müştəri mesaj yazdıqda
                if text and not is_echo:
                    if is_user_blocked(sender_id):
                        continue

                    if sender_id not in USER_BUFFERS:
                        USER_BUFFERS[sender_id] = []
                    USER_BUFFERS[sender_id].append(text)
                    
                    if sender_id in USER_TASKS and not USER_TASKS[sender_id].done():
                        USER_TASKS[sender_id].cancel()
                        
                    USER_TASKS[sender_id] = asyncio.create_task(
                        delayed_process_messages(page_id, sender_id)
                    )
            
            # 2. ŞƏRHLƏRİ EMAL ETMƏK
            for change in entry.get("changes", []):
                if change.get("field") == "comments":
                    value = change.get("value", {})
                    comment_id = value.get("id")
                    comment_text = value.get("text")
                    sender_id = value.get("from", {}).get("id")

                    if comment_text and sender_id and sender_id != page_id:
                        if not is_user_blocked(sender_id):
                            asyncio.create_task(
                                asyncio.to_thread(reply_to_comment, comment_id, comment_text, sender_id)
                            )

        return {"status": "EVENT_RECEIVED"}
    return Response(status_code=404)
