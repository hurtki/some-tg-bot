import telebot
from telebot import types
import threading
import time
from typing import Dict, Optional
import requests

from .config import settings, messages
from .database import Database

print("🚀 БОТ СТАРТОВАЛ! Проверка вывода в логи.")

# Инициализация
bot = telebot.TeleBot(settings.bot_token)
db = Database()

# Временное хранение данных пользователей
user_states: Dict[int, str] = {}
user_data: Dict[int, dict] = {}

# Проверка подписки на канал
def check_subscription(user_id: int) -> bool:
    try:
        member = bot.get_chat_member(f"@{settings.channel_username}", user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False
# Клавиатуры
def get_subscription_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(types.KeyboardButton(messages.get('buttons.check_subscription', channel_username=settings.channel_username)))
    return markup

def get_main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(types.KeyboardButton(messages.get('buttons.write_post')))
    markup.add(types.KeyboardButton(messages.get('buttons.support')))
    return markup

def get_photo_skip_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(types.KeyboardButton(messages.get('buttons.skip_photo')))
    return markup

def get_anonymity_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(types.KeyboardButton(messages.get('buttons.anonymous')))
    markup.add(types.KeyboardButton(messages.get('buttons.leave_contact')))
    return markup

def get_confirmation_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.row(
        types.KeyboardButton(messages.get('buttons.yes_send')),
        types.KeyboardButton(messages.get('buttons.no_restart'))
    )
    return markup

def get_moderation_keyboard(post_id: int):
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton(
            messages.get('buttons.approve'), 
            callback_data=f'approve_{post_id}'
        ),
        types.InlineKeyboardButton(
            messages.get('buttons.reject'), 
            callback_data=f'reject_{post_id}'
        )
    )
    return markup


