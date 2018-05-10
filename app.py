import os, io
from sqlite3 import dbapi2 as sqlite3
from hashlib import md5
from werkzeug import check_password_hash, generate_password_hash
from flask import *
from my_core import *
from config import *
import csv

# Configuration
# Все настройки хранятся в файле ./config.py

ERR_WRONG_ID = 'Ошибка: задание с таким ID не найдено!'


tasks = {}


# Initialization
app = Flask(__name__)
try:
  with open(SECRET_KEY_FILE, 'r') as f:
    app.secret_key = bytes(f.read(), 'utf-8')
except FileNotFoundError:
  with open(SECRET_KEY_FILE, 'w') as f:
    app.secret_key = os.urandom(24)
    f.write(str(app.secret_key))
    app.logger.warning('Secret key file not found. New secret key created.')

try:
  with open(PASSWORD_HASH_F, 'r') as f:
    pw_hash = f.read().strip()
except FileNotFoundError:
  with open(PASSWORD_HASH_F, 'w') as f:
    flag = False
    while not flag:
      pw_hash = generate_password_hash(input('Enter new password: '))
      if check_password_hash(pw_hash, input('Repeat password: ')):
        flag = True
    f.write(pw_hash)


@app.route("/")
def index():
  if not 'authorized' in session:
    return redirect("/login")
  return render_template('index.html', title=APP_NAME, tasks=tasks, logged_in=('authorized' in session))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'authorized' in session:
        return redirect('/')
    error = None
    if request.method == 'POST':
        if not check_password_hash(pw_hash,
                                   request.form['password']):
            error = 'Неправильный пароль.'
        else:
            flash('Вы успешно авторизовались!')
            session['authorized'] = True
            return redirect('/')
    return render_template('login.html', error=error, title=APP_NAME)


@app.route('/logout')
def logout():
  session.pop('authorized', None)
  flash('Вы вышли из системы.')
  return redirect('/')


@app.route('/settings', methods=['GET', 'POST'])
def settings():
  return render_template('settings.html', title=APP_NAME)


@app.route('/add')
def add():
  if not 'authorized' in session:
    return redirect('/')
  return render_template('add.html', title=APP_NAME)


@app.route('/add_task', methods=['GET', 'POST'])
def add_task():
  def load(f):
    if request.method == 'POST':
      if not f:
        flash('Необходимо прикрепить текстовый файл с ключевыми словами!')
        return redirect('/')
      stream = io.StringIO(f.stream.read().decode("utf-8"), newline=None)
      words = []
      for line in stream:
        words.append(line.strip())
    return words
  global tasks
  if len(tasks)>=MAX_TASKS:
    flash('Ошибка: превышен лимит заданий. Очистите очередь заданий и повторите попытку.')
    return redirect('/')
  sm_method = request.form['sitemap']
  keys_method = request.form['keymethod']
  keys_data = load(request.files['file']) if (keys_method == 'file') else request.form['keys'].split('\r\n')
  sm_data = request.form['link'] if (sm_method == 'link') else request.form['links'].split('\r\n')
  if not (sm_data and keys_data):
    flash('Форма заполнена неправильно.')
    return redirect('/')
  num = len(tasks) if not len(tasks) in tasks else len(tasks)+1
  pt = ParsingThread(num, sm_data, keys_data)
  pt.start()
  tasks[num] = pt
  flash('Задание #%i успешно добавлено.' % num)  
  return redirect('/')


@app.route('/stop/<int:id>')
def stop_task(id):
  if not 'authorized' in session:
    return redirect('/')
  try:
    tasks[id].stop()
    return redirect(url_for('show_task', id=id))
  except IndexError:
    flash(ERR_WRONG_ID)
    return redirect('/')

  
@app.route('/del_task/<int:id>')
def delete(id):
  try:
    del tasks[id]
    return redirect('/')
  except IndexError:
    flash(ERR_WRONG_ID)
    return redirect('/')


@app.route('/view_report/<int:id>')
def view_report(id):
  if not 'authorized' in session:
    return redirect('/')
  try:
    l = tasks[id].result
  except IndexError:
    flash('Ошибка создания CSV')
    return redirect('/')
  return render_template('report.html', result=l, title=APP_NAME)


@app.route('/download_log/<int:id>')
def get_log(id):
  if not 'authorized' in session:
    return redirect('/')
  try:
    log = tasks[id].get_log(full=True)
  except IndexError:
    flash('Нет задания с таким ID!')
    return redirect('/')
  return Response(
    log.encode('cp1251', errors='replace'),
    mimetype="text/txt",
    headers={"Content-disposition":
             "attachment; filename=log%i.txt" % id}
  )


@app.route('/generate_csv/<int:id>')
def gen_csv(id):
#
# result [ (word, [ link, { occurence: count } ]) ]
#
  if not 'authorized' in session:
    return redirect('/')
  try:
    l = tasks[id].result
    start = tasks[id].starttime
    stop = tasks[id].stoptime
  except IndexError:
    flash('Ошибка создания CSV')
    return redirect('/')
  csv = ''
  csv += 'Время начала;%s\nВремя окончания;%s\n\n' % (start, stop)
  for result in l:
    csv += '\n%s;;\n' % result[0].strip()
    if len(result[1])>0:
      for link in result[1]:
        if len(link[1])>0:
          csv += ';%s;\n' % (link[0].strip())
          for occurence in link[1]:
            csv +=';;%s;%i\n' % (occurence, link[1][occurence])
    else:
      csv += ';Вхождений на сайте не найдено!;\n'
  return Response(
    csv.encode('cp1251', errors='replace'),
    mimetype="text/csv",
    headers={"Content-disposition":
             "attachment; filename=report.csv"}
  )
  

@app.route('/task/<int:id>')
def show_task(id):
  if not 'authorized' in session:
    return redirect('/')
  try:
    task = tasks[id]
    return render_template('task.html', task=task, title=APP_NAME, logged_in=('authorized' in session))
  except KeyError:
    flash('Ошибка: задание с таким ID не найдено!')
    return redirect('/')


