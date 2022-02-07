# -*- coding: utf-8 -*-
"""
Created on Wed Feb 6 2022

@author: Walling
"""
import os
from os.path import exists
import time
from flask import Flask, request, g, jsonify
from redis import Redis
import urllib, json
from ratelimit import limits, sleep_and_retry
import logging
import requests
import requests_cache

import sqlalchemy.pool as pool
import psycopg2

def getconn():
    c = psycopg2.connect(user=os.environ['DB_USER'], host=os.environ['DB_HOST'], password=os.environ['DB_PASSWORD'], dbname='coins')
    return c

mypool = pool.QueuePool(getconn, max_overflow=-1, pool_size=25)

app = Flask(__name__)
app.secret_key = "dev"

logging.basicConfig(filename='etl.log', level=logging.DEBUG, format=f'%(asctime)s %(levelname)s %(name)s %(threadName)s : %(message)s')

# Use request caching to avoid repeat calls to external API
backend = requests_cache.RedisCache(host='redis', port=6379)
requests_cache.install_cache('coin_gecko_cache', backend=backend, expire_after=180)

# Use redis to provide a global task counter (i.e. task_run)
redis = Redis(host='redis', port=6379)

def get_db():
    """Opens a new database connection if there is none yet for the
    current application context.
    """
    if not hasattr(g, 'conn_db'):
        g.conn_db = mypool.connect()
    return g.conn_db

@app.before_request
def before_request():
    g.start_time = time.time()

@app.after_request
def after_request(response):
    print(f"Time used: {time.time() - g.start_time}", flush=True)
    app.logger.info((f"Time used: {time.time() - g.start_time}"))
    get_db().close()
    return response
     
@app.teardown_appcontext
def close_connection(exception):
    if hasattr(g, 'conn_db'):
        g.conn_db.close()

@sleep_and_retry
@limits(calls=50, period=60)
def get_exchanges(id):
    """
    Call CoinGecko API endpoint and extract unique tickers[].market.identifier values
    """
    url = "https://api.coingecko.com/api/v3/coins/%s/tickers" % id
    data = requests.get(url).json()
    # If pulling from Redis cache, requests.exceptions aren't thrown
    # Manually check for cached error response
    if 'error' in data.keys():
        return None 
    return(data)
      
@app.route('/coin_id_transform', methods=['POST'])
def coin_id_transform():
    
    task_run = redis.incr('hits') # Use redis to keep track of a global request/task count
    
    if (request.content_type.startswith('application/json')):
        data = request.json
        ids = data['coins']    
    elif (request.content_type.startswith('text/csv')):
        data = request.data
        ids = data.decode().split('\n')[1:] # Skip header
        ids = [i for i in ids if i] # Remove any blank lines
    else:
        return('Invalid Content-Type', 400)
    
    result = []
    for id in ids:
        try:
            data = get_exchanges(id) #Either returns dict, None or raises Exception to be caught here
            if data:
                exchanges = list(set([x['market']['identifier'] for x in data['tickers']]))
            else:
                continue
        except requests.exceptions.HTTPError as e:
            if e.code == 404:
                continue # Ignore coins not found
            else:
                return(str(e), 424) # 424 = Failed Dependency
        except requests.exceptions.ConnectionError :
            return('Cannot reach CoinGecko', 424) # 424 = Failed Dependency
        except Exception as e:
            app.logger.error("Unhandled exception" + str(e))
            return('Unhandled exception', 500)
        
        # Check if entry exists
        row =  get_db().cursor().execute("select id, exchanges from coins where id='%s'" % id)
        # Store sorted list as string for quick comparison
        exchanges.sort()
        str_exchanges = json.dumps(exchanges).replace("[", "{").replace("]", "}") # Format for postgres text column insert
        #row = row.first()
        if not row:
            app.logger.info("Inserting id = " + id)
            get_db().cursor().execute("insert into coins (id, exchanges, task_run) values ('%s', '%s', %s)" % (id, str_exchanges, task_run))
            get_db().commit()
            result.append({"id": id, "exchanges": exchanges, "task_run": task_run})
        else:
            # If the exchanges in db doesn't match, update it
            db_exchanges = row[1]
            if not set(db_exchanges)==set(exchanges):
                app.logger.info('Updating id = ' + id)
                get_db().cursor().execute("update coins set exchanges='%s' where id = '%s'" % (str_exchanges, id))
                get_db().commit()
            result.append({"id": id, "exchanges": exchanges, "task_run": row[2]})
            
    return(json.dumps(result), 200)

if __name__ == "__main__":

    app.run(host="0.0.0.0", debug=True, threaded=True)