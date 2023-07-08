# coding=utf-8

import os

import pymysql

# datax安装路径
path_datax = os.path.join("../datax/bin/", "datax.py")
num_processes = 4  # 最大进程数
num_threads = 4  # 最大线程数

# 配置数据库类型,选择数据源和目标源数据库类型，可选数据库类型有: 'mysql', 'sqlserver', 'oracle', 'gaussdb'
source_db_type = 'gaussdb'  # 数据源
target_db_type = 'sqlserver'  # 目标源


# 数据源数据库信息
sourceip = '10.201.65.21'  # host
sourceport = '30100'  # 端口
sourcedb = 'ygt'  # datebase
sourceuser = 'ygt'  # 用户名
sourcepw = 'ygtqwe123!@#'  # 密码
reader = 'postgresqlreader'  # 配置json中的数据源读取器名称：readername
'''


# 数据源数据库信息
sourceip = '192.168.203.130'  # host
sourceport = '1433'  # 端口
sourcedb = 'YGT'  # datebase
sourceuser = 'sa'  # 用户名
sourcepw = 'x032013x@..'  # 密码
reader = 'sqlserverreader'  # 配置json中的数据源读取器名称：readername
'''
# 目标源数据库信息
targetip = '192.168.203.129'  # host
targetport = '1433'  # 端口
targetdb = 'YGT'  # datebase
targetuser = 'sa'  # 用户名
targetpw = 'x032013x@..'  # 密码
writer = 'sqlserverwriter'  # 配置json中的数据源读取器名称：writername


db_config = {
    'mysql': {
        'host': '{host}',
        'port': '{port}',
        'user': '{user}',
        'password': '{password}',
        'database': '{database}',
        'charset': 'utf8mb4',
        'cursorclass': pymysql.cursors.DictCursor,
        # 添加 mysql 的 jdbc 连接字符串
        'source_jdbcUrl': "jdbc:mysql://{host}:{port}/{database}?useUnicode=true&characterEncoding=utf8",
        'target_jdbcUrl': "jdbc:mysql://{host}:{port}/{database}?useUnicode=true&characterEncoding=utf8",
        'readername': 'reader',
        'writername': 'writer'
    },
    'sqlserver': {
        'user': '{user}',
        'password': '{password}',
        'database': '{database}',
        'host': '{host}',
        'port': '{port}',
        # 添加 sqlserver 的 jdbc 连接字符串
        'source_jdbcUrl': "jdbc:sqlserver://{0}:{1};DatabaseName={2};".format(sourceip, sourceport, sourcedb),
        'target_jdbcUrl': "jdbc:sqlserver://{0}:{1};DatabaseName={2};".format(targetip, targetport, targetdb),
        'readername': 'reader',
        'writername': 'writer'

    },
    'oracle': {
        'user': '{user}',
        'password': '{password}',
        'dsn': '{dsn}',  # 实例，例如oracle
        # 添加 oracle 的 jdbc 连接字符串
        'source_jdbcUrl': "jdbc:oracle:thin:@{user}/{password}@{dsn}",
        'target_jdbcUrl': "jdbc:oracle:thin:@{user}/{password}@{dsn}",
        'readername': 'reader',
        'writername': 'writer'
    },

    'gaussdb': {
        'host': '{host}',
        'port': '{port}',
        'user': '{user}',
        'password': '{password}',
        'database': '{database}',
        'charset': 'UTF8',
        # 添加 gaussdb 的 jdbc 连接字符串
        'source_jdbcUrl': "jdbc:postgresql://{0}:{1}/{2}".format(sourceip, sourceport, sourcedb),
        'target_jdbcUrl': "jdbc:postgresql://{0}:{1}/{2}".format(targetip, targetport, targetdb),
        'readername': 'reader',
        'writername': 'writer'
    }
}

# 数据源连接配置，需修改为对应值
db_config[source_db_type]['host'] = sourceip
db_config[source_db_type]['port'] = sourceport
db_config[source_db_type]['user'] = sourceuser
db_config[source_db_type]['password'] = sourcepw
db_config[source_db_type]['database'] = sourcedb
db_config[source_db_type]['reader'] = reader
source_database_type = db_config[source_db_type]['source_jdbcUrl']

# 目标库的连接配置，需修改为对应值
db_config[target_db_type]['host'] = targetip
db_config[target_db_type]['port'] = targetport
db_config[target_db_type]['user'] = targetuser
db_config[target_db_type]['password'] = targetpw
db_config[target_db_type]['database'] = targetdb
db_config[target_db_type]['writer'] = writer
target_database_type = db_config[target_db_type]['target_jdbcUrl']


# 放置json文件以及数据迁移json脚本文件目录
job_path = './jobs'
log_path = './logs'
migration_tables = './migration_tables.txt'  # 存放需要迁移的表（表必须是一列，也就是一行一个，不要加标点符号）