# Обработчики команд
@bot.message_handler(commands=['start'])
def start_handler(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    
    # Сначала добавляем/обновляем пользователя
    db.add_user(user_id, username, first_name)
    
    # ЗАТЕМ проверяем бан
    if db.is_user_banned(user_id):
        bot.send_message(user_id, messages.get('moderation.user_banned_notification'))
        return
    
    # Затем проверяем подписку
    if not check_subscription(user_id):
        bot.send_message(message.chat.id, messages.get('subscription.check_required', settings.channel_username),
                        reply_markup=get_subscription_keyboard())
        return
    
    # Отправляем главное меню
    bot.send_message(message.chat.id, messages.get('welcome.greeting'),
                    reply_markup=get_main_keyboard())

@bot.message_handler(commands=['admin'])
def admin_handler(message: types.Message):
    user_id = message.from_user.id
    
    if not db.is_admin(user_id):
        bot.send_message(message.chat.id, messages.get('admin_commands.not_admin'))
        return
    
    bot.send_message(
        message.chat.id,
        messages.get('admin_commands.admin_help')
    )

@bot.message_handler(commands=['ban'])
def ban_handler(message: types.Message):
    if not db.is_admin(message.from_user.id):
        return
    
    try:
        args = message.text.split()[1:]
        if not args:
            bot.send_message(message.chat.id, "Укажите ID")
            return
        
        target = args[0]

        target_id = int(target)
        db.ban_user(target_id)
        
        # Уведомляем админов
        bot.send_message(
            message.chat.id, 
            messages.get('moderation.user_banned_admin', user=target_id)
        )
        
        # Уведомляем пользователя
        try:
            bot.send_message(
                target_id,
                messages.get('moderation.user_banned_notification')
            )
        except:
            pass
            
    except (ValueError, IndexError) as e:
        bot.send_message(message.chat.id, "Неверный формат. Используйте: /ban ID")
        bot.send_message(message.chat.id, f"ошибка {e}")

@bot.message_handler(commands=['unban'])
def unban_handler(message: types.Message):
    if not db.is_admin(message.from_user.id):
        return
    
    try:
        args = message.text.split()[1:]
        if not args:
            bot.send_message(message.chat.id, "Укажите ID пользователя")
            return
        
        target_id = int(args[0])
        db.unban_user(target_id)
        
        # Уведомляем админов
        bot.send_message(
            message.chat.id, 
            messages.get('moderation.user_unbanned_admin', user=target_id)
        )
        
        # Уведомляем пользователя
        try:
            bot.send_message(
                target_id,
                messages.get('moderation.user_unbanned_notification')
            )
        except:
            pass
            
    except (ValueError, IndexError):
        bot.send_message(message.chat.id, "Неверный формат. Используйте: /unban ID")

@bot.message_handler(commands=['stats'])
def stats_handler(message: types.Message):
    if not db.is_admin(message.from_user.id):
        return
    
    stats = db.get_stats()
    bot.send_message(
        message.chat.id,
        messages.get('stats.message', 
                    total_users=stats['users_count'], 
                    total_posts=stats['total_posts'])
    )

@bot.message_handler(commands=['rasil'])
def broadcast_handler(message: types.Message):
    if not db.is_admin(message.from_user.id):
        return
    
    try:
        broadcast_text = ' '.join(message.text.split()[1:])
        if not broadcast_text:
            bot.send_message(message.chat.id, "Введите текст для рассылки")
            return
        
        bot.send_message(
            message.chat.id, 
            messages.get('broadcast.starting', message_text=broadcast_text)
        )
        
        # Запускаем рассылку в отдельном потоке
        thread = threading.Thread(target=send_broadcast, args=(message.chat.id, broadcast_text))
        thread.start()
        
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка: {str(e)}")

def send_broadcast(admin_chat_id: int, text: str):
    users = db.get_all_users()
    success_count = 0
    fail_count = 0
    
    for user_id in users:
        try:
            bot.send_message(user_id, text, parse_mode="HTML")
            success_count += 1
            time.sleep(0.1)  # Задержка для избежания лимитов
        except:
            fail_count += 1
    
    bot.send_message(
        admin_chat_id,
        messages.get('broadcast.finished', 
                    success_count=success_count, 
                    failed_count=fail_count)
    )


@bot.message_handler(func=lambda message: message.text == messages.get('buttons.check_subscription'))
def check_subscription_handler(message: types.Message):
    user_id = message.from_user.id
    
    if check_subscription(user_id):
        bot.send_message(
            message.chat.id,
            messages.get('welcome.greeting'),
            reply_markup=get_main_keyboard()
        )
    else:
        bot.send_message(
            message.chat.id,
            messages.get('subscription.not_subscribed'),
            reply_markup=get_subscription_keyboard()
        )

# Вместо @bot.callback_query_handler(func=lambda call: call.data == "support")
@bot.message_handler(func=lambda message: message.text == messages.get('buttons.support'))
def support_handler(message: types.Message):
    bot.send_message(
        message.chat.id,
        messages.get('support.message'),
        reply_markup=get_main_keyboard()
    )

# Вместо @bot.callback_query_handler(func=lambda call: call.data == "create_post")
@bot.message_handler(func=lambda message: message.text == messages.get('buttons.write_post'))
def create_post_handler(message: types.Message):
    user_id = message.from_user.id
    
    # Проверяем бан
    
    if db.is_user_banned(user_id):
        bot.send_message(
            message.chat.id,
            messages.get('moderation.user_banned_notification')
        )
        return
    
    user_states[user_id] = "waiting_for_text"
    user_data[user_id] = {}
    
    # Убираем клавиатуру при создании поста
    bot.send_message(
        message.chat.id,
        messages.get('post_creation.write_description'),
        reply_markup=types.ReplyKeyboardRemove()
    )

# Вместо @bot.callback_query_handler(func=lambda call: call.data == "skip_photo")
@bot.message_handler(func=lambda message: message.text == messages.get('buttons.skip_photo'))
def skip_photo_handler(message: types.Message):
    user_id = message.from_user.id
    if user_states.get(user_id) != "waiting_for_photo":
        return
    
    user_data[user_id]["has_photo"] = False
    user_data[user_id]["photo_file_id"] = None
    user_states[user_id] = "waiting_for_anonymity"
    
    bot.send_message(
        message.chat.id,
        messages.get('post_creation.choose_anonymity'),
        reply_markup=get_anonymity_keyboard()
    )


@bot.message_handler(func=lambda message: message.text in [messages.get('buttons.anonymous'), messages.get('buttons.leave_contact')])
def anonymity_handler(message: types.Message):
    user_id = message.from_user.id
    if user_states.get(user_id) != "waiting_for_anonymity":
        return
    
    username = message.from_user.username
    
    if message.text == messages.get('buttons.leave_contact'):
        if not username:
            bot.send_message(
                message.chat.id,
                messages.get('post_creation.no_username'),
                reply_markup=get_anonymity_keyboard()
            )
            return
        user_data[user_id]["is_anonymous"] = False
    else:
        user_data[user_id]["is_anonymous"] = True
    
    # Показываем превью поста
    show_post_preview(message.chat.id, user_id)


@bot.message_handler(func=lambda message: message.text == messages.get('buttons.yes_send'))
def confirm_post_handler(message: types.Message):
    user_id = message.from_user.id
    data = user_data.get(user_id, {})
    
    if not data:
        return
    
    # Создаем пост в базе
    post_id = db.create_post(
        user_id=user_id,
        text_content=data["text"],
        has_photo=data["has_photo"],
        photo_file_id=data.get("photo_file_id"),
        is_anonymous=data["is_anonymous"]
    )
    
    confirmation_text = messages.get('post_creation.sent_for_review', post_id=post_id)
    
    bot.send_message(
        message.chat.id, 
        confirmation_text,
        reply_markup=get_main_keyboard()
    )
    
    # Отправляем админам на модерацию
    send_to_moderation(post_id)
    
    # Очищаем данные пользователя
    user_states.pop(user_id, None)
    user_data.pop(user_id, None)


@bot.message_handler(func=lambda message: message.text == messages.get('buttons.no_restart'))
def restart_post_handler(message: types.Message):
    user_id = message.from_user.id
    user_states[user_id] = "waiting_for_text"
    user_data[user_id] = {}
    
    bot.send_message(
        message.chat.id,
        messages.get('post_creation.write_description'),
        reply_markup=types.ReplyKeyboardRemove()
    )
@bot.callback_query_handler(func=lambda call: call.data.startswith('approve_'))
def approve_handler(call):
    if not db.is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "У вас нет прав администратора")
        return
    
    # Извлекаем post_id из callback_data
    post_id = int(call.data.split('_')[1])
    admin_id = call.from_user.id
    admin_username = call.from_user.username or str(admin_id)
    
    post = db.get_post(post_id)
    if not post:
        bot.answer_callback_query(call.id, "Пост не найден")
        return
    
    # Обновляем статус поста
    db.approve_post(post_id, admin_id)
    
    # Редактируем сообщение в группе админов с помощью существующей функции
    edit_moderation_message(call.message, post, "approved", admin_username)
    
    # Убираем кнопки
    try:
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None
        )
    except:
        pass
    
    # Уведомляем пользователя
    try:
        bot.send_message(
            post["user_id"],
            messages.get('user_notifications.approved', post_id=post_id)
        )
    except:
        pass
    
    # Публикуем в канале
    publish_to_channel(post)
    
    # Отвечаем на callback
    bot.answer_callback_query(call.id, "Пост одобрен")

