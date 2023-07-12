# coding=utf-8

import concurrent.futures
import json
import logging
import multiprocessing
import pathlib
import subprocess
import threading
import time
from concurrent.futures import as_completed
import pyodbc
#import cx_Oracle
import psycopg2
import pymssql
from tqdm import tqdm

from config import *

# 设置日志的格式和级别
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO)


# 读取migration_tables.txt文件,获取所有的表名和分片字段
def get_tables_and_split():
    tables = []
    split_columns = []
    with open(migration_tables) as f:
        for line in f:
            # 如果是空行或者以#开头，则跳过
            if line.strip() == '' or line.strip().startswith('#'):
                continue
            if line.strip() == '*':  # 如果是*，则表示所有表
                tables = ['*']
                split_columns = ['']
                break
            elif ":" in line:
                # 如果是:，则表示表名和分片字段
                table, split_column = line.strip().split(":", 1)
            else:
                table = line.strip()  # 如果没有:，则表示只有表名
                split_column = ""
            tables.append(table)
            split_columns.append(split_column)

    return tables, split_columns


# 获取数据库连接和游标对象，根据不同的数据库类型传入不同的数据库配置
def get_connection_and_cursor(database_type, db_config):
    try:
        if database_type == db_config['mysql']['source_jdbcUrl'] \
                or database_type == db_config['mysql']['target_jdbcUrl']:
            conn = pymysql.connect(**db_config['mysql'])
            cursor = conn.cursor()
            return conn, cursor
        elif database_type == db_config['sqlserver']['source_jdbcUrl'] \
                or database_type == db_config['sqlserver']['target_jdbcUrl']:
            conn = pyodbc.connect(f'DRIVER={{ODBC Driver 17 for SQL Server}};'
                                  f'SERVER={db_config["sqlserver"]["host"]};'
                                  f'PORT={db_config["sqlserver"]["port"]};'
                                  f'DATABASE={db_config["sqlserver"]["database"]};'
                                  f'UID={db_config["sqlserver"]["user"]};'
                                  f'PWD={db_config["sqlserver"]["password"]}')

            cursor = conn.cursor()
            return conn, cursor
        elif database_type == db_config['oracle']['source_jdbcUrl'] \
                or database_type == db_config['oracle']['target_jdbcUrl']:
            conn = cx_Oracle.connect(db_config['oracle']['user'],
                                     db_config['oracle']['password'],
                                     db_config['oracle']['dsn'])
            cursor = conn.cursor()
            return conn, cursor
        elif database_type == db_config['gaussdb']['source_jdbcUrl'] \
                or database_type == db_config['gaussdb']['target_jdbcUrl']:
            conn = psycopg2.connect(
                host=db_config['gaussdb']['host'],
                port=db_config['gaussdb']['port'],
                user=db_config['gaussdb']['user'],
                password=db_config['gaussdb']['password'],
                database=db_config['gaussdb']['database']
            )
            cursor = conn.cursor()
            return conn, cursor
        else:
            raise ValueError("不支持的数据库类型。")
    except Exception as e:
        logging.error(f"获取数据库连接和游标对象失败：{e}")
        raise e


# 关闭数据库连接和游标对象
def close_connection_and_cursor(conn, cursor):
    try:
        cursor.close()
        conn.close()
    except Exception as e:
        logging.error(f"关闭数据库连接和游标对象失败：{e}")
        raise e


