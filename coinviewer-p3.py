"""
Name:       Coinviewer
Author:     alex@life-sucks.info
Date:       01/2019
Version:    2.3

This little tool gives you an overview over
all of your and your families or clients
cryptocoins. You can add unlimited coinholders
and unlimited coins, as long as they are listed
at coinmarketcap.com You can also save the values
of your coins for every data retrieval.

Sources used are:
# https://pypi.python.org/pypi/tabulate

Configuration:
Create a csv file named coins-yourname.csv
with the following content format:
"Coin Name";"Coin Amount";"Investment Coin Price"
digibyte;5922.7;0.0005506
bitcoin;47.34;2661.862
posw-coin;72637;0.075843
waves;30.219;0.2286993449
xtrabytes;1961.96;0.0000834987

How to run:
python coinviewer-v2.py coins-yourname.csv currency savehistory
currency is the symbol of the currency you want to calculate in
(choose usd, eur or btc, otherwise eur is used)
savehistory lets you save the current calculations in a csv
(savehistory is optional)

3rd-party libraries needed to run:
# sudo pip install tabulate

"""
#
# Libraries
#

import urllib.request, urllib.parse, urllib.error, json, csv, sys, time
from tabulate import tabulate

#
# Global Variables
#

currency = "eur"

#
# Functions
#

# API connectors

def getCryptoCoinPriceInEuro(cryptocoinurl):
    while True:
        try:
            response = urllib.request.urlopen(cryptocoinurl)
            data = json.loads(response.read())[0]
            break
        except:
            input("Error while getting coin price!")
    return data['price_' + currency]

def getUrlFromCryptoCoinName(cryptocoinname):
    return "https://api.coinmarketcap.com/v1/ticker/" + cryptocoinname + "/?convert=" + currency

# File in- and output

def getCryptoCoinsFromCSVFile(csvfilename):
    with open(csvfilename, 'r') as csvfile:
        coins = csv.reader(csvfile, delimiter=';', quotechar='"')
        coinlist = []
        for row in coins:
            coinlist.append(row)
    return coinlist

def createValueHistoryCSVLine(coinlist):
    now = time.strftime("%d.%m.%Y %H:%M:%S")
    csvline = [now]
    currentsumcounter = 0
    for line in coinlist[1:]:
        currentvalue = calculateCurrentCryptoCoinTotalValue(line[0], line[1])
        csvline.append(currentvalue)
        currentsumcounter += currentvalue
    csvline.append(currentsumcounter)
    return csvline

def saveValueHistoryCSV(csvline, csvhistoryfilename):
    with open(csvhistoryfilename, 'a') as csvfile:
        wr = csv.writer(csvfile, lineterminator='\n', quoting=csv.QUOTE_ALL)
        wr.writerow(csvline)

def getUsernameFromCSVFilename(csvfilename):
    tmplist = csvfilename.split("-")
    tmplist2 = tmplist[1].split(".")
    return tmplist2[0]

def createCurrentCSVHistoryName(username):
    return "history-" + username + ".csv"

# Prices and and value calculation

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

# Table creation

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
    print(tabulate(coinlist, headers=header, showindex="always", tablefmt="rst", floatfmt=(".0f")))
    return 0

#
# Main
#

if __name__ == '__main__':
    try:
        inp2 = sys.argv[2]
        if inp2 == "eur" or inp2 == "usd" or inp2 == "btc":
            currency = sys.argv[2]
        else:
            print("You can only choose usd, eur or btc as currency")
            print("Otherwise " + currency + " is used as standard currency.")
    except IndexError:
        print("Please provide the currency you want to calculate in as the second argument!")
        print("Otherwise " + currency + " is used as standard currency.")
    try:
        currentcsvfilename = sys.argv[1]
        coinlist = getCryptoCoinsFromCSVFile(currentcsvfilename)
        printTable(createWholeTable(coinlist))
        time.sleep(10)
    except IndexError:
        print("Please provide the filename of the csv file containing the coins as the first argument!")
    try:
        if sys.argv[3] == "savehistory":
            saveValueHistoryCSV(createValueHistoryCSVLine(coinlist), createCurrentCSVHistoryName(getUsernameFromCSVFilename(currentcsvfilename)))
    except IndexError:
        pass