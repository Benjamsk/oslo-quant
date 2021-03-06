from abc import ABCMeta, abstractmethod
from copy import deepcopy
import numpy as np
import datetime

import markets
from . import broker

class Order(object):
    """An order recommendation"""

    def __init__(self, ticker, action, quantity, price=None):
        """
        Args:
           ticker(str): The ticker
           action(str): 'buy' or 'sell'
           quantity(int): The number of shared
           price(float): Limit price or None for market value
        """
        self.ticker = ticker
        self.action = action
        self.quantity = quantity
        self.price = price
        self.filled = False
        self.filled_price = None
        self.cost = None
        
    def __str__(self):
        s = "%s %d %s" % (self.action, self.quantity, self.ticker)
        
        # check if self.price is defined
        if self.price is None:
            s += ", market price"
        else:
            s += ", limit: " + str(round(self.price, 2))

        if self.filled:
            s += ", filled: " + str(round(self.filled_price, 2))
            s += ", cost: " + str(round(self.cost, 2))
            s += ", brokerage: " + str(round(self.brokerage, 2))
            s += ", total: " + str(round(self.total, 2))
        else:
            s += ", open"
            
        return s
        
    def fill(self, filled_price):
        """
        Fill this order.
        Typically this function will be called by the simulator.

        Args:
           filled_price(float): The matched price for this order
        """
        self.filled_price = filled_price
        self.filled = True
        self.brokerage = broker.calculate_brokerage(self)
        self.cost = self.quantity * self.filled_price
        self.total = self.cost + self.brokerage

class Share(object):
    """A share holding position"""

    def __init__(self, ticker, quantity, price):
        """
        Args:
           ticker(str): The ticker
           quantity(int): The number of shares (negative for short)
           price(float): The purchase price per share
        """
        self.ticker = ticker
        self.quantity = quantity
        self.price = price

    def get_value(self, date):
        """
        Get the closing value of an instrument at a given date
        The closing value will be used if it exists,
        otherwise the 'value' field will be used.
        Nasdaq OMX data typical doesn't have closing values.

        Args:
           date(datetime.date): Date to get value for

        Return:
           The monetary value of the asset
        """
        instrument = markets.get_instrument(self.ticker)
        
        # if this date doesn't have any data, assume its worth the last known value
        day_data = instrument.get_day_or_last_before(date)

        # preferably use the 'close' field, then the 'value' field
        try:
            current_price = day_data['close']
        except KeyError:
            current_price = day_data['value']

        return self.quantity * current_price
        
class Strategy(object, metaclass=ABCMeta):
    """Base class for all strategies"""

    @abstractmethod
    def __init__(self, money, portfolio, from_date, to_date):
        """
        Override this method and call super()

        Args:
           money(float): Initial liquid assets
           portfolio: Dict of Share objects indexed by ticker
                     represening the intital share holding positions
           from_date(datetime.date): First daty of the simulation
           to_date(datetime.date): Last day of the simulation
        """
        self.money = money
        self.portfolio = portfolio
        self.today = from_date
        self.from_date = from_date
        self.to_date = to_date

    def __str__(self):
        """
        Return the name of the subclass
        """
        return self.__class__.__name__
        
    @abstractmethod
    def execute(self, today, portfolio, money):
        """
        Override this method and call super()

        This method shall assume that we have data only upto the
        trading day before <today>. This method is typically run on
        before the trading opens. A list of order recommendations for
        today shall be returned.
        
        Args:
           today(datetime.date): Present day
           portfolio: The updated portfolio.
           money(float): The updated liquid funds

        Return:
           A list of Order objects
        """
        self.today = today
        self.portfolio = portfolio
        self.money = money

    def get_instrument(self, ticker):
        """
        Get an altered version of the instrument which only contains
        date up till today.

        Args:
           ticker(str): Ticker name
        
        Return:
           A deepcopied version of the Instrument object

        Raises:
           ValueError: If the ticker doesn't exist for this date.
                       For instance when trying to get 'NAS.OSE'
                       and today's date is before 2003-12-18.
        """
        # get a copy of the Instrument object which we can modify
        instrument = deepcopy(markets.get_instrument(ticker))
        
        # Check that this ticker existed at today's date
        if not instrument.existed_at_date(self.today):
            raise ValueError("'" + ticker + "' didn't exist at " + str(self.today) + \
                             ", first date: " + str(instrument.get_first_date()) + \
                             ", last date: " + str(instrument.get_last_date()))

        # We already know that this date exists for this ticker.
        # If there is no date, it means there were no trades this date,
        # Therefore we will look for this date, or the last preceding date.
        row_index = instrument.get_day_index_or_last_before(self.today)

        # delete data which is into the future and the strategy now nothing of
        instrument.data = np.delete(instrument.data, np.s_[row_index + 1:])

        return instrument

    def get_instruments(self):
        """
        Get a list of instruments that exist at today's date

        Return:
           Alphabetically sorted list of tickers
        """
        # All tickers that ever existed
        all_instruments = markets.get_tickers()
        
        todays_instruments = []
        for t in all_instruments:

            # If a ValueError is raised, it mean it exist today
            try:
                i = self.get_instrument(t)
                todays_instruments.append(i)
            except ValueError:
                pass

        return todays_instruments

    def trading_days(self, from_date, to_date):
        """
        Find the closed interval of trading days between two dates

        Args:
        from_date(datetime.date):
        to_date(datetime.date):

        Yields:
        datetime.date objects
        """
        yield markets.trading_days(from_date, to_date)

    def trading_days_ago(self, days):
        """
        Find the date N trading days in the past from today

        Args:
            days(int): Number of days to count backwards

        Return:
            datetime.date

        Raises:
            KeyError: If there is no data for either of the dates
        """
        return markets.trading_days_ago(self.today, days)