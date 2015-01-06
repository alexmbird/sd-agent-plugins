"""
Server Density plugin
MySQL

https://www.serverdensity.com/plugins/mysql/
https://github.com/serverdensity/sd-agent-plugins/

version: 0.1
"""
import traceback
import re

try:
    import MySQLdb
except ImportError:
    pass


class MySQL(object):

    def __init__(self, agent_config, checks_logger, raw_config):
        self.agent_config = agent_config
        self.checks_logger = checks_logger
        self.raw_config = raw_config
        self.connection = None

    def preliminaries(self):
        if ('MySQLServer' not in self.raw_config
            and 'mysql_server' not in self.raw_config['MySQLServer']
            or self.raw_config['MySQLServer']['mysql_server'] == ''
            or self.raw_config['MySQLServer']['mysql_user'] == ''
            or self.raw_config['MySQLServer']['mysql_pass'] == ''):
                self.checks_logger.debug('mysql: config not set')
                return False

        if not self.raw_config['MySQLServer'].get('mysql_port'):
            self.raw_config['MySQLServer']['mysql_port'] = "3306"

        self.checks_logger.debug('mysql: config set')

        try:
            import MySQLdb
        except ImportError:
            self.checks_logger.error('mysql: unable to import MySQLdb')
            return False

        if not self.raw_config['MySQLServer'].get('mysql_port'):
            # Connect
            try:
                MySQLdb.connect(
                    host=self.raw_config['MySQLServer']['mysql_server'],
                    user=self.raw_config['MySQLServer']['mysql_user'],
                    passw=self.raw_config['MySQLServer']['mysql_pass'],
                    port=int(self.raw_config['MySQLServer']['mysql_port'])
                    )
            except MySQLdb.OperationalError as message:
                self.checks_logger.error(
                    "mysql: MySQL connection error: {}".format(message))
                return False
        else:
            # Connect
            try:
                MySQLdb.connect(
                    host='localhost',
                    user=self.raw_config['MySQLServer']['mysql_user'],
                    passwd=self.raw_config['MySQLServer']['mysql_pass'],
                    port=int(self.raw_config['MySQLServer']['mysql_port']))
            except MySQLdb.OperationalError as message:
                self.checks_logger.error(
                    'mysql: MySQL connection error: {}'.format(message)
                    )
                return False
        return True

    def get_connection(self):
        try:
            # connection
            db = MySQLdb.connect(
                host=self.raw_config['MySQLServer']['mysql_server'],
                user=self.raw_config['MySQLServer']['mysql_user'],
                passwd=self.raw_config['MySQLServer']['mysql_pass'],
                port=int(self.raw_config['MySQLServer']['mysql_port'])
                )
            self.connection = db
            # note, how do I take into account the socket?
        except Exception:
            self.checks_logger.error(
                'Unable to connect to MySQL server {0} - Exception: {1}'.format(
                    self.config_raw['MySQLServer']['mysql_server'],
                    traceback.format_exc())
                )
            return False
        return True

    def run(self):
        self.checks_logger.debug('mysql: started gathering data')

        if not self.preliminaries():
            return False

        if not self.get_connection():
            return False

        try:
            db = self.connection

            # setup
            status = {}

            # Get MySQL version
            try:
                self.checks_logger.debug('mysql: getting mysqlversion')

                cursor = db.cursor()
                cursor.execute('SELECT VERSION()')
                result = cursor.fetchone()

                version = result[0].split('-')
                # Case 31237. Might include a description e.g. 4.1.26-log. See http://dev.mysql.com/doc/refman/4.1/en/information-functions.html#function_version
                version = version[0].split('.')

                status['version'] = []

                for version_item in version:
                    number = re.match('([0-9]+)', version_item)
                    number = number.group(0)
                    status['version'].append(number)

            except MySQLdb.OperationalError as message:
                self.checks_logger.error(
                    'mysql: MySQL query error when getting version: {}'.format(
                        message)
                    )
                return False
        except Exception:
            self.checks_logger.error(
                'mysql: unable to get data from MySQL - '
                'Exception: {}'.format(traceback.format_exc())
                )

        self.checks_logger.debug('mysql: completed, returning')
        return status

if __name__ == "__main__":
    """Standalone test"""

    import logging
    import sys
    import json
    import time
    host = 'localhost'
    port = '3306'

    raw_agent_config = {
        'MySQLServer': {
            'mysql_server': host,
            'mysql_port': port,
            'mysql_user': 'jonathan',
            'mysql_pass': 'password'
        }
    }

    main_checks_logger = logging.getLogger('MySQLplugin')
    main_checks_logger.setLevel(logging.DEBUG)
    main_checks_logger.addHandler(logging.StreamHandler(sys.stdout))
    mysql_check = MySQL({}, main_checks_logger, raw_agent_config)
    while True:
        try:
            result = mysql_check.run()
            print(json.dumps(result, indent=4, sort_keys=True))
        except:
            main_checks_logger.exception("Unhandled Exception")
        finally:
            time.sleep(60)