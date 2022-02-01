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

logger = logging.getLogger('fb_quota')
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
    def __init__(self, array):
        self.array = array
        self.message = "Can not establish session with array."
        super().__init__(self.message)
    def __str__(self):
        return f'{self.message} --> {self.array}'



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

    pure_fs -n <flashblade> [ -f <Filesystem Name>]  [ -u <user name>] [-c ] 

    """
    parser = argparse.ArgumentParser(
        prog="pure_fs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(msg)
    )
    parser.add_argument('-n', help='FlashBlade Name', required=True)
    parser.add_argument('-u', help='User for quota', required=False)
    parser.add_argument('-f', help='filesystem to check', required=False)
    parser.add_argument('-c', help='Output to csv', action='store_true', required=False)
    args = parser.parse_args()
    return args, parser


class FlashBlade:

    def __init__(self, array):
        self.filesystems = []
        self.fs_names = []
        fb = PurityFb(array['ip-address'])
        fb.disable_verify_ssl()
        try:
            res = fb.login(array['api-token'])
            self.client = fb

        except rest.ApiException as e:
            print("Exception when logging in to the array: %s\n" % e)


    def list_quotas(self, filesystem):
        # List all user quotas for the file system
        res = ''
        try:
            #res = self.client.quotas_users.list_user_quotas(file_system_names=[filesystem]).to_dict()['items']
            res = self.client.usage_users.list_user_usage(file_system_names=[filesystem]).to_dict()['items']
        except rest.ApiException as e:
            print("Exception when creating file system or listing user quotas: %s\n" % e)
            sys.exit(1)

        return res


    def get_filesystems(self):
        res = ''
        try:
            res = self.client.file_systems.list_file_systems().to_dict()['items']
        except rest.ApiException as e:
            print("failed.")

        self.filesystems = [each['name'] for each in res]

    def print_filesystems(self):

        if len(self.filesystems) == 0:
            self.get_filesystems()

        for each in self.filesystems:
            print(each.name)

def print_header():
    print('{:<15}{:<30}{:<18}{:<12}{:<10}{:<18}{:<10}{:<10}'.format(
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

    print('{:<15}{:<30}{:<18}{:<12}{:<10}{:<18}{:<10}{:<10}'.format(
                                                    fb,
                                                    data['file_system']['name'],
                                                    data['file_system_default_quota'],
                                                    str(data['user']['name']),
                                                    str(data['user']['id']),
                                                    str(data['quota']),
                                                    str(data['usage']),
                                                    str(data['percent']
                                                    ))
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
    #for name in array.filesystems:
    #    quotas = array.list_quotas(name)
    #    for quota in quotas:
    #        pprint(quota)

    if not args.c:
        print_header()
    if args.f:
        quotas = array.list_quotas(args.f)
        for quota in quotas:

            if quota['file_system_default_quota']:
                quota['file_system_default_quota'] = round(quota['file_system_default_quota'] / 1024 ** 3, 2)
            else:
                quota['file_system_default_quota'] = 0
            if quota['quota']:
                quota['quota'] = round(quota['quota'] / 1024 ** 3, 2)
            else:
                quota['quota'] = 0
            if quota['usage']:
                quota['usage'] = round(quota['usage'] / 1024 ** 3, 2)
            else:
                quota['usage'] = 0

            try:
                quota['percent'] = str(round(quota['usage'] / quota['quota'] * 100, 2))
            except:
                try:
                    quota['percent'] = str(round(['usage'] / quota['file_system_default_quota'] * 100, 2))
                except:
                    quota['percent'] = "0"

            if quota['quota'] == 0:
                quota['quota'] = quota['file_system_default_quota']

            if args.u and args.u == str(quota['user']['name']):
                if args.c:
                    to_csv(quota, args.n)
                else:
                    to_screen(quota, args.n)
            elif not args.u:
                if args.c:
                    to_csv(quota, args.n)
                else:
                    to_screen(quota, args.n)
        exit()
    else:
        for name in array.filesystems:
            quotas = array.list_quotas(name)
            for quota in quotas:

                if quota['file_system_default_quota']:
                    quota['file_system_default_quota'] = round(quota['file_system_default_quota'] / 1024 ** 3, 2)
                else:
                    quota['file_system_default_quota'] = 0
                if quota['quota']:
                    quota['quota'] = round(quota['quota'] / 1024 ** 3, 2)
                else:
                    quota['quota'] = 0
                if quota['usage']:
                    quota['usage'] = round(quota['usage'] / 1024 ** 3, 2)
                else:
                    quota['usage'] = 0

                try:
                    quota['percent'] = str(round(quota['usage'] / quota['quota'] * 100, 2))
                except:
                    try:
                        quota['percent'] = str(round(['usage'] / quota['file_system_default_quota'] * 100, 2))
                    except:
                        quota['percent'] = "0"

                if quota['quota'] == 0:
                    quota['quota'] = quota['file_system_default_quota']


                if args.u and args.u == str(quota['user']['name']):
                    if args.c:
                        to_csv(quota, args.n)
                    else:
                        to_screen(quota, args.n)
                if not args.u:
                    if args.c:
                        to_csv(quota, args.n)
                    else:
                        to_screen(quota, args.n)
        

if __name__ == "__main__":
    main()