# -*- coding: utf-8 -*-
"""
Created on Wed Feb 6 2022

@author: Walling
"""
import os
from os.path import exists
import time
from flask import Flask, request, g, jsonify
from flask_caching import Cache 
import sqlite3
from redis import Redis
import urllib, json
from ratelimit import limits, sleep_and_retry

import requests
import requests_cache

app = Flask(__name__)
app.secret_key = "dev"

app.config.from_object('config.BaseConfig')  # Set the configuration variables to the flask application
cache = Cache(app)  # Initialize Cache

backend = requests_cache.RedisCache(host='redis', port=6379)
requests_cache.install_cache('coin_gecko_cache', backend=backend, expire_after=180)

redis = Redis(host='redis', port=6379)

DATABASE = '/code/sqlite.db'

@app.before_request
def before_request():
    g.start_time = time.time()

@app.after_request
def after_request(response):
    print((f"Time used: {time.time() - g.start_time}"), flush=True)
    return response
    
def get_db():   
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        
    return db

def alter_db(query):
    con =  get_db()
    cur = con.execute(query)
    con.commit()
    cur.close()
    
def query_db(query, args=(), one=False):
    """
    Example Usage:
    user = query_db('select * from users where username = ?',
                [the_username], one=True)
    """
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv
        
@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@sleep_and_retry
@limits(calls=50, period=60)
@cache.cached(timeout=30, query_string=True)
def get_exchanges(id):
    """
    Call CoinGecko API endpoint and extract unique tickers[].market.identifier values
    """
    url = "https://api.coingecko.com/api/v3/coins/%s/tickers" % id
    data = requests.get(url).json()
    # If pulling from Redis cache, requests.exceptions aren't thrown
    # Manually check for errors
    if 'error' in data.keys():
        return None 
    return(data)

def validate_csv(data):
    return(True)

def validate_json(data):
    return(True)
      
@app.route('/coin_id_transform', methods=['POST'])
def coin_id_transform():
    
    task_run = redis.incr('hits') # Use redis to keep track of a global request/task count
    
    if (request.content_type.startswith('application/json')):
        data = request.json
        ids = data['coins']    
    elif (request.content_type.startswith('text/csv')):
        data = request.data
        ids = data.decode().split('\n')[1:] # Skip header
    else:
        return('Invalid Content-Type', 400)
    
    for id in ids:
        try:
            data = get_exchanges(id)
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
        except requests.exceptions.RequestException as e:
            print('id = ' + id + 'Exception = ' + str(e), flush=True)
            return('Unhandled exception', 500)
        
        # Check if entry exists
        row = query_db("select id, exchanges from coins where id=?", [id], one=True)
        #print(row, flush=True)
        str_exchanges = json.dumps(exchanges)
        exchanges.sort()
        #print(exchanges, flush=True)
        if not row:
            print("Inserting id = " + id, flush=True)
            alter_db("insert into coins (id, exchanges, task_run) values ('%s', '%s', %s)" % (id, str_exchanges, task_run))
        else:
            # If the exchanges in db doesn't match, update it
            if not row[1]==str_exchanges:
                print('Updating id = ' + id, flush=True)
                alter_db("update coins set exchanges='%s' where id = '%s'" % (str_exchanges, id))
                   
    return('', 200)

@app.route('/get_coins', methods=['GET'])
def get_coins():
    """
    Display contents of current coins table
    """
    data =  query_db("select * from coins")
    rowarray_list = []
    for row in data:
        d = dict(zip(row.keys(), row))   # a dict with column names as keys
        rowarray_list.append(d)
    return jsonify(rowarray_list)

if __name__ == "__main__":

    app.run(host="0.0.0.0", debug=True, threaded=True)