# 获取源库的所有表名
def get_all_tables_source(source_database_type, tables):
    try:
        # 获取数据库连接和游标对象
        conn, cursor = get_connection_and_cursor(
            source_database_type, db_config)

        if source_database_type == db_config['mysql']['source_jdbcUrl']:
            cursor.execute("SHOW TABLES")
            source_tables = [table[0] for table in cursor.fetchall()]

        elif source_database_type == db_config['sqlserver']['source_jdbcUrl']:
            cursor.execute(
                f"SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'dbo' "
                f"AND TABLE_CATALOG='{db_config['sqlserver']['database']}'")
            # 获取所有表名
            source_tables = [table[0] for table in cursor.fetchall()]

        elif source_database_type == db_config['oracle']['source_jdbcUrl']:
            cursor.execute(
                f"SELECT table_name FROM all_tables WHERE owner = '{db_config['oracle']['user']}'")
            source_tables = [table[0] for table in cursor.fetchall()]

        elif source_database_type == db_config['gaussdb']['source_jdbcUrl']:
            cursor.execute(
                f"SELECT table_name FROM information_schema.tables WHERE table_schema = "
                f"'{db_config['gaussdb']['database']}'")
            source_tables = [table[0] for table in cursor.fetchall()]

        else:
            raise ValueError("不支持的数据库类型。")
    except Exception as e:
        logging.error(f"获取源数据库表名失败：{e}")
        raise e
    finally:
        close_connection_and_cursor(conn, cursor)  # 关闭数据库连接和游标对象
    if tables == ['*']:
        return source_tables
    else:
        missing_tables = [table for i, table in enumerate(tables, start=1)
                          if table.lower() not in [t.lower() for t in source_tables]]
        if missing_tables:
            missing_table = missing_tables[0]
            missing_table_index = tables.index(missing_table) + 1
            raise ValueError(
                f"请检查migration_tables中第{missing_table_index}行的表：'{missing_table}'在源数据库中是否存在。")
        else:
            # 根据migration_tables.txt中的表名在数据库中匹配
            source_tables = [table for table in source_tables
                             if table.lower() in [t.lower() for t in tables]
                             or table.upper() in [t.upper() for t in tables]]
            return source_tables


# 获取目标库的所有表名
def get_all_tables_target(target_database_type, tables):
    try:
        # 获取数据库连接和游标对象
        conn, cursor = get_connection_and_cursor(
            target_database_type, db_config)

        if target_database_type == db_config['mysql']['target_jdbcUrl']:
            cursor.execute("SHOW TABLES")
            target_tables = [table[0] for table in cursor.fetchall()]

        elif target_database_type == db_config['sqlserver']['target_jdbcUrl']:

            cursor.execute(
                f"SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'dbo' "
                f"AND TABLE_CATALOG='{db_config['sqlserver']['database']}'")
            # 获取所有表名
            target_tables = [table[0] for table in cursor.fetchall()]

        elif target_database_type == db_config['oracle']['target_jdbcUrl']:

            cursor.execute(
                f"SELECT table_name FROM all_tables WHERE owner = '{db_config['oracle']['user']}'")
            target_tables = [table[0] for table in cursor.fetchall()]

        elif target_database_type == db_config['gaussdb']['target_jdbcUrl']:

            cursor.execute(
                f"SELECT table_name FROM information_schema.tables WHERE table_schema = "
                f"'{db_config['gaussdb']['database']}'")
            target_tables = [table[0] for table in cursor.fetchall()]
        else:
            raise ValueError("不支持的数据库类型。")
    except Exception as e:
        logging.error(f"获取目标数据库表名失败：{e}")
        raise e
    finally:
        close_connection_and_cursor(conn, cursor)  # 关闭数据库连接和游标对象
    if tables == ['*']:  # 如果migration_tables.txt中的表名为*，则返回所有表名
        return target_tables
    else:
        # 如果migration_tables.txt中的表名不为*，则判断migration_tables.txt中的表名是否在目标数据库中存在
        missing_tables = [table for i, table in enumerate(tables, start=1)
                          if table.lower() not in [t.lower() for t in target_tables]]
        if missing_tables:
            missing_table = missing_tables[0]
            missing_table_index = tables.index(missing_table) + 1
            raise ValueError(
                f"请检查migration_tables中第{missing_table_index}行的表：'{missing_table}'在目标数据库中是否存在。")
        else:
            # 根据migration_tables.txt中的表名在数据库中匹配
            target_tables = [table for table in target_tables
                             if table.lower() in [t.lower() for t in tables]
                             or table.upper() in [t.upper() for t in tables]]

            return target_tables



