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

import cx_Oracle
import psycopg2
import pymssql

from config import *


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
            conn = pymssql.connect(server=db_config['sqlserver']['host'],
                                   port=db_config['sqlserver']['port'],
                                   user=db_config['sqlserver']['user'],
                                   password=db_config['sqlserver']['password'],
                                   database=db_config['sqlserver']['database']
                                   )
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
def get_all_tables_source(source_database_type):
    try:
        # 获取数据库连接和游标对象
        conn, cursor = get_connection_and_cursor(source_database_type, db_config)

        if source_database_type == db_config['mysql']['source_jdbcUrl']:
            cursor.execute("SHOW TABLES")
            source_tables = [table[0] for table in cursor.fetchall()]

        elif source_database_type == db_config['sqlserver']['source_jdbcUrl']:

            cursor.execute(f"SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'dbo' "
                           f"AND TABLE_CATALOG='{db_config['sqlserver']['database']}'")
            # 获取所有表名
            source_tables = [table[0] for table in cursor.fetchall()]


        elif source_database_type == db_config['oracle']['source_jdbcUrl']:

            cursor.execute(f"SELECT table_name FROM all_tables WHERE owner = '{db_config['oracle']['user']}'")
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
    finally:  # 关闭数据库连接和游标对象
        close_connection_and_cursor(conn, cursor)

    return source_tables


# 获取目标库的所有表名
def get_all_tables_target(target_database_type):
    try:
        # 获取数据库连接和游标对象
        conn, cursor = get_connection_and_cursor(target_database_type, db_config)

        if target_database_type == db_config['mysql']['target_jdbcUrl']:
            cursor.execute("SHOW TABLES")
            target_tables = [table[0] for table in cursor.fetchall()]

        elif target_database_type == db_config['sqlserver']['target_jdbcUrl']:

            cursor.execute(f"SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'dbo' "
                           f"AND TABLE_CATALOG='{db_config['sqlserver']['database']}'")
            # 获取所有表名
            target_tables = [table[0] for table in cursor.fetchall()]


        elif target_database_type == db_config['oracle']['target_jdbcUrl']:

            cursor.execute(f"SELECT table_name FROM all_tables WHERE owner = '{db_config['oracle']['user']}'")
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
    finally:  # 关闭数据库连接和游标对象
        close_connection_and_cursor(conn, cursor)
    return target_tables


# 获取源表的所有字段
def get_table_columns_source(source_database_type, source_table_name):
    try:
        # 获取数据库连接和游标对象
        conn, cursor = get_connection_and_cursor(source_database_type, db_config)

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
            source_columns = [column[0].upper() for column in cursor.fetchall()]
            if not source_columns:
                logging.warning(f"{source_table_name}表字段为空")  # 使用logging.warning()方法记录
    except Exception as e:
        logging.error(f"获取源数据库表字段失败：{e}")  # 使用logging.error()方法记录错误信息
        raise e
    finally:  # 关闭数据库连接和游标对象
        close_connection_and_cursor(conn, cursor)
    return source_columns


# 获取目标表的所有字段
def get_table_columns_target(target_database_type, target_table_name):
    try:
        # 获取数据库连接和游标对象
        conn, cursor = get_connection_and_cursor(target_database_type, db_config)

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
            target_columns = [column[0].upper() for column in cursor.fetchall()]
            if not target_columns:
                logging.warning(f"{target_table_name}表字段为空")  # 使用logging.warning()方法记录
        else:
            raise ValueError("不支持的数据库类型。")
    except Exception as e:
        logging.error(f"获取目标数据库表字段失败：{e}")  # 使用logging.error()方法记录错误信息
        raise e
    finally:  # 关闭数据库连接和游标对象
        close_connection_and_cursor(conn, cursor)

    return target_columns


# 生成json格式字典
def generate_data_dict(source_columns, target_columns, source_db_type, target_db_type, source_table_name,
                       target_table_name):
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
                            "splitPk": "",
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
    with open(file_name, "w", encoding="utf-8") as file:
        file.truncate(0)  # 清空文件大小为0
        file.write(json_data)


# 生成单个表的json文件
def generate_table_json(source_database_type, target_database_type, source_table_name, target_table_name, job_path):
    source_columns = get_table_columns_source(source_database_type, source_table_name)
    target_columns = get_table_columns_target(target_database_type, target_table_name)

    # 比较两个列表是否相等，不管它们的顺序和大小写
    def compare_lists(list1, list2):
        return sorted([str(item).lower() for item in list1]) == sorted([str(item).lower() for item in list2])

    # 检查两张表字段是否一致
    if compare_lists(source_columns, target_columns):
        # 如果一致则定义数据字典并生成json文件
        data = generate_data_dict(source_columns, target_columns, source_db_type, target_db_type, source_table_name,
                                  target_table_name)  # json的字典
        generate_json_file(data, job_path, source_table_name)  # 根据json字典生成json文件
    else:
        # 如果不一致，把target_columns按照source_columns 进行排列
        try:
            assert source_columns and target_columns
            target_columns = [col for col in source_columns if col.lower() in map(str.lower, target_columns)] + \
                             [col for col in target_columns if col.lower() not in map(str.lower, source_columns)]
        except AssertionError:
            print("源表字段或者目标表字段是空的!")
            return
        except AttributeError:
            print("源表字段或目标表列表中包含非字符串元素")
            return

        # 再次使用这个函数来检查两张表字段是否一致
        if compare_lists(source_columns, target_columns):
            # 如果一致则定义数据字典并生成json文件
            data = generate_data_dict(source_columns, target_columns, source_db_type, target_db_type, source_table_name,
                                      target_table_name)  # 调用封装的函数
            generate_json_file(data, job_path, source_table_name)  # 调用封装的函数
        else:
            # 如果还不一致则跳过执行
            logging.warning(f"{source_table_name}源表和目标表列信息不一致,跳过该表迁移")
            return  # 退出函数，不生成json文件


