import re, pymorphy2
from threading import Thread
from time import sleep
from requests import get as rget
from random import seed, choice, randint
from json import dump
from config import BLACKLIST_FILE
import csv
import time


m = pymorphy2.MorphAnalyzer()
sovp = m.parse('совпадение')[0]
LOADING_DELAY_MIN = 3
LOADING_DELAY_MAX = 5
seed()

blacklist = []
try:
  with open(BLACKLIST_FILE, 'r') as f:
    blacklist = f.read().split('\n')
except FileNotFoundError:
  with open(BLACKLIST_FILE, 'w') as f:
    f.write('')


def parse_csv(f):
  res = []
  for row in csv.reader(f, delimiter=';'):
    res.append(row)
  return res


def parse_sitemap(link):
  text = load_page(link)
  return re.findall(r'<loc>(.+)<\/loc>', text)


def make_regex(s):
  s = re.sub(r'\+', '', s)
  lst = re.split(r'[ -]', s)
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
  return res


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
        return 'Ошибка: не страница HTML'
    else:
      return 'Ошибка %i' % r.status_code
  except:
    return 'Ошибка'


def strip_html(h):
  reg = r'(?:description" content="(.+)"|<title>(.+)<\/title>|<body>([\S\s]+)<\/body>)'
  res = re.findall(reg, h, flags=re.IGNORECASE)
  if len(res)>0:
    return '\n\n'.join(res[0])


def count_occurences(string, page):
  reg = make_regex(string.strip())
  debug('Создаём регулярное выражение для "%s"\n%s' % (string, reg))
  text = strip_html(page)
  return re.findall(reg, page, flags=re.IGNORECASE)


class ParsingThread(Thread):
  def __init__(self, threadID, link, words_list):
    Thread.__init__(self)
    self.threadID = threadID
    self.words_list = words_list
    self.progress = 0
    self.link = link.strip()
    self.completed = False
    self._log_s = []
    self._log('Создан поток.\n')
    self.paused = False
    self.stopped = False


  def _log(self, s):
    t = time.asctime()
    self._log_s.append('[%s] %s\n' % (t, s))
    if len(self._log_s) > 1000:#25:
      self._log_s.pop(0)


  def run(self):
    self.starttime = time.asctime()
    self._log('Поток запущен')
    self.result = []
    self.url_list = parse_sitemap(self.link)
    self._log('Завершён разбор sitemap, ссылки получены.')
    self._log('Начинаю загрузку страниц.')
    self.pages = []
    for i, url in enumerate(self.url_list):
      while self.paused:
        pass
      if self.stopped:
        self.stoptime = time.asctime()
        return
      sleep(randint(LOADING_DELAY_MIN, LOADING_DELAY_MAX))
      self.pages.append((url, load_page(url)))
      self._log('Загружена страница %s' % url)
      self.progress = (i/len(self.url_list)) * 100
    self._log('Страницы загружены.')
    for i, w in enumerate(self.words_list):
      while self.paused:
        pass
      if self.stopped:
        self.stoptime = time.asctime()
        return
      self._log('Фраза №%i - "%s"' % (i, w))
      found = 0
      occurences = (w, [])
      for p in self.pages:
        if not re.findall(r'^Ошибка.+$', p[1]):
          occs = count_occurences(w, p[1])
          count = len(occs)
          if count>0:
            found+=1
            sov = sovp.make_agree_with_number(count).word
            self._log('Ключевая фраза: %s. Найдено %i %s: %s.' % (w, count, sov, occs))
            occurences[1].append((p[0], count))
        else:
          self._log('Страница не загружена. %s' % p[0])
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


  def get_log(self):
    s = ''
    for line in self._log_s:
      s+=line
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


