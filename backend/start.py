#!/usr/bin/env python3
"""Simple startup script that reads PORT from env and starts gunicorn."""

import os
import sys
import subprocess

# Get port from env, default to 8000
port = os.getenv('PORT', '8000')
bind_address = f"0.0.0.0:{port}"

# Build gunicorn command
cmd = [
    sys.executable, '-m', 'gunicorn',
    'flask_wsgi:app',
    '--bind', bind_address,
    '--workers', '2',
    '--timeout', '60'
]

print(f"Starting server on port {port}...")
subprocess.run(cmd)
