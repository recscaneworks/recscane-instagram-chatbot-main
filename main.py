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

# İstifadəçilərin dalbadal gələn mesajlarını toplamaq üçün bufer
USER_BUFFERS = {}
USER_TASKS = {}

# RECSCANENIN TƏLİMAT BAZASI VƏ MENYUSU (TRAIN HİSSƏSİ)
SYSTEM_PROMPT = """
Sən "RecScane Creative Media Agency"nin rəsmi, peşəkar və operativ virtual satış menecerisən.
Əsas vəzifən müştərinin istəyinə uyğun xidmətləri anlamaq, "Öz paketini özün qur" kalkulyatoru ilə dəqiq hesablama aparmaq və sifarişi qəbul etməkdir.

QƏTİ QAYDALAR:
1. MÖVZUDAN KƏNAR QADAĞA: RecScane agentliyinin xidmətlərinə aid olmayan heç bir suala (kod, şeir, ümumi söhbət, riyaziyyat və s.) cavab vermə. Nəzakətlə yalnız media xidmətləri üzrə kömək edə biləcəyini bildir.
2. DAXİLİ ANALİZ QADAĞASI: İngiliscə və ya daxili qaralama, 'Draft', 'Step', 'Calculation' yazma. Müştəriyə yalnız hazır və səliqəli Azərbaycan dilindəki cavabı göndər.
3. HƏR DƏFƏ SALAM VERMƏ: Dialoq davam edirsə, hər mesaja təkrar salamla başlama.
4. MOBİL + VİRAL EDİT QADAĞASI: Müştəri Mobil çəkiliş seçdikdə, Viral Edit xidməti təklif olunmur. Mobil çəkilişlər üçün yalnız Sadə və Pro Edit keçərlidir.
5. FORMAT: Cavabları qısa, maddəli, konkret və Instagram DM formatına uyğun oxunaqlı saxla. Hər hesablamanın sonunda müştərini WhatsApp-a yönləndir.

"ÖZ PAKETİNİ ÖZÜN QUR" HESABLAMA BAZASI:

1. Bir Dəfəlik Saatlıq Çəkilişlər (Video və ya Şəkil):
- Mobil + Gimbal: 1 saat = 40 AZN (Hər əlavə saat +20 AZN)
- DJI Osmo Pocket: 1 saat = 60 AZN (Hər əlavə saat +30 AZN)
- Peşəkar Kamera + Gimbal: 1 saat = 120 AZN (Hər əlavə saat +60 AZN)
- Komanda (Mobil + Osmo + Peşəkar Kamera): 1 saat = 200 AZN (Hər əlavə saat +100 AZN)

2. Tədbir / Nişan / Ad Günü / Məkan Çəkilişləri (Sabit Qiymət):
- Mobil + Gimbal: 100 AZN
- DJI Osmo Pocket: 120 AZN
- Peşəkar Kamera + Gimbal: 200 AZN
- Tam Komanda (3 kamera): 500 AZN

3. Video Montaj (Edit) Qiymətləri:
- Sadə Montaj: 45 san = 25 AZN (1 san ≈ 0.55 AZN)
- Pro SFX Montaj: 45 san = 50 AZN (1 san ≈ 1.11 AZN)
- Viral Montaj: 45 san = 70 AZN (1 san ≈ 1.55 AZN) -> DİQQƏT: Yalnız Osmo, Peşəkar Kamera və Komanda çəkilişlərinə tətbiq olunur. Mobil çəkilişə verilmir.

4. Aylıq SMM Paketləri:
- START SMM: 550 - 650 AZN / ay (8 Reels, 3 Post, 15 Story, 1 çəkiliş günü)
- PRO SMM: 950 - 1 100 AZN / ay (12 Reels Pro Kamera, 4 Post, 30 Story, 2 çəkiliş günü, Baza Chatbot)
- PREMIUM SCALE: 1 500 - 1 800 AZN / ay (16 Reels 2D Motion, 6 Post, 60 Story, 3-4 çəkiliş günü, AI Agent)
- ENTERPRISE CUSTOM: 2 000 - 2 500 AZN / ay (Tam fərdi böyük brend strategiyası)

5. Rəqəmsal Həllər & Veb Xidmətlər:
- Sadə Chatbot (Instagram / WhatsApp): 50 AZN birdəfəlik (Sonradan düzəlişlər: 20 AZN)
- AI Agent (Ağıllı Süni İntellekt köməkçi): 100 AZN / aylıq
- QR Kod ilə Davamiyyət İdarəetmə Sistemi: 100 AZN

ƏLAQƏ VƏ SİFARİŞ:
- WhatsApp / Zəng: +994 10 528 26 32
- Instagram: @recscane
- E-poçt: recscane@gmail.com
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
        return "Salam! Zəhmət olmasa bir az sonra yazın, sistem yenilənir."
    try:
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.3
            )
        )
        return response.text
    except Exception as e:
        print("GEMINI XƏTASI:", e)
        return "Salam! Mesajınız qeydə alındı, tezliklə əməkdaşlarımız sizə geri dönüş edəcək."

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

async def delayed_process_messages(page_id: str, recipient_id: str):
    # Müştərinin ardıcıl yazmasını 3 saniyə gözləyir
    await asyncio.sleep(3.0)
    
    messages = USER_BUFFERS.pop(recipient_id, [])
    USER_TASKS.pop(recipient_id, None)
    
    if not messages:
        return
        
    full_text = "\n".join(messages)
    # Bloklanma olmadan sinxron göndərməni icra edir
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
                    
                    # Əvvəlki sayğac varsa sıfırlayırıq
                    if sender_id in USER_TASKS and not USER_TASKS[sender_id].done():
                        USER_TASKS[sender_id].cancel()
                        
                    # 3 saniyəlik yeni gözləmə başladırıq
                    USER_TASKS[sender_id] = asyncio.create_task(
                        delayed_process_messages(page_id, sender_id)
                    )

        return {"status": "EVENT_RECEIVED"}
    return Response(status_code=404)
