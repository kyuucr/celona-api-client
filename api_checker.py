import argparse
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import requests
import sys
import time
import yaml


def get_call(url: str, headers: dict = None):
    """
    Performs a GET REST call to the specified URL.

    Args:
        url (str): The URL to send the GET request to.
        headers (dict, optional): A dictionary of HTTP headers to send with the request. Defaults to None.

    Returns:
        dict or None: JSON response data if successful, None otherwise.
    """
    logging.info(f"Attempting GET request to: {url}")
    try:
        response = requests.get(url, headers=headers, timeout=10) # 10-second timeout
        return response.status_code, response.json()

    except requests.exceptions.ConnectionError as conn_err:
        logging.error(f"Connection error occurred: {conn_err}")
    except requests.exceptions.Timeout as timeout_err:
        logging.error(f"Timeout error occurred: {timeout_err}")
    except requests.exceptions.RequestException as req_err:
        logging.error(f"An unexpected request error occurred: {req_err}")
    except ValueError:
        logging.error(f"Response was not valid JSON.")
    return 500, dict()


def batch_fetch_data(api_key, api_endpoints, default_params):
    base_url = f"https://{api_endpoints['host']}{api_endpoints['basePath']}"
    logging.debug(base_url)
    headers = {
        "Accept": "application/json",
        "X-API-Key": api_key
    }

    results = list()

    # Get only first level endpoints with get method
    ep_list = [key for key in api_endpoints['paths'].keys()
               if (key.count('/') == 1
                   and 'get' in api_endpoints['paths'][key])]
    logging.debug(ep_list)

    for ep in ep_list:
        logging.info(f"Fetching {ep}...")
        call_url = f"{base_url}{ep}"
        
        # Fetch required parameters
        if ('parameters' in api_endpoints['paths'][ep]['get']):
            logging.debug(api_endpoints['paths'][ep]['get']['parameters'])
            params = [param['name']
                      for param in api_endpoints['paths'][ep]['get']['parameters']
                      if ('required' in param and param['required'])]
            params_wo_input = [item for item in params
                               if item not in default_params.keys()]
            if len(params_wo_input) > 0:
                logging.warning(f"Skipping {ep}, these parameters are without "
                                f"input {params_wo_input}")
                results.append({
                    "path": ep,
                    "full_url": call_url,
                    "code": 500,
                    "result": "skipped"
                })
                continue
            if len(params) > 0:
                param_str = "&".join(
                    [f"{param}={default_params[param]}" for param in params])
                call_url = f"{call_url}?{param_str}"

        result_code, result_json = get_call(call_url, headers)
        result_exists = "exists" if result_json else "empty"
        logging.info(f"{ep} => {result_code}: {result_exists}")
        logging.debug(result_json)
        results.append({
            "path": ep,
            "full_url": call_url,
            "code": result_code,
            "result": result_exists
        })
        time.sleep(1)   # Avoid rate limit

    return results


def parse(list_args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("api_endpoints", type=Path,
                        help="Specify API YAML file")
    parser.add_argument("-s", "--api-key", type=Path, default=Path("./.secret"),
                        help="Specify API key file, default='./.secret'")
    parser.add_argument("-d", "--defaults", type=Path,
                        default=Path("./defaults.json"),
                        help=("Specify JSON file containing default parameters,"
                              " default='./defaults.json'"))
    parser.add_argument("-l", "--log-level", default="warning",
                        help="Provide logging level, default is warning'")
    if (list_args is None):
        return parser.parse_args()
    else:
        return parser.parse_args(args=list_args)


if __name__ == '__main__':
    args = parse()
    logging.basicConfig(level=args.log_level.upper())
    default_params = dict()
    api_key = ''
    api_endpoints = dict()
    with open(args.api_key, 'r') as f:
        api_key = f.read()
    with open(args.api_endpoints, 'r') as f:
        api_endpoints = yaml.safe_load(f)
    with open(args.defaults, 'r') as f:
        default_params = json.load(f)
    if (api_key == ''):
        raise Exception("API key is not valid !")
    if (api_endpoints == dict()):
        raise Exception("API endpoints YAML file is not valid !")
    if (default_params == dict()):
        raise Exception("Default param file is not valid !")
    results = batch_fetch_data(api_key, api_endpoints, default_params)

    output_fn = f"{args.api_endpoints.stem}.json"
    print(f"Writing results to {output_fn}...")
    with open(output_fn, "w") as f:
        json.dump(results, f, indent=4)
    print("Done !")
