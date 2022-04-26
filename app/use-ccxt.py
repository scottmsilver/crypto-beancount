# -*- coding: utf-8 -*-
import sys
import ccxt  # noqa: E402
from dotenv import dotenv_values

config = dotenv_values(".env")

exchange = ccxt.ftxus({
    'apiKey': config['API_KEY'],
    'secret': config['API_SECRET'],
})

# go back and DO NOT USE the info field
# exchange.verbose = True  # uncomment for debugging

def fetchTrades(exchange):
    all_trades = {}
    symbol = None
    since = None
    limit = 200
    end_time = exchange.milliseconds()

    while True:
      params = {'end_time': int(end_time / 1000),}
      trades = exchange.fetch_my_trades(symbol, since, limit, params)
      if len(trades):
          first_trade = trades[0]
          last_trade = trades[len(trades) - 1]
          end_time = first_trade['timestamp'] + 1000
          #print('Fetched', len(trades), 'trades from', first_trade['datetime'], 'till', last_trade['datetime'])
          fetched_new_trades = False
          for trade in trades:
              trade_id = trade['id']
              if trade_id not in all_trades:
                  fetched_new_trades = True
                  all_trades[trade_id] = trade
          if not fetched_new_trades:
              break
      else:
          break
        
    all_trades = list(all_trades.values())
    return all_trades

all_trades = fetchTrades(exchange)


# Make all FIAT currency look alike register as one as they are treated all the same, unfortunately, by FTX
def normalizeCurrency(currency):
  STABLE_USD_COINS = {'USD', 'USDC', 'TUSD', 'USDP', 'BUSD', 'HUSD'}
  if currency in STABLE_USD_COINS:
    return 'USD'
  else:
    return currency

class Ledger:
  def __init__(self):
    self.entries = []

  def addEntry(self, date, description):
    entry = LedgerEntry(date, description)
    self.entries.append(entry)
    return entry

  def getAccountsAndCurrencies(self):
    # horribly inefficient
    accounts = set()
    currencies = set()
    for entry in self.entries:
      for item in entry.items:
        currencies.add(item.currency)
        accounts.add(item.account)
    return (accounts, currencies)

  def getEntries(self):
   return sorted(self.entries, key=lambda entry: entry.date, reverse=False)


class LedgerEntry:
  class Item:
    def __init__(self, account, currency, quantity, inputCommodity, inputQuantity, description):
      self.currency = normalizeCurrency(currency)
      self.account = account #"{account}:{currency}".format(account = account, currency = self.currency)
      self.quantity = quantity
      self.description = description
      self.inputCommodity = inputCommodity
      self.inputQuantity = inputQuantity

    def generateCostBasisText(self):
      return "" if (self.inputCommodity == None or self.inputQuantity == None) else '{{{quantity:.13f} {commodity}}}'.format(quantity = self.inputQuantity, commodity = normalizeCurrency(self.inputCommodity))

    def generateDescriptionComment(self):
      return ';; {0}'.format(self.description) if self.description else ''


    # NB: The precision here is hack; it should really be based on the known precision; i had to force it here to get rid of scientific notation because beancounter doesn't understand it.
    def __repr__(self):
      print("qq--", self.quantity)
      if (self.currency == None or self.quantity == None):
        return "{account}\t{comment}".format(account=self.account, comment = self.generateDescriptionComment())
      else:
        return "{account}\t{quantity} {currency} {costBasis} {comment}".format(account = self.account, quantity = self.quantity, currency = self.currency, costBasis = self.generateCostBasisText(), comment = self.generateDescriptionComment())


  def __init__(self, date, description):
    self.date = date
    self.description = description
    self.items = []

  def addItem(self, account, currency = None, quantity = None, inputCommodity = None, inputQuantity = None, description = ''):
    print(quantity, description)
    self.items.append(self.Item(account=account, currency=currency, quantity=quantity,
                      inputCommodity=inputCommodity, inputQuantity=inputQuantity, description=description))

  def print(self):
    print('{0} * "{1}"'.format(self.date.strftime("%Y/%m/%d"), self.description))
    for item in self.items:
      print("  {}".format(item))
    print()


import sys

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

ledger = Ledger()

from decimal import *
import dateutil.parser


class Symbol:
  def __init__(self, symbol):
    self.symbol = symbol
    (self.baseCurrency, self.quoteCurrency) = symbol.split('/')
  
  def __repr__(self):
    return self.symbol

# The way that FTX does charges is as follows
# Say you by 1 BTC for 1000 USD and your Maker fee is 1%
# You will be 0.01 BTC (BTC because is Maker fee).
# So you will debit 1000 USD to bay for 1 BTC
# Then you will debit 0.1 BTC for yoru feel
# You will then have 0.99 BTC @ 1000 USD and -1000 USD in your accounts


#def amount_to_precision (symbol, amount):
#def price_to_precision (symbol, price):
#def cost_to_precision (symbol, cost):
#def currency_to_precision (code, amount):

exchange.loadMarkets()