# 获取源表的所有字段
def get_table_columns_source(source_database_type, source_table_name):
    try:
        # 获取数据库连接和游标对象
        conn, cursor = get_connection_and_cursor(
            source_database_type, db_config)

        if source_database_type == db_config['mysql']['source_jdbcUrl']:
            cursor.execute(f"SHOW COLUMNS FROM {source_table_name}")
            source_columns = [column[0] for column in cursor.fetchall()]

        elif source_database_type == db_config['sqlserver']['source_jdbcUrl']:
            cursor.execute(
                f"SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = '{source_table_name}'")
            source_columns = [column[0] for column in cursor.fetchall()]

        elif source_database_type == db_config['oracle']['source_jdbcUrl']:
            cursor.execute(
                f"SELECT column_name FROM all_tab_columns WHERE owner = '{db_config['oracle']['user']}' "
                f"AND table_name = '{source_table_name}'")
            source_columns = [column[0] for column in cursor.fetchall()]

        elif source_database_type == db_config['gaussdb']['source_jdbcUrl']:
            cursor.execute(
                f"SELECT column_name FROM information_schema.columns WHERE table_schema = "
                f"'{db_config['gaussdb']['database']}' AND table_name = '{source_table_name}'")
            source_columns = [column[0]
                              for column in cursor.fetchall()]
            if not source_columns:
                # 使用logging.warning()方法记录
                logging.warning(f"{source_table_name}表字段为空")
    except Exception as e:
        logging.error(f"获取源数据库表字段失败：{e}")  # 使用logging.error()方法记录错误信息
        raise e
    finally:  # 关闭数据库连接和游标对象
        close_connection_and_cursor(conn, cursor)

    return source_columns


# 获取目标表的所有字段
def get_table_columns_target(target_database_type, target_table_name, split_columns):
    try:
        # 获取数据库连接和游标对象
        conn, cursor = get_connection_and_cursor(
            target_database_type, db_config)

        if target_database_type == db_config['mysql']['target_jdbcUrl']:
            cursor.execute(f"SHOW COLUMNS FROM {target_table_name}")
            target_columns = [column[0] for column in cursor.fetchall()]

        elif target_database_type == db_config['sqlserver']['target_jdbcUrl']:
            cursor.execute(
                f"SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME  = '{target_table_name}'")
            target_columns = [column[0] for column in cursor.fetchall()]

        elif target_database_type == db_config['oracle']['target_jdbcUrl']:
            cursor.execute(
                f"SELECT column_name FROM all_tab_columns WHERE owner = "
                f"'{db_config['oracle']['user']}' AND table_name = '{target_table_name}'")
            target_columns = [column[0] for column in cursor.fetchall()]

        elif target_database_type == db_config['gaussdb']['target_jdbcUrl']:
            cursor.execute(
                f"SELECT column_name FROM information_schema.columns WHERE "
                f"table_schema = '{db_config['gaussdb']['database']}' AND table_name = '{target_table_name}'")
            target_columns = [column[0].upper()
                              for column in cursor.fetchall()]
            if not target_columns:
                logging.warning(f"{target_table_name}表字段为空")
        else:
            raise ValueError("不支持的数据库类型。")
    except Exception as e:
        logging.error(f"获取目标数据库表字段失败：{e}")
        raise e
    finally:  # 关闭数据库连接和游标对象
        close_connection_and_cursor(conn, cursor)

    # 判断目标表是否有分片字段,并且保持分片字段的大小写与源表一致
    for index, table in enumerate(tables):
        if table.lower() == target_table_name or table.upper() == target_table_name:
            index = tables.index(table)
            split_column = split_columns[index]
            # 判断target_table_name是大写还是小写
            if target_table_name.isupper():
                split_column = split_column.upper()
            else:
                split_column = split_column.lower()
            if split_column:
                # 检查 split_column 是否在 target_columns 中,否则抛出异常
                if split_column not in target_columns:
                    raise ValueError(f"目标库的{target_table_name}表中的分片字段:{split_column}不正确,请认真检查。")
            break
    else:
        split_column = ''
    return target_columns, split_column


# 生成json格式字典
def generate_data_dict(source_columns, target_columns, source_database_type, target_database_type, source_table_name,
                       target_table_name, split_column):
    data = {
        "job": {
            "setting": {
                "speed": {
                    "channel": 20
                },
                "errorLimit": {
                    "record": 0
                }
            },
            "content": [
                {
                    "reader": {
                        "name": db_config[source_db_type]['reader'],
                        "parameter": {
                            "username": db_config[source_db_type]['user'],
                            "password": db_config[source_db_type]['password'],
                            "column": source_columns,
                            "splitPk": split_column,
                            "connection": [
                                {
                                    "table": [source_table_name],
                                    "jdbcUrl": [source_database_type]
                                }
                            ]
                        }
                    },
                    "writer": {
                        "name": db_config[target_db_type]['writer'],
                        "parameter": {
                            "username": db_config[target_db_type]['user'],
                            "password": db_config[target_db_type]['password'],
                            "column": target_columns,
                            "preSql": [f"TRUNCATE TABLE {target_table_name}"],
                            "connection": [
                                {
                                    "jdbcUrl": target_database_type,
                                    "table": [target_table_name]
                                }
                            ]
                        }
                    }
                }
            ]
        }
    }
    return data


