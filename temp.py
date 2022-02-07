# -*- coding: utf-8 -*-
"""
Created on Sun Feb  6 15:26:15 2022

@author: Walling
"""

import json
 
# Opening JSON file
# with open('coin_gecko_example.json') as json_file:
#     data = json.load(json_file)
#     print(data)
    
    
a = {'binance', 'huobi', 'gdax', 'hotbit', 'bybit_spot', 'bitget', 'ftx_us', 'bitstamp', 'b2bx', 'delta_spot', 
     'gmo_japan', 'btse', 'bitso', 'currency', 'phemex', 'bkex', 'crypto_com', 'ftx_spot', 'binance_us', 'whitebit', 
     'kraken', 'kucoin', 'zb', 'bigone', 'digifinex', 'waves', 'okcoin', 'coincheck', 'huobi_japan', 'alterdice', 
     'bitfinex', 'cryptology', 'okex', 'aax', 'bitflyer', 'hitbtc', 'finexbox', 'coinsbit', 'gate', 'bitvavo', 
     'exrates', 'xt'}
b = {'coincheck', 'gate', 'gmo_japan', 'waves', 'hitbtc', 'kraken', 'aax', 'bitflyer', 'huobi', 'ftx_spot', 'xt', 
     'bigone', 'currency', 'bitget', 'hotbit', 'coinsbit', 'gdax', 'exrates', 'finexbox', 'alterdice', 'huobi_japan', 
     'bitso', 'kucoin', 'bitstamp', 'digifinex', 'binance', 'bybit_spot', 'bitfinex', 'whitebit', 'crypto_com', 
     'ftx_us', 'delta_spot', 'okcoin', 'phemex', 'zb', 'b2bx', 'okex', 'binance_us', 'btse', 'bitvavo', 'bkex', 'cryptology'}

if a==b:
    print("Match")