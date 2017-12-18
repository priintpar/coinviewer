# README
### Info
Name:       Coinviewer<br />
Author:     alex@life-sucks.info<br />
Website:    https://life-sucks.info/818/coinviewer-v2-usdeurbtc-versions/<br />
Date:       12/2017<br />
Version:    2.2<br />
<br />
### Description
This little tool gives you an overview over<br />
all of your and your families or clients<br />
cryptocoins. You can add unlimited coinholders<br />
and unlimited coins, as long as they are listed<br />
at coinmarketcap.com You can also save the values<br />
of your coins for every data retrieval.<br />
<br />
### Sources used are
https://pypi.python.org/pypi/tabulate<br />
<br />
### How to run
python coinviewer-v2.py coins-yourname.csv currency savehistory<br />
currency is the symbol of the currency you want to calculate in<br />
(choose usd, eur or btc, otherwise eur is used)<br />
savehistory lets you save the current calculations in a csv<br />
(savehistory is optional)<br />
<br />
### 3rd-party libraries needed to run
sudo pip install tabulate<br />
### Configuration
Create a csv file with the following format:<br />
```
"Coin Name";"Coin Amount";"Investment Coin Price"
digibyte;5922.7;0.0005506
bitcoin;47.34;2661.862
posw-coin;72637;0.075843
waves;30.219;0.2286993449
xtrabytes;1961.96;0.0000834987
```
