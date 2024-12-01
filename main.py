import os
import sqlite3
from flask import Flask, render_template, request, session, redirect, url_for, flash, jsonify
from werkzeug.utils import secure_filename
from flask_socketio import SocketIO, emit, join_room, leave_room

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
socketio = SocketIO(app, cors_allowed_origins="*")

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


def init_db():
    with sqlite3.connect("chat.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                avatar TEXT DEFAULT NULL,
                status TEXT DEFAULT 'Онлайн'
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender TEXT NOT NULL,
                recipient TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS friends (
                user_id INTEGER NOT NULL,
                friend_id INTEGER NOT NULL,
                UNIQUE(user_id, friend_id),
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(friend_id) REFERENCES users(id)
            )
        """)
        conn.commit()


init_db()


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
        return render_template('chat.html', user=user, friends=friends)
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        if password != confirm_password:
            flash("Пароли не совпадают!")
            return redirect(request.url)
        with sqlite3.connect("chat.db") as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
                conn.commit()
                return redirect(url_for('login'))
            except sqlite3.IntegrityError:
                flash("Имя пользователя уже существует!")
                return redirect(request.url)
    return render_template('register.html')


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


@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))


@socketio.on('join')
def handle_join(data):
    username = data['username']
    room = data.get('room', 'vad')  # По умолчанию подключаем к "vad"
    join_room(room)
    emit('message', {'message': f'{username} присоединился к {room}!', 'room': room}, room=room)


@socketio.on('send_message')
def handle_send_message(data):
    sender = data['sender']
    message = data['message']
    recipient = data.get('recipient')
    room = data.get('room', 'vad')

    # Сохраняем сообщение в базу данных
    with sqlite3.connect("chat.db") as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO messages (sender, recipient, message) VALUES (?, ?, ?)", (sender, recipient, message))
        conn.commit()

    # Отправляем сообщение
    emit('message', {'sender': sender, 'message': message, 'recipient': recipient, 'room': room}, room=room)


@socketio.on('call_user')
def handle_call_user(data):
    caller = data['caller']
    callee = data['callee']
    emit('incoming_call', {'caller': caller}, to=callee)


@socketio.on('accept_call')
def handle_accept_call(data):
    room = f"call_{data['caller']}_{data['callee']}"
    join_room(room)
    emit('call_accepted', {'room': room}, broadcast=True)


@socketio.on('ice_candidate')
def handle_ice_candidate(data):
    emit('ice_candidate', data, to=data['room'])


@socketio.on('offer')
def handle_offer(data):
    emit('offer', data, to=data['room'])


@socketio.on('answer')
def handle_answer(data):
    emit('answer', data, to=data['room'])


if __name__ == '__main__':
    socketio.run(app, debug=True)
