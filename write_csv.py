import argparse
import csv
import json
import logging
from pathlib import Path
import sys


def read_enodebs(enodebs, timestamp):
    output = list()

    for enodeb in enodebs:
        for radio in enodeb['radios']:
            item = {
                'timestamp': timestamp,
                'enodeb_name': enodeb['name'],
                'radio_name': radio['name'],
                'pci': radio['pci'],
                'earfcn': radio['earfcndl'] if 'earfcndl' in radio else 0,
                'freq_mhz': radio['frequency_dl'],
                'bw_mhz': radio['channel_bandwidth'] / 5,
                'bw_rb': radio['channel_bandwidth'],
                'optimal_power_dbm': radio['optimal_power'],
                'signal_power_dbm': radio['signal_power_dbm'],
                'default_max_transmit_power': radio['default_max_transmit_power'],
                'configured_max_transmit_power': radio[
                    'configured_max_transmit_power'],
                'rf_state': radio['rf_state'],
                'rf_state_change_pending': radio['rf_state_change_pending'],
                'sas_grant_status': radio['sas_grant_status']
            }
            output.append(item)

    return output


def read_devices(devices, timestamp):
    output = list()

    for device in devices:
        if (device['op_status_name'] == 'Offline'):
            continue
        item = {
            'timestamp': timestamp,
            'name': device['description'],
            'phone_model': device['name'] if 'name' in device else '',
            'phone_model_number': device['model'] if 'model' in device else '',
            'status': device['op_status_name'],
            'connected_enodeb_name': device['enodeb_name'],
        }
        output.append(item)

    return output


def parse(list_args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--std-out", action='store_true')
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

    files = [path for path in args.log_dir.rglob("*") if path.is_file()]
    logging.debug(files)

    enodebs = list()
    devices = list()

    for file in files:
        logging.info(f"Reading {file.name}...")
        json_dict = dict()
        try:
            with open(file) as f:
                json_dict = json.load(f)
        except Exception as err:
            logging.error(f"Cannot open {file.name} as JSON: {err}")
            continue

        logging.debug(json_dict)
        timestamp = json_dict['timestamp']
        if ('enodebs' in json_dict):
            enodebs += read_enodebs(json_dict['enodebs'], timestamp)
        if ('devices' in json_dict):
            devices += read_devices(json_dict['devices'], timestamp)

    output_file = sys.stdout
    if (not args.std_out):
        output_file = open('enodebs.csv', 'w')
    csv_writer = csv.DictWriter(
        output_file,
        fieldnames=[
            'timestamp',
            'enodeb_name',
            'radio_name',
            'pci',
            'earfcn',
            'freq_mhz',
            'bw_mhz',
            'bw_rb',
            'optimal_power_dbm',
            'signal_power_dbm',
            'default_max_transmit_power',
            'configured_max_transmit_power',
            'rf_state',
            'rf_state_change_pending',
            'sas_grant_status'
        ])
    csv_writer.writeheader()
    csv_writer.writerows(enodebs)
    if (not args.std_out):
        output_file = open('devices.csv', 'w')
    csv_writer = csv.DictWriter(
        output_file,
        fieldnames=[
            'timestamp',
            'name',
            'phone_model',
            'phone_model_number',
            'status',
            'connected_enodeb_name'
        ])
    csv_writer.writeheader()
    csv_writer.writerows(devices)

    print('Done!')
