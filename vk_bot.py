import requests
import bs4


class VkBot:

    def get_user_name(self, user_id):
        request = requests.get(f'https://vk.com/id{user_id}')
        request.raise_for_status()
        text = request.text
        soup = bs4.BeautifulSoup(text, 'html.parser')
        user_name = self._clean_all_tag(soup.findAll('title')[0])
        return user_name.split()[0]

    def _clean_all_tag(self, string_line):
        result = ''
        not_skip = True
        for i in list(string_line):
            if not_skip:
                if i == '<':
                    not_skip = False
                else:
                    result += i
            else:
                if i == '>':
                    not_skip = True

        return result
