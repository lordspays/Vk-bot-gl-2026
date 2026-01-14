from flask import Flask
app = Flask(__name__)

@app.route('/')
def home():
    return "BOT WORKS"

if __name__ == '__main__':
    app.run()
