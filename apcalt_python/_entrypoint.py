import os
import sys

from uvicorn.main import main

try:
    import certifi
    import ssl

    _create_default_context = ssl.create_default_context

    def create_default_context(*args, **kwargs):
        ctx = _create_default_context(*args, **kwargs)
        ctx.load_verify_locations(certifi.where())
        return ctx

    ssl.create_default_context = create_default_context
except ImportError:
    pass

os.environ.setdefault('FLASK_SESSION_TYPE', 'filesystem')
sys.argv[1:] = ['apcalt_python.__main__:app', '--host', '0.0.0.0', '--port', '8052']

from apcalt_python.__main__ import app


@app.before_serving
def before_serving():
    print('**** APCAlt has started! Please visit: http://localhost:8052 ****')


main()
