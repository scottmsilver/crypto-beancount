from locale import currency
from posixpath import curdir
import time
import urllib.parse
from typing import Optional, Dict, Any, List

from requests import Request, Session, Response
import hmac
from datetime import datetime
from decimal import *
import simplejson

class FtxClient:
    _ENDPOINT = 'https://ftx.us/api/'

    def __init__(self, api_key=None, api_secret=None, subaccount_name=None) -> None:
        self._session = Session()
        self._api_key = api_key
        self._api_secret = api_secret
        self._subaccount_name = subaccount_name

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        return self._request('GET', path, params=params)

    def _post(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        return self._request('POST', path, json=params)

    def _delete(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        return self._request('DELETE', path, json=params)

    def _request(self, method: str, path: str, **kwargs) -> Any:
        request = Request(method, self._ENDPOINT + path, **kwargs)
        self._sign_request(request)
        response = self._session.send(request.prepare())
        return self._process_response(response)

    def _sign_request(self, request: Request) -> None:
        ts = int(time.time() * 1000)
        prepared = request.prepare()
        signature_payload = f'{ts}{prepared.method}{prepared.path_url}'.encode(
        )
        if prepared.body:
            signature_payload += prepared.body
        signature = hmac.new(self._api_secret.encode(),
                             signature_payload, 'sha256').hexdigest()
        request.headers['FTXUS-KEY'] = self._api_key
        request.headers['FTXUS-SIGN'] = signature
        request.headers['FTXUS-TS'] = str(ts)
        if self._subaccount_name:
            request.headers['FTXUS-SUBACCOUNT'] = urllib.parse.quote(
                self._subaccount_name)

    def _process_response(self, response: Response) -> Any:
        try:
            data = simplejson.loads(response.text, use_decimal=True)
        except ValueError:
            response.raise_for_status()
            raise
        else:
            if not data['success']:
                raise Exception(data['error'])
            return data['result']

    def get_all_futures(self) -> List[dict]:
        return self._get('futures')

    def get_future(self, future_name: str = None) -> dict:
        return self._get(f'futures/{future_name}')

    def get_markets(self) -> List[dict]:
        return self._get('markets')

    def get_orderbook(self, market: str, depth: int = None) -> dict:
        return self._get(f'markets/{market}/orderbook', {'depth': depth})

    def get_trades(self, market: str, start_time: float = None, end_time: float = None) -> dict:
        return self._get(f'markets/{market}/trades', {'start_time': start_time, 'end_time': end_time})

    def get_account_info(self) -> dict:
        return self._get(f'account')

    def get_open_orders(self, market: str = None) -> List[dict]:
        return self._get(f'orders', {'market': market})

    def get_order_history(
        self, market: str = None, side: str = None, order_type: str = None,
        start_time: float = None, end_time: float = None
    ) -> List[dict]:
        return self._get(f'orders/history', {
            'market': market,
            'side': side,
            'orderType': order_type,
            'start_time': start_time,
            'end_time': end_time
        })

    def get_conditional_order_history(
        self, market: str = None, side: str = None, type: str = None,
        order_type: str = None, start_time: float = None, end_time: float = None
    ) -> List[dict]:
        return self._get(f'conditional_orders/history', {
            'market': market,
            'side': side,
            'type': type,
            'orderType': order_type,
            'start_time': start_time,
            'end_time': end_time
        })

    def modify_order(
        self, existing_order_id: Optional[str] = None,
        existing_client_order_id: Optional[str] = None, price: Optional[float] = None,
        size: Optional[float] = None, client_order_id: Optional[str] = None,
    ) -> dict:
        assert (existing_order_id is None) ^ (existing_client_order_id is None), \
            'Must supply exactly one ID for the order to modify'
        assert (price is None) or (
            size is None), 'Must modify price or size of order'
        path = f'orders/{existing_order_id}/modify' if existing_order_id is not None else \
            f'orders/by_client_id/{existing_client_order_id}/modify'
        return self._post(path, {
            **({'size': size} if size is not None else {}),
            **({'price': price} if price is not None else {}),
            ** ({'clientId': client_order_id} if client_order_id is not None else {}),
        })

    def get_conditional_orders(self, market: str = None) -> List[dict]:
        return self._get(f'conditional_orders', {'market': market})

    def place_order(self, market: str, side: str, price: float, size: float, type: str = 'limit',
                    reduce_only: bool = False, ioc: bool = False, post_only: bool = False,
                    client_id: str = None, reject_after_ts: float = None) -> dict:
        return self._post('orders', {
            'market': market,
            'side': side,
            'price': price,
            'size': size,
            'type': type,
            'reduceOnly': reduce_only,
            'ioc': ioc,
            'postOnly': post_only,
            'clientId': client_id,
            'rejectAfterTs': reject_after_ts
        })

    def place_conditional_order(
        self, market: str, side: str, size: float, type: str = 'stop',
        limit_price: float = None, reduce_only: bool = False, cancel: bool = True,
        trigger_price: float = None, trail_value: float = None
    ) -> dict:
        """
        To send a Stop Market order, set type='stop' and supply a trigger_price
        To send a Stop Limit order, also supply a limit_price
        To send a Take Profit Market order, set type='trailing_stop' and supply a trigger_price
        To send a Trailing Stop order, set type='trailing_stop' and supply a trail_value
        """
        assert type in ('stop', 'take_profit', 'trailing_stop')
        assert type not in ('stop', 'take_profit') or trigger_price is not None, \
            'Need trigger prices for stop losses and take profits'
        assert type not in ('trailing_stop',) or (trigger_price is None and trail_value is not None), \
            'Trailing stops need a trail value and cannot take a trigger price'

        return self._post('conditional_orders', {
            'market': market,
            'side': side,
            'triggerPrice': trigger_price,
            'size': size,
            'reduceOnly': reduce_only,
            'type': 'stop',
            'cancelLimitOnTrigger': cancel,
            'orderPrice': limit_price
        })

    def cancel_order(self, order_id: str) -> dict:
        return self._delete(f'orders/{order_id}')

    def cancel_orders(
        self, market_name: str = None,
        conditional_orders: bool = False, limit_orders: bool = False
    ) -> dict:
        return self._delete(f'orders', {
            'market': market_name,
            'conditionalOrdersOnly': conditional_orders,
            'limitOrdersOnly': limit_orders
        })

    def get_fills(self, market: str = None, start_time: float = None,
                  end_time: float = None, min_id: int = None, order_id: int = None
                  ) -> List[dict]:
        return self._get('fills', {
            'market': market,
            'start_time': start_time,
            'end_time': end_time,
            'minId': min_id,
            'orderId': order_id
        })

    def get_balances(self) -> List[dict]:
        return self._get('wallet/balances')

    def get_total_usd_balance(self) -> int:
        total_usd = 0
        balances = self._get('wallet/balances')
        for balance in balances:
            total_usd += balance['usdValue']
        return total_usd

    def get_all_balances(self) -> List[dict]:
        return self._get('wallet/all_balances')

    def get_total_account_usd_balance(self) -> int:
        total_usd = 0
        all_balances = self._get('wallet/all_balances')
        for wallet in all_balances:
            for balance in all_balances[wallet]:
                total_usd += balance['usdValue']
        return total_usd

    def get_positions(self, show_avg_price: bool = False) -> List[dict]:
        return self._get('positions', {'showAvgPrice': show_avg_price})

    def get_position(self, name: str, show_avg_price: bool = False) -> dict:
        return next(filter(lambda x: x['future'] == name, self.get_positions(show_avg_price)), None)

    def get_all_trades(self, market: str, start_time: float = None, end_time: float = None) -> List:
        ids = set()
        limit = 100
        results = []
        while True:
            response = self._get(f'markets/{market}/trades', {
                'end_time': end_time,
                'start_time': start_time,
            })
            deduped_trades = [r for r in response if r['id'] not in ids]
            results.extend(deduped_trades)
            ids |= {r['id'] for r in deduped_trades}
            print(f'Adding {len(response)} trades with end time {end_time}')
            if len(response) == 0:
                break

            end_time = min(datetime.fromisoformat(t['time'])
                           for t in response).timestamp()
            if len(response) < limit:
                break
        return results

    def get_historical_prices(
        self, market: str, resolution: int = 300, start_time: float = None,
        end_time: float = None
    ) -> List[dict]:
        return self._get(f'markets/{market}/candles', {
            'resolution': resolution,
            'start_time': start_time,
            'end_time': end_time
        })

    def get_last_historical_prices(self, market: str, resolution: int = 300) -> List[dict]:
        return self._get(f'markets/{market}/candles/last', {'resolution': resolution})

    def get_borrow_rates(self) -> List[dict]:
        return self._get('spot_margin/borrow_rates')

    def get_borrow_history(self, start_time: float = None, end_time: float = None) -> List[dict]:
        return self._get('spot_margin/borrow_history', {'start_time': start_time, 'end_time': end_time})

    def get_lending_history(self, start_time: float = None, end_time: float = None) -> List[dict]:
        return self._get('spot_margin/lending_history', {
            'start_time': start_time,
            'end_time': end_time
        })

    def get_expired_futures(self) -> List[dict]:
        return self._get('expired_futures')

    def get_coins(self) -> List[dict]:
        return self._get('wallet/coins')

    def get_future_stats(self, future_name: str) -> dict:
        return self._get(f'futures/{future_name}/stats')

    def get_single_market(self, market: str = None) -> Dict:
        return self._get(f'markets/{market}')

    def get_market_info(self, market: str = None) -> dict:
        return self._get('spot_margin/market_info', {'market': market})

    def get_trigger_order_triggers(self, conditional_order_id: str = None) -> List[dict]:
        return self._get(f'conditional_orders/{conditional_order_id}/triggers')

    def get_trigger_order_history(self, market: str = None) -> List[dict]:
        return self._get('conditional_orders/history', {'market': market})

    def get_staking_balances(self) -> List[dict]:
        return self._get('staking/balances')

    def get_stakes(self) -> List[dict]:
        return self._get('staking/stakes')

    def get_staking_rewards(self, start_time: float = None, end_time: float = None) -> List[dict]:
        return self._get('staking/staking_rewards', {
            'start_time': start_time,
            'end_time': end_time
        })

    def place_staking_request(self, coin: str = 'SRM', size: float = None) -> dict:
        return self._post('srm_stakes/stakes',)

    def get_funding_rates(self, future: str = None, start_time: float = None, end_time: float = None) -> List[dict]:
        return self._get('funding_rates', {
            'future': future,
            'start_time': start_time,
            'end_time': end_time
        })

    def get_all_funding_rates(self) -> List[dict]:
        return self._get('funding_rates')

    def get_funding_payments(self, start_time: float = None, end_time: float = None) -> List[dict]:
        return self._get('funding_payments', {
            'start_time': start_time,
            'end_time': end_time
        })

    def create_subaccount(self, nickname: str) -> dict:
        return self._post('subaccounts', {'nickname': nickname})

    def get_subaccount_balances(self, nickname: str) -> List[dict]:
        return self._get(f'subaccounts/{nickname}/balances')

    def get_deposit_address(self, ticker: str) -> dict:
        return self._get(f'wallet/deposit_address/{ticker}')

    def get_deposit_history(self) -> List[dict]:
        return self._get('wallet/deposits')

    def get_withdrawal_fee(self, coin: str, size: int, address: str, method: str = None, tag: str = None) -> Dict:
        return self._get('wallet/withdrawal_fee', {
            'coin': coin,
            'size': size,
            'address': address,
            'method': method,
            'tag': tag
        })

    def get_withdrawals(self, start_time: float = None, end_time: float = None) -> List[dict]:
        return self._get('wallet/withdrawals', {'start_time': start_time, 'end_time': end_time})

    def get_saved_addresses(self, coin: str = None) -> dict:
        return self._get('wallet/saved_addresses', {'coin': coin})

    def submit_fiat_withdrawal(self, coin: str, size: int, saved_address_id: int, code: int = None) -> Dict:
        return self._post('wallet/fiat_withdrawals', {
            'coin': coin,
            'size': size,
            'savedAddressId': saved_address_id,
            'code': code
        })

    def get_latency_stats(self, days: int = 1, subaccount_nickname: str = None) -> Dict:
        return self._get('stats/latency_stats', {'days': days, 'subaccount_nickname': subaccount_nickname})


from dotenv import dotenv_values

config = dotenv_values(".env")

ftxClient  = FtxClient(api_key = config['API_KEY'], 
          api_secret = config['API_SECRET'])

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
      if (self.currency == None or self.quantity == None):
        return "{account}\t{comment}".format(account=self.account, comment = self.generateDescriptionComment())
      else:
        return "{account}\t{quantity:.13f} {currency} {costBasis} {comment}".format(account = self.account, quantity = self.quantity, currency = self.currency, costBasis = self.generateCostBasisText(), comment = self.generateDescriptionComment())


  def __init__(self, date, description):
    self.date = date
    self.description = description
    self.items = []

  def addItem(self, account, currency = None, quantity = None, inputCommodity = None, inputQuantity = None, description = ''):
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

# The way that FTX does charges is as follows
# Say you by 1 BTC for 1000 USD and your Maker fee is 1%
# You will be 0.01 BTC (BTC because is Maker fee).
# So you will debit 1000 USD to bay for 1 BTC
# Then you will debit 0.1 BTC for yoru feel
# You will then have 0.99 BTC @ 1000 USD and -1000 USD in your accounts
for fill in ftxClient.get_fills(start_time=0, end_time=2147483647):
  entry = ledger.addEntry(datetime.fromisoformat(fill['time']), "fillid-{0}: {1} {2} {3} @ {4} {5} ea. {6}".format(
      fill['id'], fill['side'], fill['size'], fill['baseCurrency'], fill['price'], fill['quoteCurrency'], fill))
  size = Decimal(str(fill['size']))
  price = Decimal(str(fill['price']))
  fee = Decimal(str(fill['fee']))
  eprint("fill({id}), {date}".format(date = fill['time'], id = fill['id']))
  entry.addItem(account="Assets:Wallet",
                currency=fill['baseCurrency'], quantity=size, inputCommodity=fill['quoteCurrency'], inputQuantity=price, description="Purchase")
  #entry.addItem(account="Assets:Wallet",
  #              currency=fill['quoteCurrency'], quantity=-price*size, description="y")
  
  #  {'id': 63820377, 'market': 'SOL/USD', 'future': None, 'baseCurrency': 'SOL', 'quoteCurrency': 'USD', 
  # 'type': 'order', 'side': 'buy', 'price': 89.7775, 'size': 15.0, 'orderId': 4216671021, 
  # 'time': '2022-03-21T13:54:26.393415+00:00', 'tradeId': 27130489, 'feeRate': 0.0008, 'fee': 0.012, 
  # 'feeCurrency': 'SOL', 'liquidity': 'maker'}
  doItRight = True
  if not doItRight and fill['quoteCurrency'] != fill['feeCurrency']:
    entry.addItem(account="Expenses:Fees", currency=fill['feeCurrency'], quantity=fee, inputCommodity=fill['quoteCurrency'], inputQuantity=price, description='Fee rate of {0} as {makerOrTaker}'.format(fill['feeRate'], makerOrTaker=fill['liquidity']))
  else:
    entry.addItem(account="Expenses:Fees", currency=fill['feeCurrency'], quantity=fee, description='Fee rate of {feeRate} as {makerOrTaker}'.format(feeRate= fill['feeRate'], makerOrTaker = fill['liquidity']))
  entry.addItem(account="Assets:Wallet", currency=fill['feeCurrency'])


for deposit in ftxClient.get_deposit_history():
  if deposit['size'] != None:
    currency = deposit['coin']
    quantity = deposit['size']
    entry = ledger.addEntry(
      date=datetime.fromisoformat(deposit['time']),
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


