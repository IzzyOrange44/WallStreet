import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from mplfinance.original_flavor import candlestick_ohlc
import os


def create_graph(df):
        # Ensure the 'date' column is a datetime type and sort by date
        df['date'] = pd.to_datetime(df['date'])
        df.sort_values('date', inplace=True)

        # Calculate Bollinger Bands
        df['MA20'] = df['close'].rolling(window=20).mean()  # 20-day moving average
        df['Upper'] = df['MA20'] + 2 * df['close'].rolling(window=20).std()
        df['Lower'] = df['MA20'] - 2 * df['close'].rolling(window=20).std()

        # Prepare candlestick data
        df_ohlc = df[['date', 'open_price', 'high', 'low', 'close']]
        df_ohlc['date'] = df_ohlc['date'].map(mdates.date2num)

        # Plot the candlestick chart with Bollinger Bands
        fig, ax = plt.subplots(figsize=(10, 6))
        candlestick_ohlc(ax, df_ohlc.values, width=0.6, colorup='green', colordown='red', alpha=0.8)

        # Plot Bollinger Bands
        ax.plot(df['date'].map(mdates.date2num), df['Upper'], color='blue', label='Upper Band')
        ax.plot(df['date'].map(mdates.date2num), df['Lower'], color='blue', label='Lower Band')
        ax.plot(df['date'].map(mdates.date2num), df['MA20'], color='orange', label='20-Day MA')

        # Formatting
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        plt.xticks(rotation=45)
        plt.title(f"Bollinger Bands for {df['ticker'].iloc[0]}")
        plt.legend()
        plt.tight_layout()

        # Save the plot as a PNG file
        chart_path = os.path.join('static', 'bollinger_chart.png')
        plt.savefig(chart_path)
        plt.close(fig)

        # Convert the DataFrame to HTML
        df_html = df.to_html(classes='data', header="true")

        return df_html, chart_path