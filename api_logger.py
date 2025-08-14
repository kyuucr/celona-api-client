import argparse
from datetime import datetime, timedelta, timezone
import http.server
import json
import logging
from pathlib import Path
import requests
import os
import socketserver
import sys
import threading
import time


PORT = 8000
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


class MyHandler(http.server.SimpleHTTPRequestHandler):
    """
    A custom handler that serves files from the specified directory.
    This is a subclass of SimpleHTTPRequestHandler.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=SCRIPT_DIR, **kwargs)


def run_server():
    """
    Starts a simple HTTP server in a separate thread.
    """
    # Use a TCP server to handle requests from the specified port
    with socketserver.TCPServer(("0.0.0.0", PORT), MyHandler) as httpd:
        logging.info(f"[{datetime.now()}] Server thread started.")
        logging.info(
            f"[{datetime.now()}] Serving directory: "
            f"{os.path.abspath(SCRIPT_DIR)}")
        print(f"HTTP Server serving at http://0.0.0.0:{PORT}")
        # serve_forever() is a blocking call, which is why we need a thread
        httpd.serve_forever()


def get_call(url: str, headers: dict = None):
    """
    Performs a GET REST call to the specified URL.

    Args:
        url (str): The URL to send the GET request to.
        headers (dict, optional): A dictionary of HTTP headers to send with the request. Defaults to None.

    Returns:
        dict or None: JSON response data if successful, None otherwise.
    """
    logging.info(
        f"[{datetime.now()}] Attempting GET request to: {url}")
    try:
        response = requests.get(url, headers=headers, timeout=10) # 10-second timeout
        response.raise_for_status()  # Raises an HTTPError for bad responses (4xx or 5xx)

        logging.info(
            f"[{datetime.now()}] Request successful! "
            f"Status Code: {response.status_code}")
        # Assuming the response is JSON, parse it
        json_data = response.json()
        logging.debug(f"[{datetime.now()}] Response Data:")
        logging.debug(json_data)
        return json_data

    except requests.exceptions.HTTPError as http_err:
        logging.error(f"[{datetime.now()}] HTTP error occurred: {http_err}")
    except requests.exceptions.ConnectionError as conn_err:
        logging.error(
            f"[{datetime.now()}] Connection error occurred: {conn_err}")
    except requests.exceptions.Timeout as timeout_err:
        logging.error(
            f"[{datetime.now()}] Timeout error occurred: {timeout_err}")
    except requests.exceptions.RequestException as req_err:
        logging.error(
            f"[{datetime.now()}] An unexpected request error "
            f"occurred: {req_err}")
    except ValueError:
        logging.error(f"[{datetime.now()}] Response was not valid JSON.")
    return None


def batch_fetch_data(api_key, log_dir):
    base_url = 'https://api.celona.io/v1/api/'
    headers = {
        'Accept': 'application/json',
        'X-API-Key': api_key
    }
    timestamp = datetime.now(timezone.utc).astimezone().isoformat()
    output = {
        'timestamp': timestamp,
        'enodebs': None,
        'devices': None
    }

    logging.info(f"[{datetime.now()}] Fetching eNodeBs...")
    result = get_call(base_url + 'cfgm/enodebs', headers)
    if (result['success']):
        output['enodebs'] = result['data']
    time.sleep(1)   # Avoid rate limit

    logging.info(f"[{datetime.now()}] Fetching devices...")
    result = get_call(base_url + 'cfgm/devices?config-status=Activated',
                      headers)
    if (result['success']):
        output['devices'] = result['data']

    logging.info(f"[{datetime.now()}] Writing to logdir ...")
    output_fn = log_dir / f"{timestamp}.json"
    with open(output_fn, 'w') as f:
        f.write(json.dumps(output))

    logging.info(f"[{datetime.now()}] Writing to latest.json ...")
    with open('latest.json', 'w') as f:
        f.write(json.dumps(output))
    logging.info(f"[{datetime.now()}] Fetching done !")


def parse(list_args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--interval", type=int, default=60,
                        help=("Specify interval between captures in minutes, "
                              "default=60"))
    parser.add_argument("-s", "--api-key", type=Path, default=Path("./.secret"),
                        help="Specify api key file, default='./.secret'")
    parser.add_argument("-d", "--log-dir", type=Path, default=Path("./logs"),
                        help="Specify local log directory, default='./logs'")
    parser.add_argument("-l", "--log-level", default="warning",
                        help="Provide logging level, default is warning'")
    if (list_args is None):
        return parser.parse_args()
    else:
        return parser.parse_args(args=list_args)


if __name__ == '__main__':
    # Setup
    args = parse()
    logging.basicConfig(level=args.log_level.upper())
    args.log_dir.mkdir(parents=True, exist_ok=True)
    api_key = ''

    # Start the HTTP server in a new thread.
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    while True:
        try:
            with open(args.api_key, 'r') as f:
                api_key = f.read()
            batch_fetch_data(api_key, args.log_dir)
            dt_target = (datetime.now(timezone.utc).astimezone() + timedelta(
                0, args.interval)).isoformat()
            logging.info(
                f"[{datetime.now()}] Sleeping for {args.interval} minutes, "
                f"waking up at {dt_target}")
            time.sleep(args.interval * 60)
        except KeyboardInterrupt:
            print("\nScript interrupted by user (Ctrl+C). Exiting.")
            break
        except FileNotFoundError:
            logging.error(
                f"[{datetime.now()}] Please define API key in the "
                f"{args.api_key.name} file !")
        except Exception as e:
            logging.error(
                f"[{datetime.now()}] An unhandled error occurred in the "
                f"main loop: {e}")
