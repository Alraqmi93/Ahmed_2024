"""WSGI entry point for running the shop behind Gunicorn and HTTPS."""
from email.message import Message
from http import HTTPStatus
from io import BytesIO
import server

if not server.PASSWORD:
    raise RuntimeError('Set ADMIN_PASSWORD before starting the production service')

server.init()


class Request(server.Handler):
    def __init__(self, environ):
        self.headers = Message()
        for key, value in environ.items():
            if key.startswith('HTTP_'):
                self.headers[key[5:].replace('_', '-')] = str(value)
        for key in ('CONTENT_LENGTH', 'CONTENT_TYPE'):
            if environ.get(key):
                self.headers[key.replace('_', '-')] = environ[key]
        self.path = environ.get('PATH_INFO', '/')
        self.client_address = (environ.get('REMOTE_ADDR', ''), 0)
        self.rfile = environ['wsgi.input']
        self.wfile = BytesIO()
        self.status = 200
        self.response_headers = []

    def send_response(self, code, message=None):
        self.status = code

    def send_header(self, name, value):
        self.response_headers.append((name, str(value)))

    def end_headers(self):
        pass


def application(environ, start_response):
    request = Request(environ)
    method = environ.get('REQUEST_METHOD', 'GET')
    if method in ('GET', 'HEAD'):
        request.do_GET()
    elif method == 'POST':
        request.do_POST()
    else:
        request.send(405, {'error': 'Method not allowed'})
    body = request.wfile.getvalue()
    request.response_headers.extend([
        ('Content-Length', str(len(body))),
        ('Referrer-Policy', 'strict-origin-when-cross-origin'),
        ('X-Frame-Options', 'DENY'),
    ])
    start_response(f'{request.status} {HTTPStatus(request.status).phrase}', request.response_headers)
    return [b'' if method == 'HEAD' else body]
