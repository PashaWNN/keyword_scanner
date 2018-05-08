import re, pymorphy2
from threading import Thread
from time import sleep
from requests import get as rget
from random import seed, choice, randint
from json import dump
from config import BLACKLIST_FILE
import csv
import time


m = pymorphy2.MorphAnalyzer()   # Инициализация библиотеки для работы со словами
sovp = m.parse('совпадение')[0] # Подготовка слова "совпадение" для склонения по числам
LOADING_DELAY_MIN = 3           # Минимальная задержка между загрузкой страниц, в секундах
LOADING_DELAY_MAX = 5           # Максимальная... 
seed()                          # Инициализация генератора сл. ч.

blacklist = []
try:                            # Загрузка списка слов, которые не учитываются при поиске
  with open(BLACKLIST_FILE, 'r') as f:
    blacklist = f.read().split('\n')
except FileNotFoundError:
  with open(BLACKLIST_FILE, 'w') as f:
    f.write('')


def parse_sitemap(link):   # Вытаскивание ссылок из XML Sitemap
  text = load_page(link)
  return re.findall(r'<loc>(.+)<\/loc>', text)


def make_regex(s, preserve_blacklisted=False): 
"""
Создаёт регулярное выражение для словосочетания
Args:
  s: словосочетание
Kwargs:
  preserve_blacklisted: сохранять слова, включённые в blacklist[]
Returns:
  Регулярное выражение
"""
  s = re.sub(r'\+', '', s)
  l = re.split(r'[ -]', s)
  lst = []
  for word in l:
    if (not (word in blacklist)) or preserve_blacklisted:
      lst.append(word)
  res = ''
  for s in lst:
    reg = '('
    for p in m.parse(s)[0].lexeme:
      reg += p.word + '|'
    reg += ')'
    if s in blacklist:
      reg += '?'
    reg = re.sub(r'\|\)', ')', reg)
    res += reg + ' '
  res = res.strip()
  res = re.sub(r' ', '[ -]', res)
  res = re.sub(r'[Ёё]', '[её]', res)
  res +='[^А-Яа-яЁёA-Za-z]'
  return res

blackregex = make_regex(blacklist, preserve_blacklisted=True) # Создание регулярного выражения для поиска слов из ч.с.

def load_page(url):
  agents = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/42.0.2311.135 Safari/537.36 Edge/12.246',
    'Mozilla/5.0 (X11; CrOS x86_64 8172.45.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.64 Safari/537.36',
    'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/47.0.2526.111 Safari/537.36',
    'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:15.0) Gecko/20100101 Firefox/15.0.1',
    'Mozilla/5.0 (Linux; Android 6.0.1; SHIELD Tablet K1 Build/MRA58K; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/55.0.2883.91 Safari/537.36',
  ]
  headers = { 'User-Agent': choice(agents) }
  try:
    r = rget(url, headers = headers)
    if r.status_code == 200:
      if 'text' in r.headers['content-type']:
        return r.text
      else:
        raise Exception('Ошибка: не страница HTML')
    else:
      raise Exception('Ошибка %i' % r.status_code)
  except:
    raise


def strip_html(h):
"""
Обрезает из html-кода только значащий текст и убирает слова, входящие в ч.с.
Args:
  h: html-code
Returns:
  Обрезанный текст
"""
  reg = r'(?:description" content="(.+)"|<title>(.+)<\/title>|<body>([\S\s]+)<\/body>)'
  res = re.findall(reg, h, flags=re.IGNORECASE)
  res = re.sub(blackregex, '', res)
  if len(res)>0:
    return '\n\n'.join(res[0])


def count_occurences(string, page):
  reg = make_regex(string.strip())
  text = strip_html(page)
  return re.findall(reg, page, flags=re.IGNORECASE)


class ParsingThread(Thread):

  def __init__(self, threadID, link, words_list):
    Thread.__init__(self)
    self.threadID = threadID
    self.words_list = words_list
    self.progress = 0
    self.link = link if isinstance(link, list) else link.strip()
    self.completed = False
    self._log_s = []
    self._log('Создан поток.\n')
    self.paused = False
    self.stopped = False


  def _log(self, s):
    t = time.asctime()
    self._log_s.append('[%s] %s\r\n' % (t, s))


  def run(self):
    self.starttime = time.asctime()
    self._log('Поток запущен')
    self.result = []
    if isinstance(self.link, list):
      self._log('Ссылки готовы к обработке.')
      self.url_list = self.link
    else:
      try:
        self.url_list = parse_sitemap(self.link)
        self._log('Завершён разбор sitemap, ссылки получены.')
      except Exception as e:
        self._log('Ошибка разбора карты сайта. %s' % e)
    self._log('Начинаю загрузку страниц.')
    self.pages = []
    for i, url in enumerate(self.url_list):
      if self.stopped:
        self.stoptime = time.asctime()
        return
      sleep(randint(LOADING_DELAY_MIN, LOADING_DELAY_MAX))
      try:
        self.pages.append((url, load_page(url)))
        self._log('Загружена страница %s' % url)
      except Exception as e:
        self._log('Ошибка загрузки страницы %s' % url)
        self._log(e)
      self.progress = (i/len(self.url_list)) * 100
    self._log('Страницы загружены.')
    for i, w in enumerate(self.words_list):
      if self.stopped:
        self.stoptime = time.asctime()
        return
      self._log('Фраза №%i - "%s"' % (i, w))
      found = 0
      occurences = (w, [])
      for p in self.pages:
        occs = count_occurences(w, p[1])
        count = len(occs)
        res = {}
        for oc in occs:
          s = ' '.join(oc)
          if not s in res:
            res[s]=1
          else:
            res[s]+=1
        found+=1
        sov = sovp.make_agree_with_number(count).word
        self._log('Ключевая фраза: %s. Найдено %i %s: %s.' % (w, count, sov, occs))
        occurences[1].append((p[0], res))
      self.result.append(occurences)
    self.progress = 100.0
    self.completed = True
    self.stopped = True
    self._log('Работа завершена. Время начала: %s' % self.starttime)
    self.stoptime = time.asctime()


  def get_progress(self):
    return '%.2f' % self.progress


  def get_error(self):
    return ''


  def get_log(self, full=False):
    s = ''
    for line in self._log_s:
      s+=line
    if not full:
      s = s[25:]
    return s


  def stop(self):
    self._log('Преждевременная остановка.')
    self.stoptime = time.asctime()
    self.completed = True
    self.stopped = True


  def get_state(self, h=False):
    if self.completed:
      return 'Завершено' if h else 'completed'
    elif self.get_error():
      return 'Ошибка' if h else 'error'
    else:
      return 'Запущено' if h else 'running'


