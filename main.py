from generation import generate_image
import vk_api
import os
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.utils import get_random_id
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.upload import VkUpload
from flask import Flask
import threading
import io
import requests
import base64

HF_TOKEN = os.getenv("HF_TOKEN")
API_URL = "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell"
# Настройки доступа
TOKEN = os.getenv("VK_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")

# Авторизация
vk_session = vk_api.VkApi(token=TOKEN)
vk = vk_session.get_api()
longpoll = VkLongPoll(vk_session)
upload = VkUpload(vk)

def create_keyboard():
    keyboard = VkKeyboard(one_time=False) # one_time=False значит, что кнопки не исчезнут после нажатия
    
    # Добавляем синюю кнопку
    keyboard.add_button("Сделать фото", color=VkKeyboardColor.PRIMARY)
    
    # Добавляем новую строку и белую кнопку
    keyboard.add_line()
    keyboard.add_button("Помощь", color=VkKeyboardColor.SECONDARY)
    
    return keyboard.get_keyboard()

def upload_photo_to_vk(image_bytes, user_id):
    upload = VkUpload(vk_session)
    # Превращаем байты в объект файла, который понимает библиотека
    img = io.BytesIO(image_bytes)
    photo = upload.photo_messages(photos=img)[0]
    # Формируем строку вложения: photoOWNERID_PHOTOID
    return f"photo{photo['owner_id']}_{photo['id']}"

def generate_image(prompt, image_url=None):
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    img_data = None
    encoded_image = None

    if image_url:
        download_res = requests.get(image_url)
        if download_res.status_code == 200:
            encoded_image = base64.b64encode(download_res.content).decode("utf-8")
            img_data = download_res.content
            
              
        else:
            print("Ошибка скачивания фото")   
    if encoded_image:
        payload = {
            "inputs": prompt,
            "image": encoded_image,
            "parameters": {
                "strength": 0.7  # 0.1 — почти не меняет фото, 0.9 — меняет очень сильно
                }
            }
        
    else:
        payload = {"inputs": prompt}   


    response = requests.post(API_URL, headers=headers, json=payload)
    if response.status_code == 200:
        return response.content
    else:
        print(f"Ошибка API: {response.status_code}")
        return None
    

             
print("Бот запущен и слушает сообщения...")

user_states = {}
user_photos = {}
app = Flask('')

@app.route('/')
def home():
    return "I'm alive"

def run():
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    t = threading.Thread(target=run)
    t.start()

# Вызываем это перед запуском основного цикла бота
keep_alive()
for event in longpoll.listen():
    if event.type == VkEventType.MESSAGE_NEW and event.to_me:
        print(f"Пришло сообщение: '{event.text}'") # Кавычки помогут увидеть лишние пробелы
        user_id = event.user_id
        text = event.text.lower()
        if event.attachments:
            # Пытаемся достать полную информацию о сообщении, чтобы найти прямую ссылку
            try:
                msg_full = vk.messages.getById(message_ids=event.message_id)['items'][0]
                for attach in msg_full.get('attachments', []):
                    if attach['type'] == 'photo':
                        # Выбираем самый большой размер фото
                        photo_url = attach['photo']['sizes'][-1]['url']
                user_photos[user_id] = photo_url
                print(f"📸 Фото сохранено для {user_id}")
            except Exception as e:
                print(f"Ошибка при получении фото: {e}")
  
            # Логика ответов
        if text == "начать":
            vk.messages.send(user_id=user_id,
            random_id=get_random_id(), 
            message="Привет! Я твой бот-генератор. Нажми на кнопку, чтобы создать шедевр!",
            keyboard=create_keyboard())
           
        elif text == "сделать фото":
            user_states[user_id] = "waiting_for_prompt"
            vk.messages.send(user_id=user_id,
            random_id=get_random_id(),
            message="Напишите, что вы хотите увидеть на фото? (можно на русском) 🎨"
          ) 
        elif user_states.get(user_id) == "waiting_for_prompt":
            prompt = event.text
            photo_url = user_photos.get(user_id)
            print(f"DEBUG: Ссылка на фото: {photo_url}")
    
                # 2. Передаем и текст, и фото в функцию
            image_bytes = generate_image(prompt, photo_url)

            if image_bytes:
                    # 3. Отправляем фото (ваш код с BytesIO и upload)
                attachment = upload_photo_to_vk(image_bytes, user_id)
                vk.messages.send(user_id=user_id, random_id=get_random_id(), 
                                         message="Готово! ✨", attachment=attachment)
                    
                    # 4. УДАЛЯЕМ данные, чтобы не мешали в следующий раз
                user_states.pop(user_id, None)
                user_photos.pop(user_id, None)
                
            print(f"--- Отправляю нейросети запрос: {prompt} ---")
            image_bytes = generate_image(prompt) 
            if image_bytes:
                    from io import BytesIO
                # 1. Превращаем байты в "файл" для ВК
                    image_file = BytesIO(image_bytes)
                # 2. Загружаем на сервер ВК
                    photo = upload.photo_messages(photos=image_file)[0]
                # 3. Отправляем сообщение с вложением
                    attachment = f"photo{photo['owner_id']}_{photo['id']}"
                    vk.messages.send(user_id=user_id, random_id=get_random_id(), attachment=attachment)
                    print ( "Картинка успешно сгенерирована")
            else:
                vk.messages.send(user_id=user_id, random_id=get_random_id(), message="Ошибка при создании фото. 😔")
            
                user_states[user_id] = None
