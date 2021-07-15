import purity_fb
import textwrap
import argparse
import yaml
import logging
import os
import json
from pprint import pprint
import urllib3
from purity_fb import PurityFb, FileSystem, Reference, NfsRule, rest
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
urllib3_log = logging.getLogger("urllib3")
urllib3_log.setLevel(logging.CRITICAL)
import sys

logger = logging.getLogger('fb_totals')
logger.setLevel('ERROR')
ch = logging.StreamHandler()
ch.setLevel('ERROR')
formatter = logging.Formatter('%(asctime)s - %(levelname)s ==> %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)


class ReadSessionsException(Exception):
    def __init__(self):
        self.message = "Can not read .sessions file."
        super().__init__(self.message)
    def __str__(self):
        return f'{self.message}'


class NoArrayCredentials(Exception):
    def __init__(self, array):
        self.array = array
        self.message = "Can not find array"
        super().__init__(self.message)
    def __str__(self):
        return f'{self.message} --> {self.array}'


class CanNotEstablishArraySession(Exception):
    def __init__(self, array, e):
        self.e = e
        self.array = array
        self.message = "Can not establish session with array."
        super().__init__(self.message)
    def __str__(self):
        return f'{self.message} --> {self.array} --> {self.e}'

class CanNotGetFilesystemList(Exception):
    def __init__(self, array, e):
        self.e = e
        self.array = array
        self.message = "Can not get list of filesystems."
        super().__init__(self.message)
    def __str__(self):
        return f'{self.message} --> {self.array} --> {self.e}'


class Sessions:
    def __init__(self):
        logger.info("Initiating and reading .sessions")
        script_dir = os.path.dirname(os.path.realpath(__file__))
        with open(script_dir + '/.sessions', 'r') as f:
            try:
                sessions = yaml.load(f.read(), Loader=yaml.FullLoader)
            except FileNotFoundError:
                raise ReadSessionsException()
            except Exception as e:
                raise ReadSessionsException()
            self.__dict__ = sessions

    def get_fb_creds(self, name):
        for fb in self.ARRAYS:
            if fb['name'] == name:
                return fb
        return None


def parse_args():
    msg = """

    pure_totals.py -n <flashblade> [ -c ]

    """
    parser = argparse.ArgumentParser(
        prog="pure_fs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(msg)
    )
    parser.add_argument('-n', help='FlashBlade Name', required=True)
    parser.add_argument('-c', help='Output to csv', action='store_true', required=False)
    args = parser.parse_args()
    return args, parser


class FlashBlade:

    def __init__(self, array):
        self.array_name = array['name']
        self.filesystems = []
        self.fs_names = []
        fb = PurityFb(array['ip-address'])
        fb.disable_verify_ssl()
        try:
            res = fb.login(array['api-token'])
            self.client = fb

        except rest.ApiException as e:
            raise CanNotEstablishArraySession(self.array_name, e)


    def get_filesystems(self):
        res = ''
        try:
            res = self.client.file_systems.list_file_systems().to_dict()['items']
        except rest.ApiException as e:
            raise CanNotGetFilesystemList(self.array_name)

        self.filesystems = [each['name'] for each in res]
        self.filesystem_details = res

    def print_filesystems(self):

        if len(self.filesystems) == 0:
            self.get_filesystems()

        for each in self.filesystem_details:
            print(each['name'])

    def calculate_totals(self):
        pass

def print_header():
    print('{:<15}{:<15}{:<18}{:<12}{:<10}{:<18}{:<10}{:<10}'.format(
        'FlashBlade',
        'Filesystem',
        'DefaultQuota(Gb)',
        'User',
        'Uid',
        'UserQuota(Gb)',
        'Usage(Gb)',
        'PctUsed(Gb)',
    ))

def to_screen(data, fb):

    print('{:<15}{:<15}{:<18}{:<12}{:<10}{:<18}{:<10}{:<10}'.format(
                                                  fb,
                                                  data['file_system']['name'],
                                                  data['file_system_default_quota'],
                                                  str(data['user']['name']),
                                                  str(data['user']['id']),
                                                  str(data['quota']),
                                                  str(data['usage']),
                                                  str(data['percent'])
                                                  )
    )

def to_csv(data, fb):

    print(
        fb + ',' +\
        data['file_system']['name'] + ',' +\
        str(data['file_system_default_quota']) + ',' +\
        str(data['user']['name']) + ',' + \
        str(data['user']['id']) + ',' + \
        str(data['quota']) + ',' + \
        str(data['usage']) + ',' + \
        str(data['percent'])
            )

def main():

    sessions = Sessions()
    args, parser = parse_args()

    if not args.n:
        parser.print_help()
        sys.exit(1)

    creds = sessions.get_fb_creds(args.n)
    if not creds:
        raise NoArrayCredentials(args.n)

    array = FlashBlade(creds)
    array.get_filesystems()

    for fs in array.filesystem_details:
        print(json.dumps(fs, indent=4))

if __name__ == "__main__":
    main()