# {'info':, 
# 'timestamp': 1647280938436, 'datetime': '2022-03-14T18:02:18.436Z', 
# 'symbol': 'BTC/USD', 'id': '62902857', 'order': '4120253149', '
# type': None, 'takerOrMaker': 'maker', 'side': 'buy', 'price': 38721.0, 
# 'amount': 0.1, 'cost': 3872.1, 'fee': {'cost': 0.0001, 
# 'currency': 'BTC', 'rate': 0.001}, 'fees': [{'currency': 'BTC', 'cost': 0.0001, 'rate': 0.001}]}
for trade in all_trades:
  fill = trade['info']
  # this type is wrongl;
  feeCurrency = trade['fee']['currency']
  symbol = Symbol(trade['symbol'])
  size = Decimal(exchange.amount_to_precision(trade['symbol'], trade['amount']))
  price = Decimal(exchange.price_to_precision(trade['symbol'], trade['price']))
  fee = Decimal(trade['fee']['cost'])
  baseCurrency = symbol.baseCurrency
  quoteCurrency = symbol.quoteCurrency
  dateTime = dateutil.parser.parse(trade['datetime']);

  entry = ledger.addEntry(dateTime, "fillid-{0}: {1} {2} {3} @ {4} {5} ea. {6}".format(
      fill['id'], fill['side'], size, baseCurrency, price, quoteCurrency, fill))
  entry.addItem(account="Assets:Wallet",
                currency=baseCurrency, quantity=size, inputCommodity=quoteCurrency, inputQuantity=price, description="Purchase")
   
  #  {'id': 63820377, 'market': 'SOL/USD', 'future': None, 'baseCurrency': 'SOL', 'quoteCurrency': 'USD', 
  # 'type': 'order', 'side': 'buy', 'price': 89.7775, 'size': 15.0, 'orderId': 4216671021, 
  # 'time': '2022-03-21T13:54:26.393415+00:00', 'tradeId': 27130489, 'feeRate': 0.0008, 'fee': 0.012, 
  # 'feeCurrency': 'SOL', 'liquidity': 'maker'}
  doItRight = False
  if not doItRight and quoteCurrency != feeCurrency:
    print("rr--", fee)
    entry.addItem(account="Expenses:Fees", currency=feeCurrency, quantity=fee, inputCommodity=quoteCurrency, inputQuantity=price, description='Fee rate of {feeRate} of {fee} as {makerOrTaker}'.format(feeRate = fill['feeRate'], fee = fee, makerOrTaker=fill['liquidity']))
  else:
    entry.addItem(account="Expenses:Fees", currency=feeCurrency, quantity=fee, description='Fee rate of {feeRate} of {fee} as {makerOrTaker}'.format(feeRate= fill['feeRate'], fee = fee, makerOrTaker = fill['liquidity']))
  entry.addItem(account="Assets:Wallet", currency=feeCurrency)

exit(0)
# {'info': {'id': '38252', 'coin': 'USD', 'size': None, 'status': 'cancelled', 'time': '2022-03-12T15:59:30.922452+00:00', 
# 'confirmedTime': None, 'uploadedFile': None, 'uploadedFileName': None, 'cancelReason': None, 'fiat': True, 'ach': False, 
# 'type': 'bank', 'supportTicketId': None}, 'id': '38252', 'txid': None, 'timestamp': 1647100770922, 
# 'datetime': '2022-03-12T15:59:30.922Z', 'network': None, 'addressFrom': None, 'address': None, 'addressTo': None, 'tagFrom': None, 'tag': None, 'tagTo': None, 'type': 'deposit', 'amount': None, 'currency': 'USD', 'status': 'canceled', 'updated': None, 'fee': {'currency': 'USD', 'cost': None, 'rate': None}}
for depositEntry in exchange.fetchDeposits():
  deposit = depositEntry['info']
  if deposit['size'] != None:
    currency = deposit['coin']
    quantity = Decimal(deposit['size'])
    entry = ledger.addEntry(
      date = dateutil.parser.parse(depositEntry['datetime']),
      description = 'Deposit {0} {1}'.format(quantity, currency))
    entry.addItem(
      account = 'Assets:Wallet',
      currency = currency,
      quantity = quantity,
      description = '')
    entry.addItem(
      account = 'Income:Investments',
      currency=currency,
      quantity = -quantity,
      description='')

if False:
  #{'coin': 'SOL', 'time': '2022-03-31T05:00:00+00:00', 'size': 1100.306557, 'rate': 1.142e-05, 'proceeds': 0.01256550088094, 'feeUsd': 1.5198590173526874}
  for loan in ftxClient.get_lending_history():
    quantity = loan['proceeds']
    currency = loan['coin']

    entry = ledger.addEntry(
        date=datetime.fromisoformat(loan['time']),
        description='Lending Interest {0} {1} ; {2}'.format(quantity, currency, loan))
    entry.addItem(account='Assets:Wallet:Interest', currency=currency,
                  quantity=quantity, description='')
    entry.addItem(account='Income:Interest', currency=currency,
                  quantity=-quantity, description='')

  # add borrows
  # {'coin': 'USD', 'time': '2022-03-31T15:00:00+00:00', 'size': 575.8747286, 'rate': 2e-06, 'cost': 0.0011517494572, 'feeUsd': 0.0011517494572}
  for loan in ftxClient.get_borrow_history():
    quantity = loan['cost']
    currency = loan['coin']

    entry = ledger.addEntry(
        date=datetime.fromisoformat(loan['time']),
        description='Borrowing Interest {0} {1}'.format(quantity, currency))
    entry.addItem(account = 'Assets:Wallet:Interest', currency = currency, quantity = -quantity, description='')
    entry.addItem(account='Income:Interest', currency = currency,
                  quantity = quantity, description='')

print('option "operating_currency" "USD"')

(accounts, currencies) = ledger.getAccountsAndCurrencies()
for account in accounts:
  print("2003-01-05 open {0}".format(account))

for currency in currencies:
  print(
  """
2000-01-01 commodity {currency}
  price: "USD:coinbase/{currency}-USD"
  """.format(currency = currency))

for entry in ledger.getEntries():
  entry.print()

print('plugin "beancount.plugins.unrealized" "Unrealized"')
# Next step get the costs in this