@bot.callback_query_handler(func=lambda call: call.data.startswith('reject_'))
def reject_handler(call):
    if not db.is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "У вас нет прав администратора")
        return
    
    # Извлекаем post_id из callback_data
    post_id = int(call.data.split('_')[1])
    admin_id = call.from_user.id
    admin_username = call.from_user.username or str(admin_id)
    
    post = db.get_post(post_id)
    if not post:
        bot.answer_callback_query(call.id, "Пост не найден")
        return
    
    # Обновляем статус поста
    db.reject_post(post_id, admin_id)
    
    # Редактируем сообщение в группе админов с помощью существующей функции
    edit_moderation_message(call.message, post, "rejected", admin_username)
    
    # Убираем кнопки
    try:
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None
        )
    except:
        pass
    
    # Уведомляем пользователя
    try:
        bot.send_message(
            post["user_id"],
            messages.get('user_notifications.rejected', post_id=post_id)
        )
    except:
        pass
    
    # Отвечаем на callback
    bot.answer_callback_query(call.id, "Пост отклонен")

def send_to_moderation_updated(post_id: int):
    post = db.get_post(post_id)
    if not post:
        return
    
    username = post["username"] if post["username"] else str(post["user_id"])
    photo_status = messages.get('status.photo_yes') if post['has_photo'] else messages.get('status.photo_no')
    contact_info = messages.get('status.contact_anonymous') if post["is_anonymous"] else f"@{username}"
    
    moderation_text = messages.get('admin.new_application',
                                  author=f"@{username} ({post['user_id']})",
                                  post_id=post_id,
                                  post_text=post['text_content'],
                                  photo_status=photo_status,
                                  contact_info=contact_info)
    
    # Получаем всех админов и отправляем каждому индивидуально
    admins = db.get_all_admins()  # Нужно добавить этот метод в Database
    
    for admin_id in admins:
        try:
            # Сохраняем post_id для каждого админа
            user_data[f"moderating_{admin_id}"] = {"post_id": post_id}
            
            if post["has_photo"]:
                bot.send_photo(
                    admin_id,
                    post["photo_file_id"],
                    caption=moderation_text,
                    reply_markup=get_moderation_keyboard(post_id)
                )
            else:
                bot.send_message(
                    admin_id,
                    moderation_text,
                    reply_markup=get_moderation_keyboard(post_id)
                )
        except Exception as e:
            print(f"Ошибка при отправке админу {admin_id}: {e}")



# Обработчики сообщений в зависимости от состояния
@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "waiting_for_text")
def handle_post_text(message: types.Message):
    user_id = message.from_user.id
    user_data[user_id]["text"] = message.text
    user_states[user_id] = "waiting_for_photo"
    
    bot.send_message(
        message.chat.id,
        messages.get('post_creation.add_photo'),
        reply_markup=get_photo_skip_keyboard()
    )

