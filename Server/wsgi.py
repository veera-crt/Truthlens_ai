"""
wsgi.py — Vercel serverless entry point.
Vercel's Python runtime looks for 'app' in this file.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app

# Vercel expects the Flask app instance to be named 'app'
# at module level — it is already imported above.

if __name__ == "__main__":
    app.run()
