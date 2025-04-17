from flask import Flask
from flask.helpers import make_response
from urllib.parse import urlparse
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the Flask app
from app import app

# Handler for Vercel serverless function
def handler(request):
    # Get URL components
    url_parts = urlparse(request.url)
    full_path = url_parts.path
    if not full_path:
        full_path = "/"
    
    # Create WSGI environment
    environ = {
        'wsgi.input': request.body,
        'wsgi.version': (1, 0),
        'wsgi.url_scheme': url_parts.scheme,
        'wsgi.multithread': False,
        'wsgi.multiprocess': False,
        'wsgi.run_once': False,
        'SERVER_SOFTWARE': 'Vercel',
        'REQUEST_METHOD': request.method,
        'PATH_INFO': full_path,
        'QUERY_STRING': url_parts.query,
        'SERVER_NAME': url_parts.hostname,
        'SERVER_PORT': url_parts.port or '443',
        'HTTP_HOST': url_parts.hostname,
    }
    
    # Add request headers
    for key, value in request.headers.items():
        key = key.upper().replace('-', '_')
        if key not in ('CONTENT_TYPE', 'CONTENT_LENGTH'):
            key = 'HTTP_' + key
        environ[key] = value
    
    # Response data
    response_data = {}
    
    def start_response(status, response_headers):
        # Parse status
        status_code = int(status.split(' ')[0])
        response_data['status'] = status_code
        response_data['headers'] = {k: v for k, v in response_headers}
    
    # Execute the Flask app
    body = app(environ, start_response)
    
    # Join response body if it's a list of bytes
    if isinstance(body, list) and all(isinstance(item, bytes) for item in body):
        body = b''.join(body)
    
    # Create response
    response = make_response(body)
    if 'status' in response_data:
        response.status_code = response_data['status']
    if 'headers' in response_data:
        for key, value in response_data['headers'].items():
            response.headers[key] = value
    
    return response