@bot.message_handler(content_types=['photo'], func=lambda message: user_states.get(message.from_user.id) == "waiting_for_photo")
def handle_post_photo(message: types.Message):
    user_id = message.from_user.id
    user_data[user_id]["has_photo"] = True
    user_data[user_id]["photo_file_id"] = message.photo[-1].file_id
    user_states[user_id] = "waiting_for_anonymity"
    
    bot.send_message(
        message.chat.id,
        messages.get('post_creation.choose_anonymity'),
        reply_markup=get_anonymity_keyboard()
    )

# Вспомогательные функции
def show_post_preview(chat_id: int, user_id: int):
    data = user_data[user_id]
    username = bot.get_chat(user_id).username if not data["is_anonymous"] else None
    
    photo_status = messages.get('status.photo_yes') if data['has_photo'] else messages.get('status.photo_no')
    contact_info = messages.get('status.contact_anonymous') if data['is_anonymous'] else f'@{username}'
    
    preview_text = messages.get('post_creation.confirmation',
                               post_text=data['text'],
                               photo_status=photo_status,
                               contact_info=contact_info)
    
    if data["has_photo"]:
        bot.send_photo(
            chat_id,
            data["photo_file_id"],
            caption=preview_text,
            reply_markup=get_confirmation_keyboard()
        )
    else:
        bot.send_message(
            chat_id,
            preview_text,
            reply_markup=get_confirmation_keyboard(),
            parse_mode='HTML',
        )

def send_to_moderation(post_id: int):
    post = db.get_post(post_id)
    if not post:
        return
    
    username = post["username"] if post["username"] else str(post["user_id"])
    photo_status = messages.get('status.photo_yes') if post['has_photo'] else messages.get('status.photo_no')
    contact_info = messages.get('status.contact_anonymous') if post["is_anonymous"] else f"@{username}"
    
    moderation_text = messages.get('admin.new_application',
                                  author=f"@{username} ({post['user_id']})",
                                  post_id=post_id,
                                  post_text=post['text_content'],
                                  photo_status=photo_status,
                                  contact_info=contact_info)
    
    # Используем group_username из конфига для отправки админам
    admin_chat = f"@{settings.group_username}"
    
    try:
        if post["has_photo"]:
            bot.send_photo(
                admin_chat,
                post["photo_file_id"],
                caption=moderation_text,
                reply_markup=get_moderation_keyboard(post_id)
            )
        else:
            bot.send_message(
                admin_chat,
                moderation_text,
                reply_markup=get_moderation_keyboard(post_id)
            )
    except Exception as e:
        print(f"Ошибка при отправке на модерацию: {e}")

def edit_moderation_message(message: types.Message, post: dict, status: str, admin_username: str):
    username = post["username"] if post["username"] else str(post["user_id"])
    photo_status = messages.get('status.photo_yes') if post['has_photo'] else messages.get('status.photo_no')
    contact_info = messages.get('status.contact_anonymous') if post["is_anonymous"] else f"@{username}"
    
    if status == "approved":
        new_text = messages.get('admin.application_approved',
                               author=f"@{username} ({post['user_id']})",
                               post_id=post['id'],
                               post_text=post['text_content'],
                               photo_status=photo_status,
                               contact_info=contact_info,
                               admin_username=admin_username)
    else:  # rejected
        new_text = messages.get('admin.application_rejected',
                               author=f"@{username} ({post['user_id']})",
                               post_id=post['id'],
                               post_text=post['text_content'],
                               photo_status=photo_status,
                               contact_info=contact_info,
                               admin_username=admin_username)
    
    try:
        if message.photo:
            bot.edit_message_caption(
                new_text,
                message.chat.id,
                message.message_id
            )
        else:
            bot.edit_message_text(
                new_text,
                message.chat.id,
                message.message_id,
            )
    except:
        pass

def publish_to_channel(post: dict):
    channel_chat_id = f"@{settings.channel_username}"
    username = post["username"] if not post["is_anonymous"] else None
    contact_info = f"@{username}" if username else messages.get('status.contact_anonymous')
    
    publish_text = messages.get('channel_post.template',
                               post_text=post['text_content'],
                               author_info=contact_info)
    
    try:
        if post["has_photo"]:
            bot.send_photo(channel_chat_id, post["photo_file_id"], caption=publish_text, parse_mode="HTML")
        else:
            bot.send_message(channel_chat_id, publish_text, parse_mode="HTML")
    except Exception as e:
        print(f"Ошибка при публикации в канал: {e}")

while True:
    for i in settings.admin_ids:
        db.add_admin(i, added_by="auto_add_in_script")
        print(i)
    try:
        bot.polling()
    except Exception as e:
        print(e)