import pandas as pd
import datetime
import pymysql
from sqlalchemy import create_engine
import assasin_beatch

DB_HOST = assasin_beatch.HOST
DB_NAME = 'analytics'
DB_LOGIN = 'root'
DB_PASS = assasin_beatch.DB_PASS
TABLE_NAME = 'cron_testing'

engine = create_engine('mysql+pymysql://{0}:{1}@{2}/{3}'.format(DB_LOGIN, DB_PASS, DB_HOST, DB_NAME))

pd.DataFrame({
                'datetime':[datetime.datetime.now()],
                'message':['daemon cron works']
            }).to_sql(TABLE_NAME,con = engine,if_exists='append',index=False)
