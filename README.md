Name:       Coinviewer (Euro Version)<br />
Author:     alex@life-sucks.info<br />
Date:       11/2017<br />
Version:    2.0<br />
<br />
This little tool gives you an overview over<br />
all of your and your families or clients<br />
cryptocoins. You can add unlimited coinholders<br />
and unlimited coins, as long as they are listed<br />
at coinmarketcap.com<br />
<br />
Sources used are:<br />
https://pypi.python.org/pypi/tabulate<br />
<br />
Configuration:<br />
Create a csv file with the following format:<br />
```
"Coin Name";"Coin Amount";"Investment Coin Price"
digibyte;5922.7;0.0005506
bitcoin;47.34;2661.862
posw-coin;72637;0.075843
waves;30.219;0.2286993449
xtrabytes;1961.96;0.0000834987
```
<br />
How to run:<br />
python coinviewer-v2.py "yourcsvfile.csv"<br />
<br />
3rd-party libraries needed to run:<br />
sudo pip install tabulate
