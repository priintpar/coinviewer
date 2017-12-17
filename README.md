Name:       Coinviewer (Euro Version)
Author:     alex@life-sucks.info
Date:       11/2017
Version:    2.0

This little tool gives you an overview over
all of your and your families or clients
cryptocoins. You can add unlimited coinholders
and unlimited coins, as long as they are listed
at coinmarketcap.com

Sources used are:
# https://pypi.python.org/pypi/tabulate

Configuration:
Create a csv file with the following format:
"Coin Name";"Coin Amount";"Investment Coin Price"
digibyte;5922.7;0.0005506
bitcoin;47.34;2661.862
posw-coin;72637;0.075843
waves;30.219;0.2286993449
xtrabytes;1961.96;0.0000834987

How to run:
python coinviewer-v2.py "yourcsvfile.csv"

3rd-party libraries needed to run:
# sudo pip install tabulate
