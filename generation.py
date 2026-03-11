import requests
import base64
from deep_translator import GoogleTranslator

# Функция перевода остается прежней
def translate_prompt(text_ru):
    translation = GoogleTranslator(source='auto', target='en').translate(text_ru)
    return translation


def generate_image(prompt_ru, image_bytes, hf_token):
    # 1. Перевод
    english_prompt = translate_prompt(prompt_ru)
            
    API_URL = "https://router.huggingface.co/fal-ai/fal-ai/qwen-image-edit-2511/lora?_subdomain=queue"
    headers = {
    "Authorization": f"Bearer {os.environ['HF_TOKEN']}",
}

    if image_bytes is not None:
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        payload = {
            "inputs": english_prompt,
            "parameters": {
                "image": base64_image
            }
        }
    else:
        payload = {
            "inputs": english_prompt
        }
       

    # Шаг 3: Запрос напрямую без прокси
    no_proxies = {
        "http": None,
        "https": None,
    }

    response = requests.post(API_URL, headers=headers, json=payload, proxies=no_proxies)

    if response.status_code == 200:
        return response.content  # Возвращаем байты картинки
    else:
        print(f"Ошибка Hugging Face: {response.status_code}")
        print(f"Ответ сервера: {response.text}")
        return None