from flask import Flask, request, render_template, redirect, url_for
from markupsafe import escape 
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
import tiktoken
from openai import OpenAI
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chatgpt.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your_secret_key'
socketio = SocketIO(app)

db = SQLAlchemy(app)

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    conversations = db.relationship('Conversation', backref='project', lazy=True)

class Conversation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)  # Add this line
    user_input = db.Column(db.Text, nullable=False)
    chat_response = db.Column(db.Text, nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)

client = OpenAI()

def count_tokens(text, model="gpt-4-0125-preview"):
    encoding = tiktoken.encoding_for_model(model)
    return len(encoding.encode(text))

# Custom Jinja filter for formatting datetimes
@app.template_filter('formatdatetime')
def format_datetime(value, format='%d%b%Y %H:%M:%S'):
    """Format a datetime object to a custom format."""
    if value is None:
        return ""
    return value.strftime(format)

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        project_name = request.form['project_name']
        if project_name:
            new_project = Project(name=project_name)
            db.session.add(new_project)
            db.session.commit()
            return redirect(url_for('chat', project_id=new_project.id))
    projects = Project.query.all()
    return render_template('index.html', projects=projects)

@app.route('/chat/<int:project_id>/', methods=['GET', 'POST'])
def chat(project_id):
    print("Inside Chat Function.")
    project = Project.query.get_or_404(project_id)
    print("trying POST...")
    if request.method == 'POST':
        print("POST SENT")
        user_input = request.form['user_input']
        chat_response = get_openai_response(project_id, user_input)

        if chat_response:
            new_conversation = Conversation(user_input=user_input, chat_response=chat_response, project_id=project_id)
            print(f"Attempting to add conversation to DB: User Input: {user_input}, Chat Response: {chat_response}")  # Logging before insertion
            db.session.add(new_conversation)
            db.session.commit()
            print("Conversation added to DB successfully.")  # Logging after insertion

            socketio.emit('update_conversation', {'message': chat_response, 'project_id': project_id}, room=project_id)

    return render_template('chat.html', project=project, conversations=project.conversations)


def get_openai_response(project_id, user_input):
    conversation_history = Conversation.query.filter_by(project_id=project_id).all()

    messages = []
    for conv in conversation_history:
        messages.append({"role": "user", "content": conv.user_input})
        messages.append({"role": "assistant", "content": conv.chat_response})
    messages.append({"role": "user", "content": user_input})

    try:
        response = client.chat.completions.create(
            model="gpt-4-0125-preview",
            messages=messages,
            temperature=0.2,
            stream=True,
        )
        return response.choices[0].message['content']
    except Exception as e:
        print(f"An error occurred while communicating with OpenAI: {e}")
        return None

@socketio.on('send_message')
def handle_message(data):
    user_input = data['message']
    project_id = data['project_id']
    project = Project.query.get_or_404(project_id)

    # Fetch the conversation history for the project
    conversation_history = Conversation.query.filter_by(project_id=project_id).all()

    messages = []
    for conversation in conversation_history:
        messages.append({"role": "user", "content": conversation.user_input})
        messages.append({"role": "assistant", "content": conversation.chat_response})

    messages.append({"role": "user", "content": user_input})

    try:
        accumulated_response = ""
        stream = client.chat.completions.create(
            model="gpt-4-0125-preview",
            messages=messages,
            temperature=0.2,
            stream=True
        )
        for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                safe_content = escape(chunk.choices[0].delta.content)
                accumulated_response += safe_content

        print(f"WebSocket: Attempting to add conversation to DB: User Input: {user_input}, Chat Response: {accumulated_response}")  # Logging before insertion

        # Emit the complete response to the client
        socketio.emit('receive_message', {'message': accumulated_response, 'project_id': project_id})

        # Save the conversation to the database
        new_conversation = Conversation(user_input=user_input, chat_response=accumulated_response, project_id=project_id)
        db.session.add(new_conversation)
        db.session.commit()

        print("WebSocket: Conversation added to DB successfully.")  # Logging after insertion

    except Exception as e:
        print(f"Error in handle_message: {e}")
        socketio.emit('receive_status', {'status': 'Error processing your request.', 'project_id': project_id})


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    socketio.run(app, debug=True)

