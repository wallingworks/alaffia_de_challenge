# -*- coding: utf-8 -*-
"""
Created on Wed Feb 6 2022

@author: Walling
"""
import os
from os.path import exists
import time
from flask import Flask, request, g, jsonify
from werkzeug.middleware.profiler import ProfilerMiddleware
from redis import Redis
import json
from ratelimit import limits, RateLimitException, sleep_and_retry
from backoff import on_exception, expo
import logging
import requests

import sqlalchemy.pool as pool
import psycopg2

def getconn():
    c = psycopg2.connect(user=os.environ['DB_USER'], host=os.environ['DB_HOST'], password=os.environ['DB_PASSWORD'], dbname='coins')
    return c

mypool = pool.QueuePool(getconn, max_overflow=10, pool_size=25)

app = Flask(__name__)
app.secret_key = "dev"
#app.config['PROFILE'] = False
#app.wsgi_app = ProfilerMiddleware(app.wsgi_app, restrictions=[30])

logging.basicConfig(filename='etl.log', level=logging.DEBUG, format=f'%(asctime)s %(levelname)s %(name)s %(threadName)s : %(message)s')


# Use redis to provide a global task counter (i.e. task_run) and cache ids 
# Only re-process id if hasn't been processed for 10 seconds
redis_cache = Redis(host='redis', port=6379, db=0)

# Use redis to 'throttle' reponses
redis_throttle = Redis(host='redis', port=6379, db=1)
THROTTLE_MAX_CALLS=50
THROTTLE_WINDOW_SECS=60

def get_db():
    """Opens a new database connection if there is none yet for the
    current application context.
    """
    if not hasattr(g, 'conn_db'):
        g.conn_db = mypool.connect()
    return g.conn_db

@app.teardown_appcontext
def close_connection(exception):
    if hasattr(g, 'conn_db'):
        g.conn_db.close()
        
@app.before_request
def before_request():
    g.start_time = time.time()

@app.after_request
def after_request(response):
    print(f"Time used: {time.time() - g.start_time}", flush=True) #  Output to console immediately
    app.logger.info((f"Time used: {time.time() - g.start_time}"))
    return response

def throttle(task_run):
    """
    Redis backed method for throttling
    """
    while redis_throttle.dbsize() == THROTTLE_MAX_CALLS:
        print('Waiting', flush=True)
        time.sleep(1)
    redis_throttle.set(task_run, task_run, ex=THROTTLE_WINDOW_SECS)

#@on_exception(expo, RateLimitException, max_tries=8)
#@sleep_and_retry
#@limits(calls=50, period=60)
def get_exchanges(id, task_run):
    """
    Call CoinGecko API endpoint and extract unique tickers[].market.identifier values
    """
    throttle(task_run)
    
    url = "https://api.coingecko.com/api/v3/coins/%s/tickers" % id
    r = requests.get(url)
    r.raise_for_status() # Ensure exception thrown on 400/500 responses
    data = requests.get(url).json()
    
    # Extract relevant information
    exchanges = list(set([x['market']['identifier'] for x in data['tickers']]))
    
    return(exchanges)
      
@app.route('/coin_id_transform', methods=['POST'])
def coin_id_transform():
    
    task_run = redis_cache.incr('hits') # Use redis to keep track of a global request/task count
    #print(task_run, flush=True)
    if (request.content_type.startswith('application/json')):
        data = request.json
        ids = data['coins']    
    elif (request.content_type.startswith('text/csv')):
        data = request.data
        ids = data.decode().split('\n')[1:] # Skip header 
    else:
        return('Invalid Content-Type', 400)

    ids = [i for i in ids if i] # Remove any blank ids
    result = []
    exchanges = None
    for id in ids:
        print(id, flush=True)
        # Check if id has been requested from coin gecko in last 10 seconds
        # If it has, it should either be in the db (1) or was previously ignored (2)
        redis_cache_val = redis_cache.get(id)
        if redis_cache_val is None:
            try:
                exchanges = get_exchanges(id, task_run) #Either returns dict, None or raises Exception to be caught here
                redis_cache.set(id, 1, ex=10) # Don't re-process for at least 10 seconds, data was found
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 404:
                    redis_cache.set(id, 2, ex=10) # Don't re-process for at least 10 seconds
                    continue # Ignore coins not found in CoinGecko
                else:
                    return(str(e), 424) # 424 = Failed Dependency
            except requests.exceptions.ConnectionError :
                return('Cannot reach CoinGecko', 424) # 424 = Failed Dependency
            except requests.exceptions.RequestException as e:
                app.logger.error("Unhandled exception" + str(e))
                return('Unhandled exception', 500)
        
        # If previously ignored, ignore again
        if redis_cache_val == b'2':
            continue
        else: 
            conn = get_db()
            cursor = conn.cursor() #psycopg2 cursor
            cursor.execute("select id, exchanges, task_run from coins where id='%s'" % id)
            row = cursor.fetchone()
            # If we have fresh 'exchanges' data from coin gecko, check if need to insert/update db
            if exchanges:
                # Check if entry exists
                # Store sorted list as string for quick comparison
                exchanges.sort()
                str_exchanges = format_text_array_db(json.dumps(exchanges))
                if not row:
                    print("Inserting id = " + id, flush=True)
                    app.logger.info("Inserting id = " + id)
                    cursor.execute("insert into coins (id, exchanges, task_run) values ('%s', '%s', %s)" % (id, str_exchanges, task_run))
                    conn.commit()
                    result.append({"id": id, "exchanges": exchanges, "task_run": task_run})
                else:
                    # If the exchanges in db doesn't match, update it
                    db_exchanges = row[1]
                    if not db_exchanges==str_exchanges:
                        print("Updating id = " + id, flush=True)
                        app.logger.info('Updating id = ' + id)
                        cursor.execute("update coins set exchanges='%s' where id = '%s'" % (str_exchanges, id))
                        conn.commit()
                    result.append({"id": id, "exchanges": exchanges, "task_run": row[2]})
            # Otherwise, just return information from db
            elif row:
                json_exchanges = json.loads(format_text_array_json(row[1]))
                result.append({"id": id, "exchanges": json_exchanges, "task_run": row[2]})
            
    return(json.dumps(result), 200)

def format_text_array_json(value):
    # Format from postgres -> json.dumps
    return value.replace("{", "[").replace("}", "]")
    
def format_text_array_db(value):
    # Format from json.dumps -> postgres
    return value.replace("[", "{").replace("]", "}")
    
if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True, threaded=False)