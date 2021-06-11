import pypureclient
from pypureclient.flashblade.client import Client
import textwrap
import argparse
import yaml
import logging
import os
import sys

logger = logging.getLogger('pure_fs')
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
        try:
            self.client = Client(array['ip-address'], api_token=array['api-token'])
        except:
            raise CanNotEstablishArraySession(array['name'])


    def list_quotas(self, filesystems):
        # List all user quotas for the file system
        res = self.client.get_quotas_users(file_system_names=filesystems)
        # print(list(res.items))
        if type(res) == pypureclient.responses.ValidResponse:
            return list(res.items)
        # Other valid fields: continuation_token, file_system_ids, filter, limit, names, offset, sort,
        #                     uids, user_names
        # See section "Common Fields" for examples

    def get_filesystems(self):
        res = self.client.get_file_systems()
        if type(res) == pypureclient.responses.ValidResponse:

            self.filesystems = list(res.items)
            self.fs_names = [fs.name for fs in self.filesystems]
            return self.filesystems

    def print_filesystems(self):

        if len(self.filesystems) == 0:
            self.get_filesystems()

        for each in self.filesystems:
            print(each.name)

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
    data['file_system_default_quota'] = round(data['file_system_default_quota'] / 1024 ** 3, 2)
    data['quota'] = round(data['quota'] / 1024 **3, 2)
    data['usage'] = round(data['usage'] / 1024 **3, 2)
    print('{:<15}{:<15}{:<18}{:<12}{:<10}{:<18}{:<10}{:<10}'.format(
                                                  fb,
                                                  data['file_system']['name'],
                                                  data['file_system_default_quota'],
                                                  str(data['user']['name']),
                                                  str(data['user']['id']),
                                                  str(data['quota']),
                                                  str(data['usage']),
                                                  str(round(data['usage'] / data['quota'] * 100, 2)),
                                                  )
    )

def to_csv(data, fb):
    data['file_system_default_quota'] = round(data['file_system_default_quota'] / 1024 **3, 2)
    data['quota'] = round(data['quota'] / 1024 **3, 2)
    data['usage'] = round(data['usage'] / 1024 **3, 2)
    print(
        fb + ',' +\
        data['file_system']['name'] + ',' +\
        str(data['file_system_default_quota']) + ',' +\
        str(data['user']['name']) + ',' + \
        str(data['user']['id']) + ',' + \
        str(data['quota']) + ',' + \
        str(data['usage']) + ',' + \
        str(round(data['usage'] / data['quota'] * 100, 2))
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

    if not args.c:
        print_header()
    if args.f:
        quotas = array.list_quotas(args.f)
        for quota in quotas:
            if args.u and args.u == str(quota.to_dict()['user']['name']):
                if args.c:
                    to_csv(quota.to_dict(), args.n)
                else:
                    to_screen(quota.to_dict(), args.n)
            elif not args.u:
                if args.c:
                    to_csv(quota.to_dict(), args.n)
                else:
                    to_screen(quota.to_dict(), args.n)
        exit()
    else:
        for name in array.fs_names:
            quotas = array.list_quotas([name])
            for quota in quotas:
                if args.u and args.u == str(quota.to_dict()['user']['name']):
                    if args.c:
                        to_csv(quota.to_dict(), args.n)
                    else:
                        to_screen(quota.to_dict(), args.n)
                if not args.u:
                    if args.c:
                        to_csv(quota.to_dict(), args.n)
                    else:
                        to_screen(quota.to_dict(), args.n)


if __name__ == "__main__":
    main()