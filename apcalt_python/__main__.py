from apcalt_python.app import build_app

from dotenv import load_dotenv

load_dotenv()

app = build_app()

if __name__ == '__main__':
    app.run('0.0.0.0', 8052, debug=True, use_evalex=False)
