import requests
import pandas as pd
import datetime
import json
import time
import pymysql
from io import StringIO
from sqlalchemy import create_engine
import assasin_beatch

# program parameters
# time between checking status
TIME_TO_SLEEP = 10
# number of loops to raise error
LOOP_ERROR_N = 50

# out database
DB_HOST = assasin_beatch.HOST
DB_NAME = 'analytics'
DB_LOGIN = 'root'
DB_PASS = assasin_beatch.DB_PASS
TABLE_NAME = 'logs_api_data'
engine = create_engine(
    'mysql+pymysql://{0}:{1}@{2}/{3}'.format(DB_LOGIN, DB_PASS, DB_HOST, DB_NAME))

# logs api parameters
TOKEN = assasin_beatch.TOKEN
COUNTER_ID = 44147844
START_DATE = '2019-05-01'
END_DATE = '2019-05-02'
SOURCE = 'hits'
API_HOST = 'https://api-metrika.yandex.ru'
API_FIELDS = (
    'ym:pv:counterID',
    'ym:pv:clientID',
    'ym:pv:watchID',
    'ym:pv:dateTime',
    'ym:pv:lastTrafficSource',
    'ym:pv:URL',
    'ym:pv:goalsID')

params = {
    'date1': START_DATE,
    'date2': END_DATE,
    'source': SOURCE,
    'fields': ','.join(sorted(API_FIELDS, key=lambda s: s.lower()))
}


class CreationQueryError(Exception):
    pass


class LoopingError(Exception):
    pass


def eval_query(API_HOST, COUNTER_ID, TOKEN, params):
    '''
        Валидация запроса. Функция шлет запросы к апи и проверяет принимается ли наш запрос.
        Вернет 200, если запрос принимается, иначе вернет False
    '''

    url = '{host}/management/v1/counter/{counter_id}/logrequests/evaluate'\
        .format(
            host=API_HOST,
            counter_id=COUNTER_ID
        )
    headers = {'Authorization': TOKEN}
    responce = requests.get(url, params=params, headers=headers)

    if responce.status_code == 200:
        return json.loads(responce.text)['log_request_evaluation']['possible']
    else:
        return False


def creating_query(API_HOST, COUNTER_ID, TOKEN, params):
    '''
        Создание запроса. Функция шлет запрос к апи и проверят принялся ли наш запрос (получен ли статус 200) и
        есть ли логи апи на наш запрос. Если все ок, то возвращает ответ.
        Если есть проблемы, то поднимает исключение. 
    '''
    url = '{host}/management/v1/counter/{counter_id}/logrequests'\
        .format(host=API_HOST,
                counter_id=COUNTER_ID)
    headers = {'Authorization': TOKEN}
    responce = requests.post(url, params=params, headers=headers)

    if (responce.status_code == 200) and json.loads(responce.text)['log_request']:
        return responce
    else:
        raise CreationQueryError(responce.text)


def checking_status(API_HOST, COUNTER_ID, TOKEN, request_id):
    '''
        Проверка статуса запроса. Когда мы шлем запрос к апи с помощью функции creating_query, 
        то запрос может быть в состоянии 'created' - создан, то есть не обработан ещё и в состоянии создания.
        Или в состоянии processed - обработан. 
        Функция шлет запрос по request_id, который мы получили от функции creating_query, и 
        возвращает статус (created или processed) нашего запроса, если запрос принимается, иначе поднимает исключение.
    '''
    url = '{host}/management/v1/counter/{counter_id}/logrequest/{request_id}' \
        .format(request_id=request_id,
                counter_id=COUNTER_ID,
                host=API_HOST)
    headers = {'Authorization': TOKEN}
    responce = requests.get(url, params=params, headers=headers)
    if responce.status_code == 200:
        return json.loads(responce.text)['log_request']['status'], responce
    else:
        ValueError(responce.text)


def download(API_HOST, COUNTER_ID, request_id, parts, TOKEN):
    headers = {'Authorization': TOKEN}
    all_dfs = []
    for part in parts:
        part_num = part['part_number']
        url = '{host}/management/v1/counter/{counter_id}/logrequest/{request_id}/part/{part}/download' \
            .format(
                host=API_HOST,
                counter_id=COUNTER_ID,
                request_id=request_id,
                part=part_num
            )
        response = requests.get(url, headers=headers)
        df = pd.read_csv(StringIO(response.text), sep='\t')
        all_dfs.append(df)
    return pd.concat(all_dfs)


def main():
    if eval_query(API_HOST, COUNTER_ID, TOKEN, params):
        created_responce = creating_query(API_HOST, COUNTER_ID, TOKEN, params)
        request_id = json.loads(created_responce.text)[
            'log_request']['request_id']
        status, processed_responce = checking_status(
            API_HOST, COUNTER_ID, TOKEN, request_id)
        print('request_id: {0},checked status: {1}'.format(request_id, status))
        i = 0
        while status == 'created':
            time.sleep(TIME_TO_SLEEP)
            status, processed_responce = checking_status(
                API_HOST, COUNTER_ID, TOKEN, request_id)
            print('request_id: {0},cur status: {1}'.format(request_id, status))
            i += 1
            if i > LOOP_ERROR_N:
                raise LoopingError('request_id:{0}'.format(request_id))
        parts = json.loads(processed_responce.text)['log_request']['parts']
        df = download(API_HOST, COUNTER_ID, request_id, parts, TOKEN)

        for column in API_FIELDS:
            # важный момент, так как яндекс метрика шлет числа, которые могут иметь очень много знаков полсе запятой,
            # то мы преобразуем всё, что не дата в стоку, чтобы потом в базе данных не было переполнения числового типа,
            # чтобы не потерять часть числа
            if column.find('date') < 0:
                df[column] = df[column].astype(str)
            else:
                df[column] = pd.to_datetime(df[column])

        if not df.empty:
            df.to_sql(TABLE_NAME, con=engine, if_exists='append', index=False)
            pd.DataFrame({
                'datetime': [datetime.datetime.now()],
                'message': ['cool, table name: {0}'.format(TABLE_NAME)],
                'is_ok': 1
            }, columns=['datetime', 'message', 'is_ok']).to_sql('logs', con=engine, if_exists='append', index=False)
            print('successfully done')


if __name__ == '__main__':
    try:
        main()
    except Exception as err:
        pd.DataFrame({
            'datetime': [datetime.datetime.now()],
            'message': [err],
            'is_ok': 0
        }, columns=['datetime', 'message', 'is_ok']).to_sql('logs', con=engine, if_exists='append', index=False)
        print('everything broke')
