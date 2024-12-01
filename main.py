import os
import random
import string
import sqlite3
from flask import Flask, render_template, request, session, redirect, url_for, flash
from werkzeug.utils import secure_filename
import socket
from datetime import datetime

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

def generate_token():
    """Генерация случайной строки длиной 30 символов"""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=30))

def log_activity(action, username, password, ip_address):
    """Запись логов в файл"""
    with open("user_activity.log", "a") as log_file:
        log_file.write(f"{datetime.now()} - {action} - {username} - {password} - {ip_address}\n")

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

        # Генерация уникального токена для пользователя
        token = generate_token()

        # Обновляем данные пользователя в базе данных
        with sqlite3.connect("chat.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users SET username = ?, avatar = ?, status = ?, token = ? WHERE username = ?
            """, (nickname, avatar_path, about_me, token, session['username']))
            conn.commit()

        # Обновляем сессию с новым ником и токеном
        session['username'] = nickname
        session['token'] = token
        flash("Профиль успешно обновлен!")
        return redirect(url_for('chat'))  # Перенаправляем на страницу чата

    # Если запрос GET, возвращаем страницу с настройками профиля
    return render_template('profile_settings.html', user=get_user_info(session['username']))

def get_user_info(username):
    """Функция для получения информации о пользователе из базы данных"""
    with sqlite3.connect("chat.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        return cursor.fetchone()

@app.route('/chat')
def chat():
    """Страница чата"""
    if 'username' in session and 'token' in session:
        with sqlite3.connect("chat.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE username = ? AND token = ?", (session['username'], session['token']))
            user = cursor.fetchone()

            # Проверка токена
            if user is None:
                flash("Неверный токен доступа!")
                return redirect(url_for('logout'))

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
        ip_address = request.remote_addr  # Получаем IP-адрес пользователя

        with sqlite3.connect("chat.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
            user = cursor.fetchone()

            if user:
                session['username'] = username
                session['token'] = user[4]  # Сохраняем токен пользователя в сессию
                log_activity("Login", username, password, ip_address)  # Логируем успешный вход
                return redirect(url_for('chat'))  # Перенаправляем на страницу чата

            log_activity("Failed login", username, password, ip_address)  # Логируем неудачный вход
            flash("Неверное имя пользователя или пароль!")
            return redirect(request.url)
    return render_template('login.html')

# Страница для регистрации
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        ip_address = request.remote_addr  # Получаем IP-адрес пользователя

        with sqlite3.connect("chat.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
            user = cursor.fetchone()

            if user:
                flash("Пользователь с таким именем уже существует!")
                return redirect(request.url)

            cursor.execute("INSERT INTO users (username, password, token) VALUES (?, ?, ?)",
                           (username, password, generate_token()))
            conn.commit()

        log_activity("Registration", username, password, ip_address)  # Логируем регистрацию
        flash("Регистрация прошла успешно!")
        return redirect(url_for('chat'))  # Перенаправляем на страницу чата после регистрации

    return render_template('register.html')

# Выход из аккаунта
@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('token', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
