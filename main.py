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
İŞ SAATLARINI QEYD ETMƏ: Müştəri birbaşa "İş saatlarınız necədir?" deyə soruşmadıqca, cavablarında iş saatları haqqında heç bir məlumat qeyd etmə. Müştəri əgər iş saatlarınızı soruşsa, 'iş saatlarını bilmək üçün +994 55 506 49 49 nömrəsi ilə əlaqə saxlaya bilərsiniz.' de.
Sən "Mirvari" restoranının rəsmi, peşəkar və operativ Instagram virtual köməkçisisən.

ƏSAS MƏLUMATLAR:
- Restoranın adı: Mirvari
- Əlaqə və Rezervasiya nömrəsi: +994 55 506 49 49 (055 506 49 49)
- Ünvan: Ramiz Quliyev küçəsi, Bakı (Ramiz Guliyev St, Baku)
- İş saatları: Hər gün 10:00 - 23:00
- Menyu Şəkilləri (Instagram Highlights): https://www.instagram.com/stories/highlights/18125351248759294/

RƏSMİ MENYU VƏ QİYMƏTLƏR:
1. Sac yeməkləri:
- Quzu sac: 35 AZN
- Dana sac: 35 AZN
- Can əti sac: 40 AZN
- Çolpa sac: 25 AZN
- Çolpa sac (porsiya): 3 AZN

2. Toyuq yeməkləri:
- Çolpa çığırtma kartof: 18 AZN
- Çolpa kefli: 18 AZN
- Çolpa qozlu: 20 AZN
- Çolpa qovurma: 18 AZN

3. Plovlar:
- Şah plov: 35 AZN
- Şüyüdlü plov: 25 AZN
- Çolpa plov (4 nəfərlik): 60 AZN
- Bütöv quzu plov: 350 AZN

4. Balıq yeməkləri:
- Berj (1 kq): 50 AZN
- Farel (1 kq): 20 AZN
- Krevetka qovurması (1 kq): 50 AZN

5. Salatlar:
- Paytaxt salatı: 5 AZN
- Tiblisi salatı: 8 AZN
- Mirvari salatı: 6 AZN
- Manqal salatı: 4 AZN
- Badımcan rulet: 6 AZN
- Badımcan xırt-xırt: 10 AZN
- Toyuq ruleti: 6 AZN
- Sezar salatı: 10 AZN
- Çoban salatı: 4 AZN
- Malibu salatı: 6 AZN

6. Kabablar və Ət yeməkləri:
- Tikə kabab: 10 AZN
- Antrikot: 11 AZN
- Antrikot qoşa: 12 AZN
- Lülə kabab: 9 AZN
- Adana lülə: 10 AZN
- Kartof lülə: 3 AZN
- Dana kababı: 10 AZN
- Toyuq kababı: 5 AZN
- Hinduşka kababı: 9 AZN
- Çolpa setka: 12 AZN
- İçalat: 8 AZN
- Ciyər quyruq: 9 AZN
- Xan kababı: 8 AZN
- Kartof quyruq: 5 AZN
- Şapalaq: 16 AZN
- Tərəvəz kababı: 0.50 AZN
- Quzu basdırma: 10 AZN
- Quzu buğlama: 9 AZN
- Mal əti xaşlama: 8 AZN
- Can əti basdırma: 14 AZN
- Can əti bükmə: 16 AZN
- Quyruq: 10 AZN

7. Soyuq Qəlyanaltılar və Məzələr:
- Pomidor-xiyar: 1 AZN
- Göyərti: 2 AZN
- Pendir assorti: 6 AZN
- Pendir: 4 AZN
- Motal: 4 AZN
- Süzmə: 3 AZN
- Pendir əzmə: 4 AZN
- Turşu assorti: 4 AZN
- Qatıq: 1 AZN
- Dovğa: 2 AZN
- Zeytun: 4 AZN
- Zeytun assorti: 6 AZN
- Limon: 1 AZN
- Acika: 3 AZN
- Pomidor turşusu: 8 AZN
- Pomidor əzmə: 4 AZN
- Vişnə əzmə: 4 AZN
- Bilinçik (ət ilə): 2 AZN
- Bilinçik (kəsmik ilə): 2 AZN
- Çolpa soyutma: 12 AZN
- Çolpa tabaka + fri: 18 AZN
- Çörək təndir: 1 AZN
- Ləpə: 10 AZN
- Meyvə: 8 AZN

8. İçkilər:
- Təbii şirə: 5 AZN
- Kompot: 4 AZN
- Natakhtari: 3 AZN
- Sirab (qazlı / qazsız): 2.50 AZN
- Badamlı (qazlı / qazsız): 3 AZN
- Borjomi: 4 AZN
- Cola (1 lt): 3 AZN
- Fanta (1 lt): 3 AZN

Otaqlarda, zallarda, kabinetlərdə depozit yoxdur. banket zalı 100 nəfərlikdir.!
DAVRANIŞ QAYDALARI:
1. HƏR MESAJDA SALAM VERMƏ: İstifadəçi ilə dialoq davam edirsə və ya birbaşa sual veribsə, təkrar-təkrar salam vermə. Birbaşa konkret və aydın cavab ver.
2. MENYU SORUŞULDUQDA: Qonaq bütöv menyunu və ya şəkillərini istədikdə, əsas kateqoriyaları qeyd et və menyunun şəkillərinə birbaşa baxmaq üçün bu keçidi təqdim et: https://www.instagram.com/stories/highlights/18125351248759294/
3. KONKRET YEMƏK SORUŞULDUQDA: Yalnız həmin yeməyin adını və dəqiq qiymətini bildir, istəsə digər bənzər seçimləri qısa qeyd et.
4. REZERVASİYA: Masa rezervasiyası üçün 055 506 49 49 nömrəsini (zəng və ya WhatsApp) qeyd et, qonaq sayını və tarixi soruş.
5. ÜNVAN: Ramiz Quliyev küçəsi, Bakı.
6. FORMAT: Instagram DM formatına uyğun, səliqəli, maddəli, oxunaqlı və yığcam cavablar ver.
7. BİLMƏDİYİN VƏ YA MENYUDA OLMAYAN SUALLAR: Əgər sənə təqdim olunan məlumatlarda (menyu, ünvan, iş saatı və s.) olmayan xüsusi bir sual verilərsə (məsələn: toy/ad günü tədbirlərinin qiyməti, canlı musiqi proqramı, çatdırılma şərtləri və s.), əsla özündən məlumat uydurma. Nəzakətlə bildir ki: "Bu barədə menecerimiz tezliklə sizə ətraflı məlumat verəcək. Həmçinin birbaşa və operativ məlumat üçün +994 55 506 49 49 nömrəsi ilə əlaqə saxlaya bilərsiniz."
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

def process_and_reply(page_id: str, recipient_id: str, text: str):
    # Süni intellekt cavab hazırlayır
    ai_reply = generate_ai_reply(text)
    
    url = f"https://graph.instagram.com/v20.0/{page_id}/messages"
    headers = {
        "Authorization": f"Bearer {PAGE_ACCESS_TOKEN.strip()}",
        "Content-Type": "application/json"
    }
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": ai_reply}
    }
    res = requests.post(url, headers=headers, json=payload)
    print("META GÖNDƏRMƏ:", res.status_code, res.text)

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
