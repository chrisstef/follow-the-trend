# Importing relevant libraries.
from datetime import datetime
import warnings
import ccxt
import config
import schedule
import pandas as pd
import time

pd.set_option('display.max_rows', None)

warnings.filterwarnings('ignore')


exchange = ccxt.binance({
    "apiKey": config.API_KEY,
    "secret": config.API_SECRET,
    'enableRateLimit': True,
})

# To run binance paper trading. Comment out to run with real money.
exchange.set_sandbox_mode(True)


def tr(data):
    data['previous_close'] = data['close'].shift(1)
    data['high-low'] = abs(data['high'] - data['low'])
    data['high-pc'] = abs(data['high'] - data['previous_close'])
    data['low-pc'] = abs(data['low'] - data['previous_close'])

    tr = data[['high-low', 'high-pc', 'low-pc']].max(axis=1)

    return tr


def atr(data, period):
    data['tr'] = tr(data)
    atr = data['tr'].rolling(period).mean()

    return atr


def supertrend(df, period=config.PERIOD, atr_multiplier=config.ATR_FACTOR):
    hl2 = (df['high'] + df['low']) / 2
    df['atr'] = atr(df, period)
    df['upperband'] = hl2 + (atr_multiplier * df['atr'])
    df['lowerband'] = hl2 - (atr_multiplier * df['atr'])
    df['in_uptrend'] = True

    for current in range(1, len(df.index)):
        previous = current - 1

        if (df['close'][current] > df['upperband'][previous]):
            df['in_uptrend'][current] = True
        elif (df['open'][current] < df['lowerband'][previous]):
            df['in_uptrend'][current] = False
        else:
            df['in_uptrend'][current] = df['in_uptrend'][previous]

            if df['in_uptrend'][current] and df['lowerband'][current] < df['lowerband'][previous]:
                df['lowerband'][current] = df['lowerband'][previous]

            if not df['in_uptrend'][current] and df['upperband'][current] > df['upperband'][previous]:
                df['upperband'][current] = df['upperband'][previous]

    return df


in_position = False


def check_buy_sell_signals(df):
    global in_position

    print("Checking for buy and sell signals...")
    print(df.tail(config.LOGS_DISPLAYED + 1))
    last_row_index = len(df.index) - 1
    previous_row_index = last_row_index - 1

    if not df['in_uptrend'][previous_row_index] and df['in_uptrend'][last_row_index]:
        print("Changed to Uptrend. Buy Signal!")
        if not in_position:
            order = exchange.create_market_buy_order(
                config.SYMBOL, config.QUANTITY)
            print(order)
            in_position = True
        else:
            print("Just bought. Waiting to sell...")

    if df['in_uptrend'][previous_row_index] and not df['in_uptrend'][last_row_index]:
        if in_position:
            print("Changed to Downtrend! Sell Signal!")
            order = exchange.create_market_sell_order(
                config.SYMBOL, config.QUANTITY)
            print(order)
            in_position = False
        else:
            print("Just sold. Waiting to buy...")


def run_bot():
    print('Agent is working...')
    print(f"Fetching new bars for: {datetime.now().isoformat()}")
    bars = exchange.fetch_ohlcv(
        config.SYMBOL, timeframe=config.TIMEFRAME, limit=config.LOOKBACK)
    df = pd.DataFrame(bars[:-1], columns=['timestamp',
                      'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

    supertrend_data = supertrend(df)

    check_buy_sell_signals(supertrend_data)


schedule.every(1).minutes.at(":05").do(run_bot)


while True:
    schedule.run_pending()
    time.sleep(1)

# fig = go.Figure(data=[go.Candlestick(x=df['timestamp'],
    #             open=df['open'],
    #             high=df['high'],
    #             low=df['low'],
    #             close=df['close'])])

    # fig.add_trace(go.Scatter(x=df["timestamp"], y=df["upperband"], name="upperband"))
    # fig.add_trace(go.Scatter(x=df["timestamp"], y=df["lowerband"], name="lowerband"))

    # fig.update_layout(xaxis_rangeslider_visible = False, title = 'BSW Price')
    # fig.update_xaxes(title_text = 'Date')
    # fig.update_yaxes(title_text = 'Price', tickprefix = '$')

    # fig.show()

    # df['close'] = ((df['open'] + df['high'] + df['low'] + df['close'])/4)
    # df['open'] = (df['open'].shift(1) + df['close'].shift(1))/2
    # df['high'] = df[['open', 'close', 'high']].max(axis=1)
    # df['low'] = df[['open', 'close', 'low']].min(axis=1)

# Extra condition.
# or (abs(df['high'][previous] - df['upperband'][previous]) > abs(df['upperband'][previous] - df['close'][previous]))
# or (abs(df['low'][previous] - df['lowerband'][previous]) > abs(df['lowerband'][previous] - df['open'][previous]))
