import sys
from datetime import datetime
from random import randrange
from time import sleep
import requests
import urllib3
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.keyboard import VkKeyboard
from vk_api.utils import get_random_id
from classes.vkapi import VKinderClient, RATINGS
from classes.vkapi import get_users_ratings_counts, format_city_name
from classes.vkapi import get_dict_key_by_value, log, break_str
from classes.vkapi import last_seen
from classes.vkapi_cons import LOVE_STATUSES, SEXES
from classes.vk_bot_cons import PHRASES, STATUSES
from classes.vk_bot_cons import MAX_MSG_SIZE, COMMANDS
from classes.vkapi_client import VkApiClient
from classes.db_client import VKinderDb


class VKinderBot:

    def __init__(self, group_token, person_token, group_id, app_id, db_name,
                 db_login, db_password, db_driver, db_host, db_port,
                 retry_timeout=1, retry_attempts=sys.maxsize,
                 debug_mode=False):
        self.client_activity_timeout = 300
        self.debug_mode = debug_mode
        self.clients_pool = {}
        self.group_id = group_id
        self.cmd = Commands(COMMANDS)
        self.countries = []
        self.rebuild_tables = False
        self.retry_timeout = retry_timeout
        self.retry_attempts = retry_attempts
        self.vk_personal = VkApiClient(person_token, app_id,
                                       debug_mode=debug_mode)
        self.db = VKinderDb(db_name, db_login, db_password,
                            db_driver=db_driver, db_host=db_host,
                            db_port=db_port, debug_mode=debug_mode)
        self.__initialized = self.vk_personal.is_initialized and \
            self.db.is_initialized
        self.vk_group = vk_api.VkApi(token=group_token)

        try:
            self.long_poll = VkBotLongPoll(self.vk_group, self.group_id)
            self.vk_api = self.vk_group.get_api()

        except BaseException as e:
            self.__initialized = False
            log(f'{type(self).__name__} init failed: {e.error["error_msg"]}',
                self.debug_mode)

        if self.__initialized:
            log(f'{type(self).__name__} initialised successfully',
                self.debug_mode)

    def send_typing_activity(self, client: VKinderClient):
        self.vk_api.messages.setActivity(type='typing', peer_id=client.vk_id)

    def send_msg(self, client: VKinderClient, message: str,
                 attachment: str = None, keyboard=None):

        for msg in break_str(message, max_size=MAX_MSG_SIZE):
            self.vk_api.messages.send(peer_id=client.vk_id,
                                      message=msg,
                                      attachment=attachment,
                                      random_id=get_random_id(),
                                      keyboard=keyboard)

    def get_client(self, vk_id) -> VKinderClient:
        client = self.clients_pool.get(vk_id, None)

        if client:
            lag = int((datetime.now() - client.last_contact).total_seconds())
            if lag > self.client_activity_timeout:
                self.do_send_to_start_after_absence(client)

        else:
            user = self.vk_personal.get_users(vk_id)[0]
            client = VKinderClient(user)
            self.db.save_client(client)
            self.clients_pool.update({user.vk_id: client})
            self.do_greet_client(client)

        return client

    def start(self):
        retries = 0

        if not self.__initialized:
            log(f'Can\'t start: {type(self).__name__} not initialized',
                self.debug_mode)
            return

        while True and retries < self.retry_attempts:

            try:
                retries += 1
                log(f'Listening for messages in group {self.group_id}'
                    f'...(retry #{retries})', self.debug_mode)
                self.long_poll.update_longpoll_server()
                for event in self.long_poll.listen():
                    if event.type == VkBotEventType.MESSAGE_NEW:
                        client = self.get_client(
                            str(event.object.message['from_id'])
                        )
                        msg = event.object.message['text']
                        log(f'[{client.fname} {client.lname}] typed "{msg}"',
                            self.debug_mode)
                        msg = msg.lower()
                        if msg in self.cmd.get('quit') and \
                                client.status != STATUSES['has_contacted']:
                            self.do_say_goodbye(client)
                            continue
                        if msg == 'test':
                            client.reset_search()
                            client.search.sex_id = randrange(0, 2, 1)
                            client.search.status_id = randrange(1, 8, 1)
                            client.search.city_id = 1
                            client.search.city_name = 'Москва'
                            client.search.min_age = randrange(0, 60, 1)
                            client.search.max_age = randrange(
                                client.search.min_age, 127, 1
                            )
                            client.rating_filter = RATINGS['new']
                            self.do_users_search(client)
                            continue
                        if client.status in (STATUSES['invited'],
                                             STATUSES['has_contacted']) and \
                                (msg in self.cmd.get('yes') or
                                 msg in self.cmd.get('new search')):
                            self.do_start_search_creating(client)
                        elif client.status in (STATUSES['invited'],
                                               STATUSES['has_contacted']) and \
                                msg in self.cmd.get('show history'):
                            self.do_show_search_history(client)
                        elif client.status in (STATUSES['invited'],
                                               STATUSES['has_contacted']) and \
                                (msg in self.cmd.get('liked') or msg in
                                 self.cmd.get('disliked') or msg in
                                 self.cmd.get('banned')):
                            self.do_show_rated_users(msg, client)
                        elif client.status in (STATUSES['invited'],
                                               STATUSES['has_contacted']) and \
                                msg in self.cmd.get('no'):
                            self.do_say_goodbye(client)
                        elif client.status == STATUSES['has_contacted']:
                            self.do_propose_start_search(client)
                        elif client.status == \
                                STATUSES['search_history_input_wait'] and \
                                msg in self.cmd.get('back'):
                            self.do_propose_start_search(client)
                        elif client.status ==\
                                STATUSES['search_history_input_wait']:
                            self.on_search_history_choose(msg, client)
                        elif client.status == STATUSES['country_input_wait'] \
                                and msg in self.cmd.get('back'):
                            self.do_start_search_creating(client)
                        elif client.status == STATUSES['country_input_wait']:
                            self.on_country_name_input(msg, client)
                        elif client.status == STATUSES['country_choose_wait'] \
                                and msg in self.cmd.get('back'):
                            self.do_propose_country_name_input(client)
                        elif client.status == STATUSES['country_choose_wait']:
                            self.on_country_name_choose(msg, client)
                        elif client.status == STATUSES['city_input_wait'] and \
                                msg in self.cmd.get('back'):
                            self.do_propose_start_search(client)
                        elif client.status == STATUSES['city_input_wait'] and \
                                msg in self.cmd.get('country'):
                            self.do_propose_country_name_input(client)
                        elif client.status == STATUSES['city_input_wait']:
                            self.do_propose_city_name_choose(msg, client)
                        elif client.status == STATUSES['city_choose_wait'] \
                                and msg in self.cmd.get('back'):
                            self.do_start_search_creating(client)
                        elif client.status == STATUSES['city_choose_wait']:
                            self.on_city_name_choose(msg, client)
                        elif client.status == STATUSES['sex_choose_wait'] and \
                                msg in self.cmd.get('back'):
                            self.do_start_search_creating(client)
                        elif client.status == STATUSES['sex_choose_wait']:
                            self.on_sex_choose(msg, client)
                        elif client.status == STATUSES['status_choose_wait'] \
                                and msg in self.cmd.get('back'):
                            self.do_propose_sex_choose(client)
                        elif client.status == STATUSES['status_choose_wait']:
                            self.on_status_choose(msg, client)
                        elif client.status == STATUSES['min_age_input_wait'] \
                                and msg in self.cmd.get('back'):
                            self.do_propose_status_choose(client)
                        elif client.status == STATUSES['min_age_input_wait']:
                            self.on_min_age_enter(msg, client)
                        elif client.status == STATUSES['max_age_input_wait'] \
                                and msg in self.cmd.get('back'):
                            self.do_propose_min_age_enter(client)
                        elif client.status == STATUSES['max_age_input_wait']:
                            self.on_max_age_enter(msg, client)
                        elif client.status == STATUSES['decision_wait'] and \
                                msg in self.cmd.get('back'):
                            if client.rating_filter == RATINGS['new']:
                                self.do_propose_min_age_enter(client)
                            else:
                                self.do_propose_start_search(client)
                        elif client.status == STATUSES['decision_wait']:
                            self.on_decision_made(msg, client)
                        else:
                            self.do_inform_about_unknown_command(client)

            except (requests.exceptions.ConnectionError,
                    requests.exceptions.ReadTimeout,
                    urllib3.exceptions.ReadTimeoutError):

                if retries < self.retry_attempts:
                    log(f'Error in connection. Retry in {self.retry_timeout} '
                        f'seconds...', self.debug_mode)
                    sleep(self.retry_timeout)
                else:
                    log(f'Error in connection. Bot shutting down.',
                        self.debug_mode)

    def on_decision_made(self, msg, client: VKinderClient):
        if msg in self.cmd.get('yes'):
            client.active_user.rating_id = RATINGS['liked']
        elif msg in self.cmd.get('no'):
            client.active_user.rating_id = RATINGS['disliked']
        elif msg in self.cmd.get('ban'):
            client.active_user.rating_id = RATINGS['banned']
        else:
            self.do_inform_about_unknown_command(client)
            return

        self.db.save_user_rating(client)
        self.do_show_next_user(client)

    def do_show_next_user(self, client: VKinderClient):
        self.send_typing_activity(client)
        client.status = STATUSES['decision_wait']
        client.active_user = client.get_next_user()
        if not client.active_user:
            self.do_send_to_start_due_to_reach_end(client)
            self.do_propose_start_search(client)
            return
        client.active_user.photos = \
            self.vk_personal.get_user_photos(client.active_user.vk_id)
        if not client.active_user.photos:
            client.active_user.photos = \
                self.vk_personal.get_user_photos(client.active_user.vk_id,
                                                 album_id='wall')
        photos = [f'photo{photo.owner_id}_{photo.id}'
                  for photo in client.active_user.photos]
        photos_str = ','.join(photos)
        log(f'[{client.fname} {client.lname}] Showing user: '
            f'{client.active_user.fname} {client.active_user.lname} with '
            f'{len(client.active_user.photos)} photos', self.debug_mode)
        age_str = f', возраст: {client.active_user.age}' \
            if client.active_user.age else ''
        user_info = f'{client.active_user.fname} {client.active_user.lname} '
        user_info += f'({client.active_user.city_name}{age_str})'
        user_info += f'{last_seen(client.active_user.last_seen_time)}\n' \
                     f'https://vk.com/{client.active_user.domain}'
        keyboard = self.cmd.kb(['yes', 'no', 'ban', None, 'back', 'quit'])
        self.send_msg(client, user_info, attachment=photos_str,
                      keyboard=keyboard)
        self.send_msg(client, PHRASES['do_you_like_it'])
        self.db.save_photos(client)

    def do_show_rated_users(self, msg, client: VKinderClient):
        client.status = STATUSES['loading_users']
        if msg in self.cmd.get('banned'):
            client.rating_filter = RATINGS['banned']
        elif msg in self.cmd.get('disliked'):
            client.rating_filter = RATINGS['disliked']
        else:
            client.rating_filter = RATINGS['liked']
        self.db.load_users_from_db(client)
        if client.found_users:
            self.do_show_next_user(client)
        else:
            self.send_msg(client, PHRASES['no_peoples_found'])
            self.do_propose_start_search(client)

    def do_users_search(self, client: VKinderClient):
        client.status = STATUSES['loading_users']
        params = PHRASES['city_x_sex_x_status_x_age_xx'].format(
            client.search.city_name, SEXES[client.search.sex_id],
            LOVE_STATUSES[client.search.status_id], client.search.min_age,
            client.search.max_age)
        self.send_msg(client, f'{PHRASES["started_search_peoples"]}\n'
                              f'({params})')
        self.send_typing_activity(client)
        self.db.save_search(client)
        client.found_users = self.vk_personal.search_users(
            city_id=client.search.city_id,
            sex_id=client.search.sex_id,
            love_status_id=client.search.status_id,
            age_from=client.search.min_age,
            age_to=client.search.max_age
        )
        client.found_users = [user for user in client.found_users
                              if not user.is_closed and user.last_seen_time]
        client.found_users.sort(key=lambda x: x.last_seen_time, reverse=True)
        if client.found_users:
            self.db.load_users_ratings_from_db(client)
            ratings_sum = get_users_ratings_counts(client.found_users)
            self.send_msg(client,
                          PHRASES['found_x_peoples_x_new_x_'
                                  'liked_x_disliked_x_banned'].format(
                              len(client.found_users), ratings_sum['new'],
                              ratings_sum['liked'], ratings_sum['disliked'],
                              ratings_sum['banned']
                          ))
            if ratings_sum['new'] > 0:
                self.db.save_users(client)
                self.do_show_next_user(client)
            else:
                self.send_msg(client, PHRASES['no_new_peoples_found'])
                self.do_propose_start_search(client)
        else:
            self.send_msg(client, PHRASES['no_peoples_found'])
            self.do_propose_start_search(client)

    def on_max_age_enter(self, max_age, client: VKinderClient):
        result = None
        try:
            max_age = int(max_age) + 1
            if 0 < max_age <= 128:
                result = max_age
        except ValueError:
            pass
        if result:
            if client.search.min_age > result - 1:
                self.send_msg(client, PHRASES['minimal_age_more_maximal_age'])
                self.do_propose_min_age_enter(client)
            else:
                client.search.max_age = result - 1
                self.send_msg(client,
                              PHRASES['you_chosen_min_age_x_and'
                                      '_max_age_x'].format(
                                  client.search.min_age,
                                  client.search.max_age
                              ))
                self.do_users_search(client)
        else:
            self.send_msg(client, PHRASES['error_in_age'])
            self.do_propose_min_age_enter(client)

    def do_propose_max_age_enter(self, client: VKinderClient):
        client.status = STATUSES['max_age_input_wait']
        keyboard = self.cmd.kb(['back', 'quit'])
        self.send_msg(client,
                      PHRASES['enter_max_age_from_x_127'].format
                      (client.search.min_age), keyboard=keyboard
                      )

    def on_min_age_enter(self, min_age, client: VKinderClient):
        result = None
        try:
            min_age = int(min_age) + 1
            if 0 < min_age <= 128:
                result = min_age
        except ValueError:
            pass
        if result:
            client.search.min_age = result - 1
            self.do_propose_max_age_enter(client)
        else:
            self.send_msg(client, PHRASES['error_in_age'])
            self.do_propose_min_age_enter(client)

    def do_propose_min_age_enter(self, client: VKinderClient):
        client.status = STATUSES['min_age_input_wait']
        keyboard = self.cmd.kb(['back', 'quit'])
        self.send_msg(client,
                      PHRASES['enter_min_age_from_0_127'],
                      keyboard=keyboard
                      )

    def on_status_choose(self, status_id, client: VKinderClient):
        result = None
        try:
            status_id = int(status_id)
            if 0 < status_id <= len(LOVE_STATUSES):
                result = status_id
        except ValueError:
            pass
        if result:
            client.search.status_id = result
            self.send_msg(client,
                          PHRASES['you_chosen_love_status_x'].format
                          (LOVE_STATUSES[result])
                          )
            self.do_propose_min_age_enter(client)
        else:
            self.send_msg(client, PHRASES['no_such_love_status_in_list'])
            self.do_propose_status_choose(client)

    def do_propose_status_choose(self, client: VKinderClient):
        client.status = STATUSES['status_choose_wait']
        statuses = [f'{status_id}. {status}' for status_id, status
                    in LOVE_STATUSES.items()]
        keyboard = self.cmd.kb(['back', 'quit'])
        self.send_msg(client, '\n'.join(statuses), keyboard=keyboard)
        self.send_msg(client, PHRASES['choose_love_status_number'])

    def on_sex_choose(self, sex, client: VKinderClient):
        result = None
        try:
            if sex in self.cmd.get('woman'):
                result = get_dict_key_by_value(SEXES, 'женщина') + 1
            elif sex in self.cmd.get('man'):
                result = get_dict_key_by_value(SEXES, 'мужчина') + 1
            elif sex in self.cmd.get('anybody'):
                result = get_dict_key_by_value(SEXES, 'любой') + 1
            else:
                sex = int(sex) + 1
                if 0 < sex <= len(SEXES):
                    result = sex
        except ValueError:
            pass
        if result:
            client.search.sex_id = result - 1
            self.send_msg(client,
                          PHRASES['you_chosen_sex_x'].format
                          (SEXES[client.search.sex_id])
                          )
            self.do_propose_status_choose(client)
        else:
            self.send_msg(client, PHRASES['no_such_sex_in_list'])
            self.do_propose_sex_choose(client)

    def do_propose_sex_choose(self, client: VKinderClient):
        client.status = STATUSES['sex_choose_wait']
        sexes = [f'{sex_id}. {sex}' for sex_id, sex in SEXES.items()]
        keyboard = self.cmd.kb(['woman', 'man', 'anybody',
                                None, 'back', 'quit'])
        self.send_msg(client, '\n'.join(sexes), keyboard=keyboard)
        self.send_msg(client, PHRASES['choose_sex_number'])

    def on_city_name_choose(self, city, client: VKinderClient):
        result = None
        try:
            city = int(city)
            if 0 < city <= len(client.found_cities):
                result = city
        except ValueError:
            pass
        if result:
            client.search.city_id = client.found_cities[result - 1].id
            client.search.city_name = client.found_cities[result - 1].title
            self.send_msg(client, PHRASES['you_chosen_city_x'].format(
                client.search.city_name))
            self.do_propose_sex_choose(client)
        else:
            self.send_msg(client, PHRASES['no_such_city_in_list'])
            self.do_propose_city_name_choose('', client)

    def do_propose_city_name_choose(self, city, client: VKinderClient):
        client.status = STATUSES['city_choose_wait']
        self.send_typing_activity(client)
        if city:
            client.found_cities = self.vk_personal.search_cities(
                country_id=client.country_id,
                city_name=city
            )
        cities = [f'{index}. {format_city_name(city)}' for index, city
                  in enumerate(client.found_cities, 1)]
        if cities:
            keyboard = self.cmd.kb(['back', 'quit'])
            self.send_msg(client, '\n'.join(cities), keyboard=keyboard)
            self.send_msg(client, PHRASES['choose_city_number'])
        else:
            self.send_msg(client, PHRASES['no_such_city_name'])
            self.do_start_search_creating(client)

    def on_country_name_choose(self, country_id, client: VKinderClient):
        result = None
        try:
            country_id = int(country_id)
            if 0 < country_id <= len(client.found_countries):
                result = country_id
        except ValueError:
            pass
        if result:
            client.country_id = client.found_countries[result - 1].id
            client.country_name = client.found_countries[result - 1].title
            self.db.save_client(client, force_country_update=True)
            self.send_msg(client, PHRASES['you_chosen_country_x'].format(
                client.country_name))
            self.do_start_search_creating(client)
        else:
            self.send_msg(client, PHRASES['no_such_country_in_list'])

    def on_country_name_input(self, country_name, client: VKinderClient):
        client.status = STATUSES['country_choose_wait']
        self.send_typing_activity(client)
        if not self.countries:
            self.countries = self.vk_personal.get_countries()
        client.found_countries = [country for country in self.countries
                                  if country.title.lower().find(country_name)
                                  > -1]
        countries = [f'{index}. {country.title}' for index, country
                     in enumerate(client.found_countries, 1)]
        if countries:
            keyboard = self.cmd.kb(['back', 'quit'])
            self.send_msg(client, '\n'.join(countries), keyboard=keyboard)
            self.send_msg(client, PHRASES['choose_country_number'])
        else:
            self.send_msg(client, PHRASES['no_such_city_name'])
            self.do_propose_country_name_input(client)

    def do_propose_country_name_input(self, client: VKinderClient):
        client.status = STATUSES['country_input_wait']
        keyboard = self.cmd.kb(['back', 'quit'])
        self.send_msg(client, PHRASES['enter_country_name'], keyboard=keyboard)

    def do_start_search_creating(self, client: VKinderClient):
        client.status = STATUSES['city_input_wait']
        # revert to default for new search
        client.rating_filter = RATINGS['new']
        client.reset_search()
        keyboard = self.cmd.kb(['country', None, 'back', 'quit'])
        self.send_msg(client, PHRASES['enter_city_name_in_x'].format(
            client.country_name), keyboard=keyboard)

    def on_search_history_choose(self, history_id, client: VKinderClient):
        result = None
        try:
            history_id = int(history_id)
            if 0 < history_id <= len(client.searches):
                result = history_id
        except ValueError:
            pass
        if result:
            client.search = client.searches[result - 1]
            self.do_users_search(client)
        else:
            self.send_msg(client, PHRASES['no_such_history_in_list'])
            self.do_show_search_history(client)

    def do_show_search_history(self, client: VKinderClient):
        client.status = STATUSES['search_history_input_wait']
        client.rating_filter = RATINGS['new']
        searches = self.db.load_searches(client)
        client.searches = searches
        history = []
        for index, searches in enumerate(searches, 1):
            history.append(str(index) + '. ' +
                           PHRASES['x_x_x_from_x_to_x'].format(
                               searches.city_name, SEXES[searches.sex_id],
                               LOVE_STATUSES[searches.status_id],
                               searches.min_age, searches.max_age
                           ))
        if history:
            keyboard = self.cmd.kb(['back', 'quit'])
            self.send_msg(client, '\n'.join(history), keyboard=keyboard)
            self.send_msg(client, PHRASES['choose_search_history_number'])
        else:
            self.send_msg(client, PHRASES['no_search_history'])
            self.do_propose_start_search(client)

    def do_propose_start_search(self, client: VKinderClient):
        client.status = STATUSES['invited']
        client.rating_filter = RATINGS['new']
        if len(client.searches) == 0:
            keyboard = self.cmd.kb(['yes', 'no'])
            self.send_msg(client, PHRASES['do_you_want_to_find_pair'],
                          keyboard=keyboard)
        else:
            keyboard = self.cmd.kb(['new search', 'show history', None,
                                    'liked', 'disliked', 'banned',
                                    None, 'quit'])
            self.send_msg(client, PHRASES['you_have_search_history'],
                          keyboard=keyboard)

    def do_greet_client(self, client: VKinderClient):
        self.send_msg(client, PHRASES['greetings_x'].format(client.fname))

    def do_send_to_start_after_absence(self, client: VKinderClient):
        client.status = STATUSES['has_contacted']
        self.send_msg(client,
                      PHRASES['sorry_x_you_was_absent_for_x_seconds'].format(
                          client.fname, self.client_activity_timeout
                      ))

    def do_send_to_start_due_to_reach_end(self, client: VKinderClient):
        client.status = STATUSES['has_contacted']
        self.send_msg(client, PHRASES['well_lets_start_again'])

    def do_inform_about_unknown_command(self, client: VKinderClient):
        client.last_contact = datetime.now()
        self.send_msg(client, PHRASES['sorry_i_dont_understand_you'])

    def do_say_goodbye(self, client: VKinderClient):
        if len(client.searches) == 0:
            keyboard = self.cmd.kb(['yes', 'no'])
            self.send_msg(client, PHRASES['goodbye_x'].format(client.fname),
                          keyboard=keyboard)
        else:
            keyboard = self.cmd.kb(['new search', 'show history', None,
                                    'liked', 'disliked', 'banned', None,
                                    'quit'])
            self.send_msg(client, PHRASES['goodbye_x'].format(client.fname),
                          keyboard=keyboard)
        self.clients_pool.pop(client.vk_id)


class Commands:
    def __init__(self, commands):
        self._commands = commands
        self._keyboard = VkKeyboard()

    def kb(self, params=None, one_time=False):
        if not params:
            self._keyboard = VkKeyboard()
            return self._keyboard.get_empty_keyboard()
        self._keyboard = VkKeyboard(one_time=one_time)
        for param in params:
            if param is None:
                self._keyboard.add_line()
                continue
            btn = self.get(param, True)
            self._keyboard.add_button(btn[0], color=btn[1])
        return self._keyboard.get_keyboard()

    def get(self, command_name, make_button=False):
        command = self._commands.get(command_name, None)
        if not command:
            return []
        if make_button:
            return [command[0][0], command[1]]
        return [x.lower() for x in command[0]]