@bot.on.message()
async def handle_message(message: Message):
    print(f"Получено сообщение: {text}")
    text = event.text.lower()
    user_id = event.user_id
    if 'attach1_type' in event.attachments:
        if event.attachments['attach1_type'] == 'photo':
                # Получаем ID фото, чтобы достать ссылку
            photo_id = event.attachments['attach1']
                # Чтобы получить именно URL, нам нужно вызвать метод API
            full_msg = vk.messages.getById(message_ids=event.message_id)['items'][0]
                # Берем самую большую версию фото
            photo_url = full_msg['attachments'][0]['photo']['sizes'][-1]['url']
            user_photos[user_id] = photo_url
            print(f"✅ Фото сохранено для пользователя {user_id}")
    
    if user_states.get(user_id) == "waiting_for_prompt":
        photo_bytes = None # Изначально считаем, что фото нет
    if message.attachments:
        for attachment in message.attachments:
            if attachment.photo:
                    # Берем URL самой большой версии изображения
                    photo_url = attachment.photo.sizes[-1].url
                    # 2. Скачиваем байты изображения через requests
                    response = requests.get(photo_url)
                    if response.status_code == 200:
                        photo_bytes = response.content
                        break # Нам достаточно одного фото

        vk.message.send("Начинаю генерацию, подождите немного... ⏳")

        try: # 3. Вызываем функцию генерации
            result = generate_image(user_text, photo_bytes, HF_TOKEN)
            
            if result:
                # 4. Загружаем результат в ВК и получаем строку-вложение
                attachment_str = upload_photo_to_vk(result, user_id)
                
                # 5. Отправляем сообщение с прикрепленным фото
                vk.messages.send(user_id=user_id, message="Ваше изображение готово!", attachment=attachment_str, random_id=0)
            else:
                vk.messages.send(user_id=user_id, message="Сервер вернул пустой ответ. 😟", random_id=0)
        
        except Exception as e:
            # Если что-то пошло не так
            print(f"Произошла ошибка: {e}")
            vk.messages.send(user_id=user_id, message="Извините, сейчас я не могу обработать запрос. 😔", random_id=0)
        
        user_states[user_id] = None

              
    vk.messages.send(user_id=user_id, random_id=get_random_id(), message="Принял! Рисую... 🎨")
          
    image_bytes = generate_image(text, "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")
            
    if image_bytes:
                attachment = upload_photo_to_vk(image_bytes, user_id)
                vk.messages.send(
                    user_id=user_id,
                    random_id=get_random_id(),
                    message="Ваш шедевр готов! ✨",
                    attachment=attachment
                )
    else:
                vk.messages.send(user_id=user_id, random_id=get_random_id(), message="Произошла ошибка при генерации. 😔")
            
    del user_states[user_id]
        
       