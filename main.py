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