# 生成 JSON 文件并保存到指定路径
def generate_json_file(data, job_path, source_table_name):
    json_data = json.dumps(data, indent=4)
    file_name = os.path.join(job_path, f"{source_table_name}.json")
    if not os.path.exists(os.path.dirname(file_name)):
        os.makedirs(os.path.dirname(file_name), exist_ok=True)
    with open(file_name, "w", encoding="utf-8") as file:  # 清空json文件并且写入json
        file.truncate(0)
        file.write(json_data)


# 生成单个表的json文件
def generate_table_json(source_database_type, target_database_type, source_table_name, target_table_name,
                        job_path, split_columns):
    source_columns = get_table_columns_source(source_database_type, source_table_name)
    target_columns, split_column = get_table_columns_target(target_database_type, target_table_name
                                                            , split_columns)
    # 比较源库和目标库的字段个数是否相等,如果不相等则检查是哪张表的哪个字段不一致
    if len(source_columns) != len(target_columns):
        source_left = [col for col in source_columns if col.lower() not in [c.lower() for c in target_columns]]
        target_left = [col for col in target_columns if col.lower() not in [c.lower() for c in source_columns]]
        if source_left:  # 如果source_left不为空，则说明源库中存在而目标库中不存在的字段
            logging.warning(f"源库{source_table_name}表中的字段:{','.join(source_left)}"
                            f"在目标数据库的表中未发现,已跳过该表生成json文件。")
            return 0, source_table_name
        if target_left:  # 如果target_left不为空，则说明目标库中存在而源库中不存在的字段
            logging.warning(f"目标库{target_table_name}表中的字段:{','.join(target_left)}"
                            f"在目标数据库的表中未发现,已跳过该表生成json文件。")
            return 0, source_table_name
    else:
        data = generate_data_dict(source_columns, target_columns, source_database_type, target_database_type,
                                  source_table_name, target_table_name, split_column)
        generate_json_file(data, job_path, source_table_name)
        return 1, []


def generate_all_table_json(source_database_type, target_database_type, tables, split_columns):
    logging.info("请稍等，正在开始生成json脚本...")
    # 获取源数据库的所有表名
    source_tables = get_all_tables_source(source_database_type, tables)
    # 获取目标数据库的所有表名
    target_tables = get_all_tables_target(target_database_type, tables)
    # 判断source_tables和target_tables是否为空，如果为空直接返回
    if not source_tables or not target_tables:
        logging.warning("请检查源库表名或目标库表名是否为空!")
        return
    successful_table = 0  # 记录成功生成json文件的表名
    matched_tables = []  # 记录成功匹配的表名
    filed_tables = []  # 记录字段不匹配的表名
    total_pbar = tqdm(total=len(source_tables), desc="总进度", leave=False,
                      bar_format='{desc}: {percentage:.0f}%|{bar}| {n_fmt}/{total_fmt}' + '-预计在<{remaining}>后完成  ')
    for i, source_table_name in enumerate(source_tables):  # 遍历源表表名
        # 在目标表名列表中查找与源表名匹配的表
        matching_tables = [target_table_name for target_table_name in target_tables
                           if target_table_name.lower() == source_table_name.lower()]
        if matching_tables:  # 如果匹配则取出第一个给目标表
            target_table_name = matching_tables[0]
            matched_tables.append(target_table_name)
            # 生成单个表的json迁移文件
            successful_tables = generate_table_json(source_database_type, target_database_type, source_table_name,
                                                    target_table_name, job_path, split_columns)
            if successful_tables[0] == 1:
                successful_table += 1
            else:
                successful_table += 0
                filed_tables.append(successful_tables[1])
        total_pbar.update(1)  # 更新总进度条
    # total_pbar.close()  # 关闭总进度条
    logging.info(f"总共生成了{successful_table}张表的JSON脚本文件，耗时{total_pbar.format_dict['elapsed']}s")
    if all(source_table.islower() for source_table in source_tables):
        matched_tables = [table.lower() for table in matched_tables]
    if all(source_table.isupper() for source_table in source_tables):
        matched_tables = [table.upper() for table in matched_tables]

    return matched_tables


