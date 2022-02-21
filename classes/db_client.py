import json
from classes.vkapi import VKinderClient, VKinderSearch, log, clear_db
import sqlalchemy as sa
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy import func, delete, and_, not_
from classes.db import Clients, Base, Searches, Users
from classes.db import ClientsUsers, Photos


class VKinderDb:

    def __init__(self, db_name, db_login, db_password, db_driver='postgresql',
                 db_host='localhost', db_port=5432, debug_mode=False):
        self.debug_mode = debug_mode
        self.__sqlalchemy = sa
        self.search_history_limit = 10
        self.rebuild = self.load_config()['rebuild_tables']
        try:
            self.__engine = sa.create_engine(f'{db_driver}://{db_login}:'
                                             f'{db_password}@{db_host}:'
                                             f'{db_port}/{db_name}')
            self.__engine.connect().close()
            self.__session = sessionmaker(bind=self.__engine)()
            log(f'{type(self).__name__} successfully connected to DB',
                self.debug_mode)
            if self.rebuild:
                log(f'Rebuilding tables...', self.debug_mode)
                clear_db(sa, self.__engine)
                Base.metadata.create_all(self.__engine)
            self.__initialized = True
        except OperationalError as e:
            log(f'{type(self).__name__} unable connect to DB: {e}',
                self.debug_mode)
            self.__initialized = False
            self.__session = None

    @property
    def is_initialized(self):
        return self.__initialized

    @staticmethod
    def load_config(filename='options.cfg'):
        rebuild_key = 'rebuild_tables'
        rebuild_default_value = False
        options_default = {rebuild_key: rebuild_default_value}
        result = dict()
        try:
            with open(filename, encoding='utf-8', mode='r+') as file:
                options = json.load(file)
                rebuild_value = options.get(rebuild_key, False)
                if not rebuild_value == rebuild_default_value:
                    result.update({rebuild_key: rebuild_value})
                else:
                    result.update({rebuild_key: rebuild_default_value})
                options_default[rebuild_key] = rebuild_default_value
        except json.decoder.JSONDecodeError or FileNotFoundError:
            result = options_default
        finally:
            with open(filename, encoding='utf-8', mode='w+') as file:
                json.dump(options_default, file)
        return result

    def load_client_from_db(self, vk_id):
        log(f'Loading client info from DB', is_debug_msg=self.debug_mode)
        client = self.__session.query(Clients).filter(
            Clients.vk_id == vk_id).first()
        if client:
            return client.convert_to_apiuser()

    def save_client(self, client: VKinderClient, force_country_update=False):
        log(f'[{client.fname} {client.lname}] Saving client\'s info to DB',
            is_debug_msg=self.debug_mode)
        client_db = self.__session.query(Clients).filter(
            Clients.vk_id == client.vk_id).first()
        if not client_db:
            client_db = Clients()
        client_db.vk_id = client.vk_id
        client_db.fname = client.fname
        client_db.lname = client.lname
        client_db.domain = client.domain
        if not client_db.id or force_country_update:
            client_db.country_id = client.country_id
            client_db.country_name = client.country_name
        elif client_db.id:
            client.country_id = client_db.country_id
            client.country_name = client_db.country_name
        client_db.city_id = client.city_id
        client_db.city_name = client.city_name
        client_db.hometown = client.hometown
        client_db.birth_date = client.birth_date
        client_db.birth_day = client.birth_day
        client_db.birth_month = client.birth_month
        client_db.birth_year = client.birth_year
        client_db.sex_id = client.sex_id
        client_db.updated = client.last_contact
        self.__session.add(client_db)
        self.__session.commit()
        client.db_id = client_db.id
        client.searches = self.load_searches(client)

    def load_searches(self, client: VKinderClient) -> list[VKinderSearch]:
        log(f'[{client.fname} {client.lname}] Loading all client\'s searches'
            f' from DB', is_debug_msg=self.debug_mode)
        result = self.__session.query(Searches).filter(
            Searches.client_id == client.db_id).order_by(
            Searches.updated.desc()).all()
        return result

    def save_search(self, client: VKinderClient):
        log(f'[{client.fname} {client.lname}] Saving client\'s search to DB',
            is_debug_msg=self.debug_mode)
        if client.search.id:
            return
        search_history = self.__session.query(Searches.id).filter(
            Searches.client_id == client.db_id).order_by(
            Searches.updated.desc()).limit(self.search_history_limit - 1).all()
        delete_expr = delete(Searches).where(and_(not_(
            Searches.id.in_(search_history)),
            Searches.client_id == client.db_id))
        self.__session.execute(delete_expr)
        self.__session.commit()
        search = Searches(client_id=client.db_id,
                          min_age=client.search.min_age,
                          max_age=client.search.max_age,
                          sex_id=client.search.sex_id,
                          status_id=client.search.status_id,
                          city_id=client.search.city_id,
                          city_name=client.search.city_name,
                          updated=func.now())
        self.__session.add(search)
        self.__session.commit()

        client.search.id = search.id
        client.searches.append(client.search)

    def save_users(self, client: VKinderClient):
        if not client.found_users:
            log(f'[{client.fname} {client.lname}] No users to save in DB',
                is_debug_msg=self.debug_mode)
            return
        log(f'[{client.fname} {client.lname}] Saving users info to DB',
            is_debug_msg=self.debug_mode)
        search = self.__session.query(Searches).filter(
            Searches.id == client.search.id).first()
        vk_ids = [client.vk_id for client in client.found_users]
        users = self.__session.query(Users).filter(
            Users.vk_id.in_(vk_ids)).all()
        matches = {user.vk_id: user for user in users}
        users_list = []
        for found_user in client.found_users:
            user = matches.get(found_user.vk_id, Users())
            user.vk_id = found_user.vk_id
            user.fname = found_user.fname
            user.lname = found_user.lname
            user.domain = found_user.domain
            user.country_id = found_user.country_id
            user.country_name = found_user.country_name
            user.city_id = found_user.city_id
            user.city_name = found_user.city_name
            user.hometown = found_user.hometown
            user.birth_date = found_user.birth_date
            user.birth_day = found_user.birth_day
            user.birth_month = found_user.birth_month
            user.birth_year = found_user.birth_year
            user.sex_id = found_user.sex_id
            user.updated = func.now()
            user.searches.append(search)
            users_list.append(user)
        self.__session.add_all(users_list)
        self.__session.commit()

    def save_user_rating(self, client: VKinderClient):
        log(f'[{client.fname} {client.lname}] Saving user rating to DB',
            is_debug_msg=self.debug_mode)
        client_db = self.__session.query(Clients).filter(
            Clients.vk_id == client.vk_id).first()
        user_db = self.__session.query(Users).filter(
            Users.vk_id == client.active_user.vk_id).first()
        clients_user = self.__session.query(ClientsUsers).filter(
            and_(ClientsUsers.client_id == client_db.id,
                 ClientsUsers.user_id == user_db.id)).first()
        if not clients_user:
            clients_user = ClientsUsers(client_id=client_db.id,
                                        user_id=user_db.id,
                                        rating_id=client.active_user.rating_id)
        else:
            clients_user.rating_id = client.active_user.rating_id
            clients_user.updated = func.now()
        self.__session.add(clients_user)
        self.__session.commit()

    def save_photos(self, client: VKinderClient):
        log(f'[{client.fname} {client.lname}] Saving photo\'s info to DB',
            is_debug_msg=self.debug_mode)
        user_db = self.__session.query(Users).filter(
            Users.vk_id == client.active_user.vk_id).first()
        self.__session.query(Photos).filter(and_(
            Photos.owner_id == user_db.id)).delete()
        self.__session.commit()
        photos_list = []
        for photo in client.active_user.photos:
            photo_db = Photos(url=photo.url,
                              likes_count=photo.likes_count,
                              comments_count=photo.comments_count,
                              reposts_count=photo.reposts_count,
                              photo_id=photo.id,
                              owner_db_id=user_db.id)
            photos_list.append(photo_db)
        self.__session.add_all(photos_list)
        self.__session.commit()

    def load_users_ratings_from_db(self, client: VKinderClient):
        vk_ids = [client.vk_id for client in client.found_users]
        users_db = self.__session.query(
            Users.vk_id, ClientsUsers.rating_id).join(ClientsUsers).filter(
            Users.vk_id.in_(vk_ids)).filter(
            ClientsUsers.client_id == client.db_id).all()
        for users in users_db:
            for found_user in client.found_users:
                if found_user.vk_id == users[0]:
                    found_user.rating_id = users[1]

    def load_users_from_db(self, client: VKinderClient):
        log(f'[{client.fname} {client.lname}] '
            f'Loading users from DB with rating {client.rating_filter}',
            is_debug_msg=self.debug_mode)
        users = self.__session.query(Users).join(ClientsUsers).filter(
            ClientsUsers.client_id == client.db_id).filter(
            ClientsUsers.rating_id == client.rating_filter).all()
        client.found_users = []
        for user in users:
            client.found_users.append(user.convert_to_apiuser(
                client.rating_filter))
        log(f'[{client.fname} {client.lname}] Loaded '
            f'{len(client.found_users)} users from DB',
            is_debug_msg=self.debug_mode)
