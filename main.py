from flask import Flask, render_template, request, session, redirect, url_for, flash
from werkzeug.utils import secure_filename
import os
import random
import sqlite3

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
app.config['UPLOAD_FOLDER'] = 'static/uploads'

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_avatar(nickname):
    """Генерация случайного аватара с цветом и первой буквой имени"""
    color = "#{:02x}{:02x}{:02x}".format(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
    return f"static/avatar/{color}_{nickname[0].upper()}.png"

@app.route('/profile_settings', methods=['GET', 'POST'])
def profile_settings():
    if 'username' not in session:
        return redirect(url_for('login'))  # Если пользователь не авторизован, перенаправляем на страницу входа

    if request.method == 'POST':  # Обработка отправки формы
        nickname = request.form['nickname']
        about_me = request.form['about_me']
        avatar_file = request.files.get('avatar')  # Получаем файл аватара

        # Если файл загружен и его расширение допустимо
        if avatar_file and allowed_file(avatar_file.filename):
            filename = secure_filename(avatar_file.filename)
            avatar_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            avatar_file.save(avatar_path)
        else:
            # Если аватар не был загружен, генерируем случайный аватар
            avatar_path = generate_avatar(nickname)

        # Обновляем данные пользователя в базе данных
        with sqlite3.connect("chat.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users SET username = ?, avatar = ?, status = ? WHERE username = ?
            """, (nickname, avatar_path, about_me, session['username']))
            conn.commit()

        # Обновляем сессию с новым ником
        session['username'] = nickname
        flash("Профиль успешно обновлен!")
        return redirect(url_for('index'))  # Перенаправляем на главную страницу

    # Если запрос GET, возвращаем страницу с настройками профиля
    return render_template('profile_settings.html', user=get_user_info(session['username']))

def get_user_info(username):
    """Функция для получения информации о пользователе из базы данных"""
    with sqlite3.connect("chat.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        return cursor.fetchone()

@app.route('/')
def index():
    if 'username' in session:
        with sqlite3.connect("chat.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE username = ?", (session['username'],))
            user = cursor.fetchone()
            cursor.execute("""
                SELECT users.username
                FROM users
                JOIN friends ON users.id = friends.friend_id
                WHERE friends.user_id = (
                    SELECT id FROM users WHERE username = ?
                )
            """, (session['username'],))
            friends = [row[0] for row in cursor.fetchall()]
            cursor.execute("""
                SELECT groups.name
                FROM groups
                JOIN group_members ON groups.id = group_members.group_id
                WHERE group_members.user_id = (
                    SELECT id FROM users WHERE username = ?
                )
            """, (session['username'],))
            groups = [row[0] for row in cursor.fetchall()]
        return render_template('chat.html', user=user, friends=friends, groups=groups)
    return redirect(url_for('login'))

# Страница для входа
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        with sqlite3.connect("chat.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
            user = cursor.fetchone()
            if user:
                session['username'] = username
                return redirect(url_for('index'))
            flash("Неверное имя пользователя или пароль!")
            return redirect(request.url)
    return render_template('login.html')

# Выход из аккаунта
@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
