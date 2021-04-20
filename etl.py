import configparser
import psycopg2
from sql_queries import copy_table_queries, insert_table_queries


def load_staging_tables(cur, conn, ARN=None):
    config = configparser.ConfigParser()
    config.read_file(open('dwh.cfg'))
    for query in copy_table_queries:
        if not config.get('IAM_ROLE','ARN'):
            cur.execute(query.replace('aws_iam_role=','aws_iam_role={}'.format(ARN)))
        else:
            cur.execute(query)
        conn.commit()


def insert_tables(cur, conn):
    for query in insert_table_queries:
        cur.execute(query)
        conn.commit()


def main(cluster=None, ARN=None):
    config = configparser.ConfigParser()
    config.read('dwh.cfg')

    if cluster is None:
        conn = psycopg2.connect("host={} dbname={} user={} password={} port={}".format(*config['CLUSTER'].values()))
    else:
        conn = psycopg2.connect("host={} dbname={} user={} password={} port={}".format(*cluster))
    cur = conn.cursor()
    
    load_staging_tables(cur, conn, ARN)
    insert_tables(cur, conn)

    conn.close()


if __name__ == "__main__":
    main()