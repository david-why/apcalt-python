from apcalt_python.app import build_app

from dotenv import load_dotenv

load_dotenv()

app = build_app()

if __name__ == '__main__':
    app.before_serving(
        lambda: print('**** APCAlt is up and running! http://localhost:8052 ****')
    )
    app.run('0.0.0.0', 8052)
