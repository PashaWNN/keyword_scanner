#!/usr/bin/python3
import re, pymorphy2
from threading import Thread
from time import sleep
from requests import get as rget
from random import seed, choice, randint
from json import dump
import csv
import time

m = pymorphy2.MorphAnalyzer()
sovp = m.parse('совпадение')[0]
LOADING_DELAY_MIN = 3
LOADING_DELAY_MAX = 5
seed()

dbg = ''
DEBUG=True


def parse_csv(f):
  res = []
  for row in csv.reader(f, delimiter=';'):
    res.append(row)
  return res

def parse_sitemap(link):
  text = load_page(link)
  return re.findall(r'<loc>(.+)<\/loc>', text)


def write_csv(fn, data):
  pass


def make_regex(s):
  s = re.sub(r'\+', '', s)
  lst = s.split(' ')
  res = ''
  for s in lst:
    reg = '('
    for p in m.parse(s)[0].lexeme:
      reg += p.word + '|'
    reg += ')'
    reg = re.sub(r'\|\)', ')', reg)
    res += reg + ' '
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
  return len(re.findall(reg, page, flags=re.IGNORECASE))


def debug(s):
  global dbg
  if DEBUG:
    dbg+=s+'\n'


class ParsingThread(Thread):
  def __init__(self, threadID, link, words_list):
    Thread.__init__(self)
    self.threadID = threadID
    self.words_list = words_list
    self.progress = 0
    self.link = link
    self.completed = False
    self._log_s = []
    self._log('Создан поток')
    self.paused = False
    self.stopped = False
  def _log(self, s):
    t = time.asctime()
    self._log_s.append('[%s] %s\n' % (t, s))
    if len(self._log_s) > 25:
      self._log_s.pop(0)
  def run(self):
    self.starttime = time.asctime()
    self._log('Поток запущен')
    self.result = {}
    self.url_list = parse_sitemap(self.link)
    self._log('Завершён разбор sitemap, ссылки получены')
    for i, url in enumerate(self.url_list):
      while self.paused:
        pass
      if self.stopped:
        self.stoptime = time.asctime()
        return
      self._log('Ссылка №%i - адрес %s' % (i, url))
      sleep(randint(LOADING_DELAY_MIN, LOADING_DELAY_MAX))
      self.result[url] = {}
      self.progress = (i/len(self.url_list)) * 100
      page = load_page(url)
      found = 0
      if not re.findall(r'^Ошибка.+$', page):
        for w in self.words_list:
          count = count_occurences(w, page)
          if count>0:
            self.result[url][w] = count
            found+=1
            sov = sovp.make_agree_with_number(count).word
            self._log('Ключевая фраза: %s. Найдено %i %s.' % (w, count, sov))
        self._log('Найдено %i/%i.' % (found, len(self.words_list)))
      else:
        self._log('Страница не загружена. %s' % page)
        self.result[url] = page
    self.progress = 100.0
    self.completed = True
    self.stopped = True
    self._log('Работа завершена. Время начала: %s' % time.asctime())
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

  def pause(self):
    self._log('Поток остановлен.')
    self.paused = True

  def resume(self):
    self._log('Возобновление...')
    self.paused = False

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

def save_json(pt, fn):
  with open(fn, 'w') as f:
    dump(pt.result, f)


