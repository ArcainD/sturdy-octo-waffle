from vk_api.longpoll import VkEventType
from msg import longpoll, write_msg
from vk_bot import VkBot

vkbot = VkBot()

for event in longpoll.listen():
    if event.type == VkEventType.MESSAGE_NEW:

        if event.to_me:
            request = event.text

            if request.lower() == "привет":
                write_msg(event.user_id, f"Привет, {vkbot.get_user_name(event.user_id)}. Если хочешь подыскать себе(или кому-то) пару, то я могу с этим помочь!")

            elif request == "пока":
                write_msg(event.user_id, "Пока((")
            elif request == 'Для себя':
                write_msg(event.user_id, f'')
            elif request == 'Для другого':
                write_msg(event.user_id, 'Введи VK id человека которому хочешь подыскать пару')
            else:
                write_msg(event.user_id, "Ой-ой, напиши мне 'Привет' если хочешь пообщаться")
