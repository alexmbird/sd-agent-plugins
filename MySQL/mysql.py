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

# com commands.
COMMANDS = [
    'Com_show_status',
    'Com_select',
    'Com_delete',
    'Com_update'
]


class MySQL(object):

    def __init__(self, agent_config, checks_logger, raw_config):
        self.agent_config = agent_config
        self.checks_logger = checks_logger
        self.raw_config = raw_config
        self.connection = None

    def version_is_above_5(self, status):
        if (int(status['version'][0]) >= 5
                and int(status['version'][2]) >= 2):
            return True
        else:
            return False

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

        # Note, code here doesn't really make sense. See what I copied.
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
                # Case 31237. Might include a description e.g. 4.1.26-log.
                # See http://dev.mysql.com/doc/refman/4.1/en/information-functions.html#function_version
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

            # get uptime
            try:
                cursor = db.cursor()
                cursor.execute(
                    'SHOW STATUS LIKE "Uptime"')
                results = cursor.fetchone()
                status['uptime'] = results[1]
            except MySQLdb.OperationalError as message:
                self.checks_logger.error(
                    'mysql: MySQL query error when getting uptime = {}'.format(
                        message)
                )
                return False
            self.checks_logger.debug('mysql: getting uptime - done')

            # Slow queries
            # Determine query depending on version. For 5.02 and above we
            # need the GLOBAL keyword (case 31015)
            # note, update with slow queries store. making it per second?
            # ask jordi about that.
            try:
                if self.version_is_above_5(status):
                    query = 'SHOW GLOBAL STATUS LIKE "Slow_queries"'
                else:
                    query = 'SHOW STATUS LIKE "Slow_queries'

                cursor = db.cursor()
                cursor.execute(query)
                result = cursor.fetchone()
                status['slow_queries'] = result[1]
            except MySQLdb.OperationalError as message:
                self.checks_logger(
                    'mysql: MySQL query error when getting Slow_queries = {}'.format(
                        message)
                    )
                return False
            self.checks_logger.debug('mysql: getting Slow_queries - done')

            # QPS - Queries per second.
            try:
                if self.version_is_above_5(status):
                    query = 'SHOW GLOBAL STATUS LIKE "Queries"'
                else:
                    query = 'SHOW STATUS LIKE "Queries"'
                cursor = db.cursor()
                cursor.execute(query)
                results = cursor.fetchone()
                status['queries_per_second'] = (
                    int(results[1])/float(status['uptime'])
                )
            except MySQLdb.OperationalError as message:
                self.checks_logger.debug(
                    'mysql: MySQL query error when getting QPS = {}'.format(
                        message)
                )
                return False
            self.checks_logger.debug('mysql: getting QPS - done')

            # Connection pool
            try:
                cursor = db.cursor()
                cursor.execute('SHOW STATUS LIKE "Threads_connected"')
                result = cursor.fetchone()
                status['threads_connected'] = result[1]

                cursor.execute('SHOW STATUS LIKE "Threads_running"')
                result = cursor.fetchone()
                status['threads_running'] = result[1]

                cursor.execute('SHOW VARIABLES LIKE "max_connections"')
                result = cursor.fetchone()
                status['max_connections'] = result[1]

                cursor.execute('SHOW STATUS LIKE "Max_used_connections"')
                result = cursor.fetchone()
                status['max_used_connections'] = result[1]

            except MySQLdb.OperationalError as message:
                self.checks_logger.error(
                    'mysql: MySQL query error when getting Threads_connected: {}'.format(
                        message)
                )
                return False
            self.checks_logger.debug('mysql: getting connections - done')

            # Buffer pool
            try:
                cursor = db.cursor()
                cursor.execute(
                    'SHOW STATUS LIKE "Innodb_buffer_pool_pages_total"')
                result = cursor.fetchone()
                status['buffer_pool_pages_total'] = result[1]

                cursor.execute(
                    'SHOW STATUS LIKE "Innodb_buffer_pool_pages_free"')
                result = cursor.fetchone()
                status['buffer_pool_pages_free'] = result[1]

                cursor.execute(
                    'SHOW STATUS LIKE "Innodb_buffer_pool_pages_dirty"')
                result = cursor.fetchone()
                status['buffer_pool_pages_dirty'] = result[1]

                cursor.execute(
                    'SHOW STATUS LIKE "Innodb_buffer_pool_pages_data"')
                result = cursor.fetchone()
                status['buffer_pool_pages_data'] = result[1]

            except MySQLdb.OperationalError as message:
                self.checks_logger.error(
                    'mysql: MySQL query error when getting Buffer pool pages = {}'.format(
                        message)
                )
                return False
            self.checks_logger.debug('mysql: getting buffer pool - done')

            # Query cache items
            try:
                cursor = db.cursor()
                cursor.execute(
                    'SHOW STATUS LIKE "Qcache_hits"')
                results = cursor.fetchone()
                status['qcache_hits'] = results[1]

                # NOTE: needs cache hits per second. How does that relate
                # to above?

                cursor.execute(
                    'SHOW STATUS LIKE "Qcache_free_memory"')
                results = cursor.fetchone()
                status['qcache_free_memory'] = results[1]

                cursor.execute(
                    'SHOW STATUS LIKE "Qcache_not_cached"')
                results = cursor.fetchone()
                status['qcache_not_cached'] = result[1]

                cursor.execute(
                    'SHOW STATUS LIKE "Qcache_queries_in_cache"')
                results = cursor.fetchone()
                status['qcache_in_cache'] = result[1]

            except MySQLdb.OperationalError as message:
                self.checks_logger.error(
                    'mysql: MySQL query error when getting Qcache data = {}'.format(
                        message))
                return False

            self.checks_logger.debug('mysql: getting Qcache data - done')

            # Aborted connections and clients
            try:
                cursor = db.cursor()
                cursor.execute(
                    'SHOW STATUS LIKE "Aborted_clients"')
                results = cursor.fetchone()
                status['aborted_clients'] = results[1]

                cursor.execute(
                    'SHOW STATUS LIKE "Aborted_connects"')
                results = cursor.fetchone()
                status['aborted_connects'] = results[1]

            except MySQLdb.OperationalError as message:
                self.checks_logger.error(
                    'mysql: MySQL query error when getting aborted items = {}'.format(
                        message)
                )
                return False

            self.checks_logger.debug(
                'mysql: getting aborted connections - done')

            # Replication - seconds behind master
            # note, is it enough? compared to old code?
            if self.raw_config['MySQLServer'].get('mysql_slave') == 'true':
                try:
                    cursor = db.cursor()
                    cursor.execute(
                        'SHOW SLAVE STATUS LIKE "Seconds_Behind_Master"')
                    results = cursor.fetchone()
                    status['seconds_behind_master'] = results[1]

                except MySQLdb.OperationalError as message:
                    self.checks_logger.error(
                        'mysql: MySQL query error when getting aborted items = {}'.format(
                            message)
                    )
                self.checks_logger(
                    'mysql: getting slave status data - done')
            else:
                pass

            # Created temporary tables in memory and on disk
            try:
                if self.version_is_above_5(status):
                    query = 'SHOW GLOBAL STATUS LIKE "Created_tmp_tables"'
                else:
                    query = 'SHOW STATUS LIKE "Created_tmp_tables"'
                cursor = db.cursor()
                cursor.execute(query)
                results = cursor.fetchone()
                status['created_tmp_tables'] = results[1]

                if self.version_is_above_5(status):
                    query = 'SHOW GLOBAL STATUS LIKE "Created_tmp_disk_tables"'
                else:
                    query = 'SHOW STATUS LIKE "Created_tmp_disk_tables"'
                cursor.execute(query)
                results = cursor.fetchone()
                status['created_tmp_tables_on_disk'] = results[1]
            except MySQLdb.OperationalError as message:
                self.checks_logger.error(
                    'mysql: MySQL query error when getting temp tables = {}'.format(
                        message)
                )
                return False
            self.checks_logger.debug(
                'mysql: getting temporary tables data - done')

            # select_full_join
            try:
                if self.version_is_above_5(status):
                    query = 'SHOW GLOBAL STATUS LIKE "Select_full_join"'
                else:
                    query = 'SHOW STATUS LIKE "Select_full_join"'
                cursor = db.cursor()
                cursor.execute(query)
                results = cursor.fetchone()
                status['select_full_join'] = results[1]
            except MySQLdb.OperationalError as message:
                self.checks_logger.error(
                    'mysql: MySQL query error when getting select full join = {}'.format(
                        message)
                )
                return False
            self.checks_logger.debug('mysql: getting select_full_join - done')

            # slave_running
            try:
                cursor = db.cursor()
                cursor.execute(
                    'SHOW STATUS LIKE "Slave_running"')
                results = cursor.fetchone()
                status['slave_running'] = results[1]
            except MySQLdb.OperationalError as message:
                self.checks_logger.error(
                    'mysql: MySQL query error when getting slave_running = {}'.format(
                        message)
                )
                return False
            self.checks_logger.debug(
                'mysql: getting slave_running - done')

            # open files
            try:
                cursor = db.cursor()
                cursor.execute('SHOW STATUS LIKE "Open_files"')
                results = cursor.fetchone()
                status['open_files'] = results[1]
            except MySQLdb.OperationalError as message:
                self.checks_logger.error(
                    'mysql: MySQL query error when getting open files = {}'.format(
                        message)
                )
                return False
            self.checks_logger.debug('mysql: getting open_files - done')

            # table_locks_waited
            try:
                cursor = db.cursor()
                cursor.execute('SHOW STATUS LIKE "Table_locks_waited"')
                results = cursor.fetchone()
                status['table_locks_waited'] = results[1]
            except MySQLdb.OperationalError as message:
                self.checks_logger.error(
                    'mysql: MySQL query error when getting table locks waited = {}'.format(
                        message)
                )
                return False
            self.checks_logger.debug(
                'mysql: getting table_locks_waited - done')

            # com commands
            try:
                cursor = db.cursor()
                for command in COMMANDS:
                    if self.version_is_above_5(status):
                        query = 'SHOW GLOBAL STATUS LIKE "{}"'.format(command)
                    else:
                        query = 'SHOW STATUS LIKE "{}"'.format(command)
                    cursor.execute(query)
                    results = cursor.fetchone()
                    status[command] = int(results[1])/float(status['uptime'])
            except MySQLdb.OperationalError as message:
                self.checks_logger.error(
                    'mysql: MySQL query error when getting com commands = {}'.format(
                        message)
                )
                return False
            self.checks_logger.debug(
                'mysql: getting com_commands - done')

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