class MigrationData:  # 定义一个数据迁移类
    def __init__(self):
        self.task_finished = None
        self.exec_time = 0
        # 创建一个Manager对象
        manager = multiprocessing.Manager()
        # 创建一个共享的命名空间
        self.namespace = manager.Namespace()
        # 定义self.lock变量
        self.lock = manager.Lock()
        # 把这四个变量放在命名空间里
        self.namespace.waiting = 0
        self.namespace.running = 0
        self.namespace.succeed = 0
        self.namespace.failed = 0

    # 根据表名找到所有jobs对应的json执行脚本
    def findfiles(self, var, migration_job_path, matched_tables):
        result = {}
        # 判断文件是否是一个普通文件
        if not os.path.isfile(migration_job_path):
            # 创建一个空文件
            open(migration_job_path, 'w', encoding='utf-8').close()
        # 创建一个Path对象，表示目录路径
        dir_path = pathlib.Path(var)
        # 循环遍历表名，构造json文件的路径，并存入结果字典中
        for table in matched_tables:
            # 使用os.path.join来拼接路径，并转换为字符串
            json_file = str(os.path.join(dir_path, f"{table}.json"))
            # 检查json文件是否存在
            if not os.path.isfile(json_file):
                # 如果不存在，则输出提示信息并退出程序
                logging.error(f"没有找到{table}表的json文件，请检查jobs目录下是否有该文件")
                continue
            result[table] = json_file
        self.namespace.waiting = len(result)  # 设置待执行任务数
        return result

    def run_datax(self, job, log_file):  # 定义一个执行datax的函数
        command = f"python {path_datax} {job}"
        with open(log_file, "w") as f:  # 将日志输出到指定的日志文件
            execjob = subprocess.Popen(command, shell=True, stdout=f, stderr=f)
        with self.lock:  # 控制任务数
            self.namespace.waiting -= 1
            self.namespace.running += 1
        returncode = execjob.wait()  # 等待任务执行完
        if returncode != 0:
            logging.error(f"作业任务：{job}执行失败")
            with self.lock:  # 控制任务数
                self.namespace.failed += 1
                self.namespace.running -= 1
            return False
        else:
            with self.lock:
                self.namespace.running -= 1
                self.namespace.succeed += 1
            logging.info(f"作业任务：{job}执行成功")
            return True

    def asyncexecjob(self, task_queue):  # 定义一个异步执行任务的函数
        failed_tables = set()  # 存放执行失败的表名

        # 创建logs目录，如果不存在的话则创建
        if not os.path.exists(log_path):
            os.makedirs(log_path)

        #  创建一个最大线程数为 num_threads 的线程池，调用run_datax执行任务
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as t_executor:
            futures = []  # 创建一个空的 futures 列表
            for table, job in task_queue:  # 迭代任务队列，为每个表名和作业文件提交一个任务
                log_file = os.path.abspath(os.path.join(
                    log_path, f"{table}.log"))  # 用于构造日志文件的路径
                # 提交任务，并将返回的 Future 对象添加到 futures 列表中
                future = t_executor.submit(self.run_datax, job, log_file)
                futures.append((table, future))
            # 循环遍历 futures 列表，等待每个任务完成，并处理输出和异常
            for table, future in futures:
                try:
                    if not future.result(timeout=3600):
                        if table not in failed_tables:
                            logging.error(f"表：{table}迁移失败，请检查logs日志文件")
                        failed_tables.add(table)
                except TimeoutError as e:
                    logging.error(f"表{table}迁移超过一个小时，强制终止，错误信息：{e}")
                    failed_tables.add(table)
                except Exception as e:
                    logging.error(f"表{table}迁移失败，错误信息：{e}")
                    failed_tables.add(table)
        # 定义一个failed_file文件夹，用于存放执行失败的表名
        failed_file = os.path.abspath(os.path.join(log_path, "./failed_file"))
        # 判断在当前目录下是否存在failed_file文件，如果存在则清空，不存在则创建
        if os.path.exists(failed_file):
            open(failed_file, "w").close()
        else:
            open(failed_file, "w").close()
        # 如果有执行失败的表，则把所有失败的表名写入到文件中
        if failed_tables:
            with open(failed_file, "w") as f:
                f.write("\n".join(failed_tables))

    # 创建进程池，调用asyncexecjob执行任务
    def execJobs(self, jobpath, max_processes, max_threads, tables):
        logging.info('迁移开始')
        start_time = time.time()  # 记录开始执行的时间
        jobs = self.findfiles(jobpath, migration_tables, tables)  # 获取所有待执行的作业文件
        task_queue = []  # 创建一个空的任务队列
        for table, job in jobs.items():
            task_queue.append((table, job))  # 将表名和作业文件添加到任务队列中
        task_count = len(task_queue)  # 任务总数
        # 根据任务总数和最大进程数，计算出实际的进程数
        if max_processes is None or max_processes < 1:
            num_processes = min(4, task_count)
        else:
            num_processes = min(max_processes, task_count)

        if max_threads is None or max_threads < 1:
            num_threads = min(4, task_count)
        else:
            num_threads = min(max_threads, task_count)

        sub_task_queues = [[] for _ in range(num_processes)]

        # 将任务队列中的任务均匀分配到各个子队列中
        for index, task in enumerate(task_queue):
            sub_queue_index = index % num_processes
            sub_task_queues[sub_queue_index].append(task)

        # 使用 ProcessPoolExecutor 创建进程池，指定 max_workers 参数为 num_processes
        with concurrent.futures.ProcessPoolExecutor(max_workers=num_processes) as p_executor:
            futures = [
                p_executor.submit(self.asyncexecjob, sub_queue) for sub_queue in sub_task_queues]  # 提交任务
            # 循环遍历 futures 列表，等待每个任务完成，并处理输出和异常
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logging.error(str(e))
        end_time = time.time()  # 记录结束时间
        self.exec_time = end_time - start_time
        t = threading.Thread(target=self.monitorTask, args=(self.exec_time,))
        t.start()
        t.join()
        logging.info(f'迁移结束,迁移总耗时{self.exec_time}秒')

    # 打印任务执行情况
    def taskDetails(self):
        logging.info(
            "待执行 %d 个,正在执行 %d 个,执行成功 %d 个, 执行失败 %d 个\n" %
            (self.namespace.waiting, self.namespace.running, self.namespace.succeed, self.namespace.failed))

    def monitorTask(self, exec_time):
        self.task_finished = False  # 初始化任务状态
        while True:
            with self.lock:
                self.taskDetails()
            time.sleep(5)  # 每3秒监测一次
            if self.namespace.waiting == 0 and self.namespace.running == 0:
                self.task_finished = True
                break
        if not self.task_finished:
            logging.info(f'迁移结束,迁移总耗时{self.exec_time}秒')


