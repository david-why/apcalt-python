import os
import sys

from uvicorn.main import main

os.environ['FLASK_SESSION_TYPE'] = 'filesystem'
sys.argv[1:] = ['apcalt_python.__main__:app', '--host', '0.0.0.0', '--port', '8052']

from apcalt_python.__main__ import app

main()
