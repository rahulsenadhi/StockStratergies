"""
Download 3 years of daily historical data for Nifty 50 stocks from Yahoo Finance.
Saves each stock as a separate CSV file in the /data folder.
"""

import sys
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import os
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Nifty 50 stocks with their Yahoo Finance tickers
NIFTY_50_STOCKS = {
    'ADANIENT.NS': 'Adani Enterprises',
    'ADANIGREEN.NS': 'Adani Green Energy',
    'ADANIPORTS.NS': 'Adani Ports',
    'APOLLOHOSP.NS': 'Apollo Hospitals',
    'ASIANPAINT.NS': 'Asian Paints',
    'AXISBANK.NS': 'Axis Bank',
    'BAJAJ-AUTO.NS': 'Bajaj Auto',
    'BAJFINANCE.NS': 'Bajaj Finance',
    'BAJAJFINSV.NS': 'Bajaj Finserv',
    'BPCL.NS': 'Bharat Petroleum',
    'BHARTIARTL.NS': 'Bharti Airtel',
    'BRITANNIA.NS': 'Britannia Industries',
    'CIPLA.NS': 'Cipla',
    'COALINDIA.NS': 'Coal India',
    'DIVISLAB.NS': "Divi's Laboratories",
    'DRREDDY.NS': "Dr. Reddy's Laboratories",
    'EICHERMOT.NS': 'Eicher Motors',
    'GRASIM.NS': 'Grasim Industries',
    'HCLTECH.NS': 'HCL Technologies',
    'HDFCBANK.NS': 'HDFC Bank',
    'HDFCLIFE.NS': 'HDFC Life Insurance',
    'HEROMOTOCO.NS': 'Hero MotoCorp',
    'HAL.NS': 'Hindustan Aeronautics',
    'HINDUNILVR.NS': 'Hindustan Unilever',
    'ICICIBANK.NS': 'ICICI Bank',
    'INDUSINDBK.NS': 'IndusInd Bank',
    'INFY.NS': 'Infosys',
    'ITC.NS': 'ITC',
    'JSWSTEEL.NS': 'JSW Steel',
    'KOTAKBANK.NS': 'Kotak Mahindra Bank',
    'LT.NS': 'Larsen & Toubro',
    'M&M.NS': 'Mahindra & Mahindra',
    'MARUTI.NS': 'Maruti Suzuki',
    'NESTLEIND.NS': 'Nestle India',
    'NTPC.NS': 'NTPC',
    'ONGC.NS': 'Oil and Natural Gas Corporation',
    'POWERGRID.NS': 'Power Grid Corporation',
    'RELIANCE.NS': 'Reliance Industries',
    'SBILIFE.NS': 'SBI Life Insurance',
    'SBIN.NS': 'State Bank of India',
    'SUNPHARMA.NS': 'Sun Pharmaceutical',
    'TATACONSUM.NS': 'Tata Consumer Products',
    'TMCV.NS': 'Tata Motors',
    'TATASTEEL.NS': 'Tata Steel',
    'TECH.NS': 'Tech Mahindra',
    'TITAN.NS': 'Titan Company',
    'ULTRACEMCO.NS': 'UltraTech Cement',
    'UPL.NS': 'UPL',
    'WIPRO.NS': 'Wipro',
    'ZEEL.NS': 'Zee Entertainment',
}

# Benchmark
BENCHMARK = 'NIFTYBEES.NS'

def setup_data_folder():
    """Create data folder if it doesn't exist."""
    data_folder = Path('data')
    data_folder.mkdir(exist_ok=True)
    return data_folder

def download_stock_data(ticker, start_date, end_date, data_folder):
    """
    Download daily data for a single stock and save as CSV.
    
    Args:
        ticker: Stock ticker symbol
        start_date: Start date for data
        end_date: End date for data
        data_folder: Path to data folder
    
    Returns:
        tuple: (success: bool, ticker: str, message: str)
    """
    try:
        print(f"Downloading {ticker}...", end=' ')
        
        # Download data
        data = yf.download(
            ticker, 
            start=start_date, 
            end=end_date, 
            progress=False,
            multi_level_index=False
        )
        
        # Check if data is empty
        if data.empty:
            print("✗ No data found")
            return False, ticker, "No data available"
        
        # Ensure we have the necessary columns
        if 'Close' not in data.columns:
            print("✗ Close price column not found")
            return False, ticker, "Close price column not found"
        
        # Keep only Close price
        data = data[['Close']].copy()
        data.columns = [ticker]
        
        # Save to CSV
        csv_path = data_folder / f"{ticker}.csv"
        data.to_csv(csv_path)
        
        print(f"✓ ({len(data)} records)")
        return True, ticker, f"Downloaded {len(data)} records"
    
    except Exception as e:
        print(f"✗ Error: {str(e)[:50]}")
        return False, ticker, str(e)

def main():
    """Main function to orchestrate the download process."""
    # Setup
    data_folder = setup_data_folder()
    
    # Calculate date range (3 years)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=3*365)
    
    print(f"\n{'='*70}")
    print(f"Nifty 50 Stock Data Downloader")
    print(f"{'='*70}")
    print(f"Date Range: {start_date.date()} to {end_date.date()}")
    print(f"Output Folder: {data_folder.absolute()}")
    print(f"{'='*70}\n")
    
    # Download benchmark first
    print(f"Downloading Benchmark...\n")
    benchmark_success, _, benchmark_msg = download_stock_data(
        BENCHMARK, start_date, end_date, data_folder
    )
    print()
    
    # Download all Nifty 50 stocks
    print(f"Downloading Nifty 50 Stocks ({len(NIFTY_50_STOCKS)})...\n")
    
    successful = []
    failed = []
    
    for ticker, company_name in NIFTY_50_STOCKS.items():
        success, ticker_symbol, message = download_stock_data(
            ticker, start_date, end_date, data_folder
        )
        
        if success:
            successful.append((ticker, company_name))
        else:
            failed.append((ticker, company_name, message))
    
    # Print Summary
    print(f"\n{'='*70}")
    print(f"DOWNLOAD SUMMARY")
    print(f"{'='*70}")
    print(f"Benchmark: {'✓ SUCCESS' if benchmark_success else '✗ FAILED'} ({BENCHMARK})")
    print(f"Stocks Downloaded Successfully: {len(successful)}/{len(NIFTY_50_STOCKS)}")
    print(f"Stocks Failed: {len(failed)}/{len(NIFTY_50_STOCKS)}")
    print(f"{'='*70}\n")
    
    if successful:
        print("✓ SUCCESSFUL STOCKS:")
        for ticker, name in sorted(successful):
            print(f"  - {ticker:20s} ({name})")
    
    if failed:
        print(f"\n✗ FAILED STOCKS:")
        for ticker, name, message in sorted(failed):
            print(f"  - {ticker:20s} ({name})")
            print(f"    Error: {message}")
    
    print(f"\n{'='*70}")
    print(f"All data saved to: {data_folder.absolute()}")
    print(f"Total files created: {len(list(data_folder.glob('*.csv')))}")
    print(f"{'='*70}\n")

if __name__ == "__main__":
    main()
