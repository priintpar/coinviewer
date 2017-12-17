#!c:/Python27/python.exe -u

"""
Name:       Coinviewer (BTC Version)
Author:     alex@life-sucks.info
Website:    https://life-sucks.info/818/coinviewer-v2-usdeurbtc-versions/
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

"""
#
# Libraries
#

import urllib, json, csv, sys
from tabulate import tabulate

#
# Functions
#

def getCryptoCoinPriceInEuro(cryptocoinurl):
    while True:
        try:
            response = urllib.urlopen(cryptocoinurl)
            data = json.loads(response.read())[0]
            break
        except:
            raw_input("Error while getting coin price!")
    return data['price_btc']

def getUrlFromCryptoCoinName(cryptocoinname):
    return "https://api.coinmarketcap.com/v1/ticker/" + cryptocoinname

def getCryptoCoinsFromCSVFile(csvfilename):
    with open(csvfilename, 'rb') as csvfile:
        coins = csv.reader(csvfile, delimiter=';', quotechar='"')
        coinlist = []
        for row in coins:
            coinlist.append(row)
    return coinlist

def calculateCurrentCryptoCoinTotalValue(cryptocoinname, cryptocoinamount):
    currentcryptocoinprice = getCryptoCoinPriceInEuro(getUrlFromCryptoCoinName(cryptocoinname))
    currentcryptocointotalvalue = float(currentcryptocoinprice) * float(cryptocoinamount)
    return currentcryptocointotalvalue

def calculateInvestmentDateCryptoCoinTotalValue(cryptocoininvestmentdateprice, cryptocoinamount):
    investmentdatecryptocoinvalue = float(cryptocoininvestmentdateprice) * float(cryptocoinamount)
    return investmentdatecryptocoinvalue

def calculateCryptoCoinPriceChangeSinceInvestment(currentcryptocointotalvalue, investmentdatecryptocointotalvalue):
    pricechange = ((float(currentcryptocointotalvalue) / float(investmentdatecryptocointotalvalue)) - 1) * 100
    return pricechange

def calculateCryptoCoinTotalValueSum(cryptocointotalvaluelist):
    cryptocointotalvaluesum = 0
    for element in cryptocointotalvaluelist:
        cryptocointotalvaluesum += float(element)
    return cryptocointotalvaluesum

def calculateCryptoCoinTotalPriceChangeSinceInvestment(currentcryptocointotalvaluesum, investmentdatecryptocointotalvaluesum):
    pricechangetotalsum = ((float(currentcryptocointotalvaluesum) / float(investmentdatecryptocointotalvaluesum)) - 1) * 100
    return pricechangetotalsum


def createTableRowList(cryptocoinname, cryptocoinamount, cryptocoininvestmentdateprice):
    currentcryptocointotalvalue = calculateCurrentCryptoCoinTotalValue(cryptocoinname, cryptocoinamount)
    investmentdatecryptocoinvalue = calculateInvestmentDateCryptoCoinTotalValue(cryptocoininvestmentdateprice, cryptocoinamount)
    pricechange = calculateCryptoCoinPriceChangeSinceInvestment(currentcryptocointotalvalue, investmentdatecryptocoinvalue)
    cryptocoinamount = float(cryptocoinamount)
    cryptocoinamount = float("{0:.2f}".format(cryptocoinamount))
    tablerowlist = [cryptocoinname, cryptocoinamount, currentcryptocointotalvalue, investmentdatecryptocoinvalue, pricechange]
    return tablerowlist

def createWholeTable(coinlist):
    table = []
    currentsumcounter = 0
    investmentsumcounter = 0
    for line in coinlist[1:]:
        tablerowlist = createTableRowList(line[0], line[1], line[2])
        table.append(tablerowlist)
        currentsumcounter += tablerowlist[2]
        investmentsumcounter += tablerowlist[3]
    pricechangesum = calculateCryptoCoinTotalPriceChangeSinceInvestment(currentsumcounter, investmentsumcounter)
    lastrow = ["Total Value ==>", "", currentsumcounter, investmentsumcounter, pricechangesum]
    table.append(lastrow)
    return table

def printTable(coinlist):
    header = ["Coinname", "Coin Amount", "Current Value", "Investment Value", "% Change"]
    print tabulate(coinlist, headers=header, showindex="always", tablefmt="rst", floatfmt=(".6f"))
    return 0

#
# Main
#

if __name__ == '__main__':
    coinlist = getCryptoCoinsFromCSVFile(sys.argv[1])
    table = createWholeTable(coinlist)
    printTable(table)
    raw_input("Press enter to exit ;)")
