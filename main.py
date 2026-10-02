"""
Main entry point for running the KHQR Daily Report Telegram Bot.
"""

import sys
import time
import asyncio
import os
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write(b"KHQR Bot is alive and running!")

    def do_HEAD(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()

    def log_message(self, format, *args):
        # Disable logging for health checks to keep console clean
        pass

def run_dummy_server():
    port = int(os.environ.get('PORT', 10000))
    try:
        server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
        print(f"🌐 HTTP Health Check Server listening on port {port} (0.0.0.0:{port})")
        server.serve_forever()
    except Exception as e:
        print(f"⚠️ Health check server error: {e}")

def keep_alive():
    t = Thread(target=run_dummy_server)
    t.daemon = True
    t.start()

# Safely ensure UTF-8 output on Windows terminals
if sys.platform == "win32":
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')

from bot import start_bot

if __name__ == "__main__":
    # Start the dummy web server to satisfy Render's web service requirement
    keep_alive()
    print("🌐 Web Server ត្រូវបានចាប់ផ្តើម (Port bindings for Render active).")
    
    retry_delay = 3
    while True:
        try:
            asyncio.run(start_bot())
            # If start_bot finishes normally without error, it usually means the Telegram server force-closed the connection.
            print("\n⚠️ ទំនាក់ទំនងទៅកាន់ Telegram ត្រូវបានផ្តាច់ដោយឯកឯង (Connection Closed by Server).")
            print(f"🔄 កំពុងតភ្ជាប់ឡើងវិញដោយស្វ័យប្រវត្តក្នុងរយៈពេល {retry_delay} វិនាទី...")
            time.sleep(retry_delay)
            retry_delay = min(retry_delay + 2, 30)
        except (KeyboardInterrupt, SystemExit):
            print("\n👋 KHQR Bot ត្រូវបានបញ្ឈប់ (Stopped).")
            break
        except Exception as e:
            print(f"\n⚠️ KHQR Bot ជួបបញ្ហារអាក់រអួល ឬដាច់ Connection: {e}")
            print(f"🔄 កំពុងតភ្ជាប់ និង Restart ឡើងវិញដោយស្វ័យប្រវត្តក្នុងរយៈពេល {retry_delay} វិនាទី (Auto-Recovery)...")
            time.sleep(retry_delay)
            retry_delay = min(retry_delay + 2, 30)

