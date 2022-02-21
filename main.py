from tokens import GROUP_TOKEN, PERSONAL_TOKEN, GROUP_ID, APP_ID
from tokens import DB_LOGIN, DB_PASSWORD, DB_DRIVER, DB_HOST, DB_PORT, DB_NAME
from classes.vk_bot import VKinderBot


if __name__ == '__main__':
    server = VKinderBot(group_token=GROUP_TOKEN,
                        person_token=PERSONAL_TOKEN,
                        group_id=GROUP_ID,
                        app_id=APP_ID,
                        db_name=DB_NAME,
                        db_login=DB_LOGIN,
                        db_password=DB_PASSWORD,
                        db_driver=DB_DRIVER,
                        db_host=DB_HOST,
                        db_port=DB_PORT,
                        debug_mode=True)
    server.start()
