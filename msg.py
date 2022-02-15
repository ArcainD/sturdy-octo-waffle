import vk_api
from vk_api.utils import get_random_id
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.longpoll import VkLongPoll

token = 'd42b18cefab46f70a6307f09cae96af91a432c514e443384ea0ffccf6529f2055148b7bf68a7a5651c177'

vk = vk_api.VkApi(token=token)
longpoll = VkLongPoll(vk)

keyboard = VkKeyboard(one_time=True, inline=False)

keyboard.add_button('Для себя', color=VkKeyboardColor.PRIMARY)
keyboard.add_line()
keyboard.add_button('Для другого', color=VkKeyboardColor.SECONDARY)


def write_msg(user_id, message):
    vk.method('messages.send', {'user_id': user_id, 'message': message,  'random_id': get_random_id(), 'keyboard': keyboard.get_keyboard()})