if __name__ == '__main__':
    print("=========================================================================================")
    print("||欢迎使用数据迁移工具，请选择是生成json文件并执行数据迁移或者生成json文件，默认生成json文件并执行数据迁移||")
    print("=========================================================================================")
    print("1.生成json文件并执行数据迁移")
    print("2.生成json文件           ")
    print("3.退出                  ")
    print("=========================================================================================")
    input_number = 0
    # 循环输入数字，如果输入的不是1或者2或者3，则一直提示输入
    while True:
        input_num = input("请输入你的选择：")
        if input_num == "1" or input_num == "":
            multiprocessing.freeze_support()  # 防止windows下运行报错
            tables, split_columns = get_tables_and_split()
            matched_tables = generate_all_table_json(source_database_type, target_database_type, tables, split_columns)
            manager = multiprocessing.Manager()
            lock = manager.Lock()
            migrate = MigrationData()
            t = threading.Thread(target=migrate.monitorTask, args=(migrate.exec_time,))  # 监控任务执行情况
            t.daemon = False
            t.start()
            migrate.execJobs(job_path, num_processes, num_threads, matched_tables)
            exit()
        if input_num == "2":
            tables, split_columns = get_tables_and_split()
            generate_all_table_json(source_database_type, target_database_type, tables, split_columns)
            exit()
        if input_num == "3":
            exit()
        else:
            print("输入错误，请重新输入:")
            input_number += 1
            if input_number == 3:
                print("输入错误次数超过3次，还有2次机会，请认真检查后再输入")
            if input_number == 4:
                print("输入错误次数超过4次，还有1次机会，请认真检查后再输入")
            if input_number == 5:
                print("再见！！！")
                exit()
