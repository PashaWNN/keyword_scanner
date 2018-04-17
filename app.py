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


@app.route('/add_task', methods=['GET', 'POST'])
def add_task():
  global tasks
  if len(tasks)>=MAX_TASKS:
    flash('Ошибка: превышен лимит заданий. Очистите очередь заданий и повторите попытку.')
    return redirect('/')
  if request.method == 'POST':
    f = request.files['file']
    if not f:
      flash('Необходимо прикрепить текстовый файл с ключевыми словами!')
      return redirect('/')
    stream = io.StringIO(f.stream.read().decode("utf-8"), newline=None)
    words = []
    for line in stream:
      words.append(line)
    link = request.form['link']
    if not link:
      flash('Необходимо ввести ссылку на карту сайта!')
      return redirect('/')
    num = len(tasks) if not len(tasks) in tasks else len(tasks)+1
    pt = ParsingThread(num, link, words)
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


@app.route('/generate_csv/<int:id>')
def gen_csv(id):
#
# result [ (word, [ link, count ]) ]
#
  if not 'authorized' in session:
    return redirect('/')
  try:
    l = tasks[id].result
    start = tasks[id].starttime
    stop = tasks[id].stoptime
    link = tasks[id].link
  except IndexError:
    flash('Ошибка создания CSV')
    return redirect('/')
  csv = ''
  csv += 'Время начала;%s\nВремя окончания;%s\n' % (start, stop)
  csv += 'Карта сайта;%s\n;\n' % link
  for i in l:
    csv += '\n%s;;\n' % i[0].strip()
    if len(i[1])>0:
      for j in i[1]:
        csv += ';%s;%s\n' % (j[0].strip(), j[1])
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




