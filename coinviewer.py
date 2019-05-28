"""
Name:       Coinviewer
Author:     alex@life-sucks.info
Date:       05/2019
Version:    4 (190528)

This little tool gives you an overview over
all of your and your families or clients
cryptocoins. You can add unlimited coinholders
and unlimited coins, as long as they are listed
at coinmarketcap.com

Sources used are:
# https://pypi.python.org/pypi/tabulate

Configuration:
Create a csv file named coins.csv
with the following content format:
"Coin Name";"Coin Amount";"Total Investment Price in €"
digibyte;5922.7;0.05
bitcoin;47.34;2661.86

How to run:
python coinviewer.py coins.csv

3rd-party libraries needed to run:
# sudo pip install tabulate

"""
#
# Libraries
#

import requests, json, csv, sys
from tabulate import tabulate

#
# Global Variables
#

#
# Functions
#

# API connectors

def get_crypto_coin_price(crypto_coin_url, currency):
    while True:
        try:
            r = requests.get(crypto_coin_url)
            for data in r.json():
                return data['price_' + currency]
            break
        except:
            input("Error while getting coin price!")
    return 1

def get_url_from_coin(coin_name):
    return "https://api.coinmarketcap.com/v1/ticker/" + coin_name + "/?convert=eur"

# File in- and output

def get_coins_from_csv(csv_file_name):
    with open(csv_file_name, 'r') as csvfile:
        coins = csv.reader(csvfile, delimiter=';', quotechar='"')
        coin_list = []
        for row in coins:
            coin_list.append(row)
    return coin_list

# Prices and and value calculation

def calculate_coin_value(coin_name, coin_amount, currency):
    coin_price = get_crypto_coin_price(get_url_from_coin(coin_name), currency)
    coin_value = float(coin_price) * float(coin_amount)
    return coin_value

def calculate_price_change(coin_value, investment_value):
    if float(investment_value) == 0:
        return 0
    price_change = ((float(coin_value) / float(investment_value)) - 1) * 100
    return price_change

def calculate_total_price_change(coin_value_sum, investment_value_sum):
    if float(investment_value_sum) == 0:
        return 0
    price_change_total_sum = ((float(coin_value_sum) / float(investment_value_sum)) - 1) * 100
    return price_change_total_sum

# Table creation

def create_blank_row():
    return [" ", " ", " ", " ", " ", " "]

def create_table_row(coin_name, coin_amount, coin_investment_value):
    coin_amount = float(coin_amount)
    coin_investment_value = float(coin_investment_value)
    coin_value_eur = float(calculate_coin_value(coin_name, coin_amount, "eur"))
    coin_value_usd = float(calculate_coin_value(coin_name, coin_amount, "usd"))
    price_change = float(calculate_price_change(coin_value_eur, coin_investment_value))
    table_row = [coin_name, coin_amount, int(coin_investment_value), int(coin_value_eur), int(coin_value_usd), int(price_change)]
    return table_row

def create_table(coin_list):
    table = []
    eur_sum_counter, usd_sum_counter, investment_sum_counter = 0, 0, 0
    for line in coin_list[1:]:
        table_row = create_table_row(line[0], line[1], line[2])
        table.append(table_row)
        investment_sum_counter += float(table_row[2])
        eur_sum_counter += float(table_row[3])
        usd_sum_counter += float(table_row[4])
    price_change_sum = calculate_total_price_change(eur_sum_counter, investment_sum_counter)
    table = sorted(table, key=lambda k: k[5], reverse=True)
    table.append(create_blank_row())
    table.append(["Total", "", int(investment_sum_counter), int(eur_sum_counter), int(usd_sum_counter), int(price_change_sum)])
    return table

def print_table(table):
    header = ["#", "Coin", "Amount", "Inv€st", "€", "$", "%"]
    print(tabulate(table, headers=header, showindex="always", tablefmt="rst", floatfmt=(".0f")))
    return 0

#
# Main
#

if __name__ == '__main__':
    try:
        csv_file_name = sys.argv[1]
        coin_list = get_coins_from_csv(csv_file_name)
        print_table(create_table(coin_list))
    except IndexError:
        print("Please provide the filename of the csv file containing the coins as an argument!")