# 根据源数据库类型和目标数据库类型，自动生成所有的表的json脚本
def generate_all_table_json(source_database_type, target_database_type):
    target_tables = get_all_tables_target(target_database_type)
    source_tables = get_all_tables_source(source_database_type)

    for source_table_name in source_tables:
        matching_tables = [target_table for target_table in target_tables if target_table == source_table_name]

        if matching_tables:
            # 在目标数据库中找到匹配的表
            target_table_name = matching_tables[0]
            # 根据源数据库类型和目标数据库类型，自动生成单个表的json脚本
            generate_table_json(source_database_type, target_database_type, source_table_name, target_table_name,
                                job_path)
        else:
            # 在目标数据库中没有找到匹配的表
            logging.warning(f"源库的{source_table_name}表在目标库{target_db_type}中不存在")



class MigrationData:  # 定义一个数据迁移类
    def __init__(self):
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


        # 设置日志的格式和级别
        logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

    # 根据表名找到所有jobs对应的json执行脚本
    def findfiles(self, var, migration_job_path):
        result = {}
        # 判断文件是否是一个普通文件
        if not os.path.isfile(migration_job_path):
            # 创建一个空文件
            open(migration_job_path, 'w', encoding='utf-8').close()
        # 创建一个Path对象，表示目录路径
        dir_path = pathlib.Path(var)
        # 读取文本文件中的表名，并去掉换行符
        with open(migration_job_path, 'r', encoding='utf-8') as f:
            tables = [table.strip() for table in f.readlines()]
        # 循环遍历表名，构造json文件的路径，并存入结果字典中
        for table in tables:
            # 使用os.path.join来拼接路径，并转换为字符串
            json_file = str(os.path.join(dir_path, f"{table}.json"))
            # 检查json文件是否存在
            if not os.path.isfile(json_file):
                # 如果不存在，则输出提示信息并退出程序
                print(f"没有找到{table}表的json文件，请检查./jobs目录下是否有该文件")
                exit()
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
            logging.error(f"{job}执行失败")
            with self.lock:  # 控制任务数
                self.namespace.failed += 1
            return False
        else:
            with self.lock:
                self.namespace.running -= 1
                self.namespace.succeed += 1
            logging.info(f"{job}执行成功")
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
                log_file = os.path.abspath(os.path.join(log_path, f"{table}.log"))  # 用于构造日志文件的路径
                future = t_executor.submit(self.run_datax, job, log_file)  # 提交任务，并将返回的 Future 对象添加到 futures 列表中
                futures.append((table, future))

            # 循环遍历 futures 列表，等待每个任务完成，并处理输出和异常
            for table, future in futures:
                try:
                    if not future.result(timeout=3600):  # 设置一个超时时间为 3600 秒，即 1 小时，如果超时，则抛出异常
                        if table not in failed_tables:
                            logging.error(f"表{table}迁移失败")
                        failed_tables.add(table)
                except TimeoutError as e:
                    logging.error(f"表{table}迁移超时，错误信息：{e}")
                    failed_tables.add(table)

    # 创建一个最大进程数为 num_processes 的进程池，调用asyncexecjob执行任务
    def execJobs(self, jobpath, max_processes, max_threads):
        logging.info('迁移开始')
        starttime = time.time() # 记录开始执行的时间
        jobs = self.findfiles(jobpath, migration_tables) # 获取所有待执行的作业文件
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
            futures = [p_executor.submit(self.asyncexecjob, sub_queue) for sub_queue in sub_task_queues]  # 提交任务
            # 循环遍历 futures 列表，等待每个任务完成，并处理输出和异常
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logging.error(str(e))

    # 打印任务执行情况
    def taskDetails(self):
        print("待执行 %d 个,正在执行 %d 个,执行成功 %d 个, 执行失败 %d 个\n" % (
            self.namespace.waiting, self.namespace.running, self.namespace.succeed, self.namespace.failed))

    # 监控任务执行情况
    def monitorTask(self):
        time.sleep(1)
        while True:
            with self.lock:
                self.taskDetails()
            time.sleep(2)
            if self.namespace.waiting == 0 and self.namespace.running == 0:
                break
        with self.lock:
            self.taskDetails()  # 在循环结束后再打印一次任务执行情况
        logging.info('迁移结束')


if __name__ == '__main__':
    multiprocessing.freeze_support()  # 防止windows下运行报错
    generate_all_table_json(source_database_type,target_database_type)
    manager = multiprocessing.Manager()
    lock = manager.Lock()
    migrate = MigrationData()
    t = threading.Thread(target=migrate.monitorTask)  # 监控任务执行情况
    t.daemon = True
    t.start()
    migrate.execJobs(job_path, num_processes, num_threads)
    t.join()