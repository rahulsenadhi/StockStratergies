"""
Momentum Rotation Strategy Backtest for Nifty 50 Stocks
- Monthly rebalancing based on Relative Strength (RS) vs NiftyBees benchmark
- Only stocks with positive RS qualify for selection
- Hold top 5 qualifying stocks with equal weight
- Smart rotation: hold stocks that remain in top 5, sell those that drop out
"""

import pandas as pd
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt
from datetime import datetime
import warnings

warnings.filterwarnings('ignore')

class MomentumRotationBacktest:
    def __init__(self, initial_capital=50000, top_n=5):
        self.initial_capital = initial_capital
        self.top_n = top_n
        
        self.data_folder = Path('data')
        self.prices = {}
        self.monthly_prices = {}
        self.benchmark = None
        self.benchmark_monthly = None
        
        self.portfolio = {}  # {ticker: shares}
        self.cash = initial_capital
        self.portfolio_value = []
        self.portfolio_dates = []
        self.rebalance_log = []
        
    def load_data(self):
        """Load all CSV files from data folder."""
        print("Loading data files...")
        
        # Use today as cutoff so backtest always includes the latest available data
        cutoff_date = pd.Timestamp(datetime.now().date())
        
        # Load benchmark
        benchmark_file = self.data_folder / 'NIFTYBEES.NS.csv'
        if not benchmark_file.exists():
            raise FileNotFoundError(f"Benchmark file not found: {benchmark_file}")
        
        bench_df = pd.read_csv(benchmark_file, index_col=0, parse_dates=True)
        bench_df = bench_df.sort_index()
        # Filter out future dates
        bench_df = bench_df[bench_df.index <= cutoff_date]
        # Get the first column (it will be named after the ticker)
        self.benchmark = bench_df.iloc[:, 0]
        print(f"  ✓ Benchmark (NIFTYBEES.NS) loaded: {len(self.benchmark)} records (up to {self.benchmark.index[-1].date()})")
        
        # Load stock data
        csv_files = list(self.data_folder.glob('*.csv'))
        for csv_file in csv_files:
            ticker = csv_file.stem
            
            # Skip benchmark
            if ticker == 'NIFTYBEES.NS':
                continue
            
            try:
                df = pd.read_csv(csv_file, index_col=0, parse_dates=True)
                df = df.sort_index()
                # Filter out future dates
                df = df[df.index <= cutoff_date]
                
                if df.empty:
                    print(f"  ✗ {ticker}: Empty data after filtering")
                    continue
                
                # Get the first column (it will be named after the ticker)
                self.prices[ticker] = df.iloc[:, 0]
                print(f"  ✓ {ticker}: {len(self.prices[ticker])} records")
            
            except Exception as e:
                print(f"  ✗ {ticker}: {str(e)[:50]}")
        
        print(f"\nSuccessfully loaded {len(self.prices)} stocks\n")
        
        if len(self.prices) < 1:
            raise ValueError(f"Need at least 1 stock, but only {len(self.prices)} loaded")
    
    def prepare_monthly_data(self):
        """Resample to monthly data (last trading day of month)."""
        print("Preparing monthly data...")

        # Benchmark monthly — drives the date spine
        self.benchmark_monthly = self.benchmark.resample('ME').last()

        # Stock monthly prices — each stock keeps its own available range.
        # Stocks that lack data for a given month are simply skipped in RS
        # calculation (see calculate_relative_strength).
        for ticker, prices in self.prices.items():
            self.monthly_prices[ticker] = prices.resample('ME').last()

        print(f"  Date range: {self.benchmark_monthly.index[0].date()} "
              f"to {self.benchmark_monthly.index[-1].date()}")
        print(f"  Monthly periods: {len(self.benchmark_monthly)}\n")
    
    def calculate_relative_strength(self, month_idx):
        """Calculate RS scores for all stocks at given month."""
        if month_idx < 1:  # Need previous month for calculation
            return {}
        
        prev_month_idx = month_idx - 1
        curr_month_idx = month_idx
        
        prev_date = self.benchmark_monthly.index[prev_month_idx]
        curr_date = self.benchmark_monthly.index[curr_month_idx]
        
        prev_bench = self.benchmark_monthly.iloc[prev_month_idx]
        curr_bench = self.benchmark_monthly.iloc[curr_month_idx]
        
        # Calculate benchmark return
        bench_return = ((curr_bench - prev_bench) / prev_bench) * 100 if prev_bench > 0 else 0
        
        rs_scores = {}
        
        for ticker in self.monthly_prices:
            prices = self.monthly_prices[ticker]
            
            # Check if stock has data for both months
            if prev_date not in prices.index or curr_date not in prices.index:
                continue
            
            prev_price = prices[prev_date]
            curr_price = prices[curr_date]
            
            # Calculate stock return
            stock_return = ((curr_price - prev_price) / prev_price) * 100 if prev_price > 0 else 0
            
            # Calculate RS
            rs = stock_return - bench_return
            
            rs_scores[ticker] = {
                'stock_return': stock_return,
                'bench_return': bench_return,
                'rs_score': rs,
                'curr_price': curr_price
            }
        
        return rs_scores
    
    def get_qualifying_stocks(self, rs_scores):
        """Filter stocks with positive RS and return top N."""
        # Filter for positive RS only
        qualifying = {ticker: data for ticker, data in rs_scores.items() if data['rs_score'] > 0}
        
        if not qualifying:
            return []
        
        # Sort by RS score descending and take top N
        sorted_stocks = sorted(qualifying.items(), key=lambda x: x[1]['rs_score'], reverse=True)
        top_qualifying = [ticker for ticker, _ in sorted_stocks[:self.top_n]]
        
        return top_qualifying
    
    def calculate_portfolio_value(self, month_idx):
        """Calculate current portfolio value."""
        curr_date = self.benchmark_monthly.index[month_idx]
        portfolio_value = self.cash
        
        for ticker, shares in self.portfolio.items():
            if ticker in self.monthly_prices and curr_date in self.monthly_prices[ticker].index:
                price = self.monthly_prices[ticker][curr_date]
                portfolio_value += shares * price
        
        return portfolio_value
    
    def rebalance(self, month_idx, new_top_stocks, curr_date):
        """Rebalance portfolio at month end."""
        old_holdings = set(self.portfolio.keys())
        new_holdings = set(new_top_stocks)
        
        # Smart hold rule: stocks that remain in top 5
        hold_stocks = old_holdings & new_holdings
        sell_stocks = old_holdings - new_holdings
        buy_stocks = new_holdings - old_holdings
        
        # Sell stocks that dropped out
        cash_from_sales = 0
        for ticker in sell_stocks:
            if ticker in self.monthly_prices and curr_date in self.monthly_prices[ticker].index:
                price = self.monthly_prices[ticker][curr_date]
                shares = self.portfolio[ticker]
                cash_from_sales += shares * price
                del self.portfolio[ticker]
        
        self.cash += cash_from_sales
        
        # Buy new stocks (equal weight)
        if buy_stocks:
            capital_to_invest = min(self.cash, len(buy_stocks) * (self.initial_capital / self.top_n))
            amount_per_stock = capital_to_invest / len(buy_stocks)
            
            for ticker in buy_stocks:
                if ticker in self.monthly_prices and curr_date in self.monthly_prices[ticker].index:
                    price = self.monthly_prices[ticker][curr_date]
                    shares = amount_per_stock / price if price > 0 else 0
                    self.portfolio[ticker] = shares
                    self.cash -= amount_per_stock
        
        # Log rebalance
        self.rebalance_log.append({
            'Date': curr_date,
            'Top5_Stocks': ', '.join(sorted(new_top_stocks)),
            'Stocks_Sold': ', '.join(sorted(sell_stocks)),
            'Stocks_Bought': ', '.join(sorted(buy_stocks)),
            'Stocks_Held': ', '.join(sorted(self.portfolio.keys())),
            'Portfolio_Value': self.calculate_portfolio_value(month_idx)
        })
    
    def run_backtest(self):
        """Run the backtest."""
        print("Running backtest...\n")
        
        months = self.benchmark_monthly.index
        
        # Track portfolio value at each month
        for month_idx in range(len(months)):
            curr_date = months[month_idx]
            
            # For first month, just track value (no rebalancing yet)
            if month_idx == 0:
                port_value = self.calculate_portfolio_value(month_idx)
                self.portfolio_dates.append(curr_date)
                self.portfolio_value.append(port_value)
                continue
            
            # Calculate RS scores and get qualifying stocks
            rs_scores = self.calculate_relative_strength(month_idx)
            new_top_stocks = self.get_qualifying_stocks(rs_scores)
            
            # Rebalance if we have qualifying stocks
            if new_top_stocks:
                self.rebalance(month_idx, new_top_stocks, curr_date)
            
            # Calculate portfolio value after rebalancing
            port_value = self.calculate_portfolio_value(month_idx)
            
            self.portfolio_dates.append(curr_date)
            self.portfolio_value.append(port_value)
        
        print(f"Backtest complete: {len(self.portfolio_value)} months\n")
    
    def calculate_metrics(self):
        """Calculate performance metrics."""
        portfolio_returns = np.array(self.portfolio_value)
        dates = np.array(self.portfolio_dates)
        
        # Portfolio metrics
        start_val = self.initial_capital
        end_val = portfolio_returns[-1]
        
        years = (dates[-1] - dates[0]).days / 365.25
        total_return = (end_val - start_val) / start_val
        cagr = (end_val / start_val) ** (1 / years) - 1 if years > 0 else 0
        
        # Max drawdown
        cummax = np.maximum.accumulate(portfolio_returns)
        drawdown = (portfolio_returns - cummax) / cummax
        max_dd = np.min(drawdown)
        
        # Monthly returns for Sharpe ratio
        monthly_returns = np.diff(portfolio_returns) / portfolio_returns[:-1]
        sharpe = np.mean(monthly_returns) / np.std(monthly_returns) * np.sqrt(12) if len(monthly_returns) > 1 else 0
        
        # Benchmark metrics — use start/end dates that match the backtest range
        bench_start = self.benchmark_monthly.loc[self.portfolio_dates[0]]
        bench_end   = self.benchmark_monthly.loc[self.portfolio_dates[-1]]
        bench_total_return = (bench_end - bench_start) / bench_start
        bench_cagr = (bench_end / bench_start) ** (1 / years) - 1 if years > 0 else 0
        
        metrics = {
            'Final_Portfolio_Value': end_val,
            'Total_Return_Pct': total_return * 100,
            'CAGR_Pct': cagr * 100,
            'Max_Drawdown_Pct': max_dd * 100,
            'Sharpe_Ratio': sharpe,
            'Benchmark_CAGR_Pct': bench_cagr * 100,
            'Benchmark_Total_Return_Pct': bench_total_return * 100,
            'Alpha_Pct': (cagr - bench_cagr) * 100,
            'Years': years
        }
        
        return metrics
    
    def save_results(self):
        """Save results to CSV and chart."""
        print("Saving results...\n")
        
        # Prepare results dataframe — align benchmark to the dates we processed
        bench_values = self.benchmark_monthly.reindex(self.portfolio_dates).values
        results_df = pd.DataFrame({
            'Date': self.portfolio_dates,
            'Portfolio_Value': self.portfolio_value,
            'Benchmark_Value': bench_values,
        })
        
        results_df.to_csv('backtest_results.csv', index=False)
        print(f"  ✓ Results saved to backtest_results.csv")
        
        # Save rebalance log
        log_df = pd.DataFrame(self.rebalance_log)
        log_df.to_csv('rebalance_log.csv', index=False)
        print(f"  ✓ Rebalance log saved to rebalance_log.csv")
        
        # Create chart
        plt.figure(figsize=(14, 7))
        
        plt.plot(results_df['Date'], results_df['Portfolio_Value'], 
                label='Momentum Rotation Strategy', linewidth=2, color='#2E86AB')
        plt.plot(results_df['Date'], results_df['Benchmark_Value'], 
                label='NiftyBees Benchmark', linewidth=2, color='#A23B72', linestyle='--')
        
        plt.xlabel('Date', fontsize=12, fontweight='bold')
        plt.ylabel('Portfolio Value (Rs)', fontsize=12, fontweight='bold')
        plt.title('Momentum Rotation Strategy vs NiftyBees Benchmark', 
                 fontsize=14, fontweight='bold', pad=20)
        plt.legend(fontsize=11, loc='upper left')
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        
        # Format y-axis as currency
        ax = plt.gca()
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'₹{x/1000:.0f}K'))
        
        plt.savefig('backtest_chart.png', dpi=300, bbox_inches='tight')
        print(f"  ✓ Chart saved to backtest_chart.png")
        
        plt.close()
    
    def print_summary(self):
        """Print backtest summary."""
        metrics = self.calculate_metrics()
        
        print("="*70)
        print("BACKTEST SUMMARY: Momentum Rotation Strategy")
        print("="*70)
        print(f"\nStrategy Parameters:")
        print(f"  Starting Capital: Rs {self.initial_capital:,.0f}")
        print(f"  Rebalance Frequency: Monthly")
        print(f"  Selection Criteria: Top {self.top_n} stocks with RS > 0")
        print(f"  Backtest Period: {self.portfolio_dates[0].date()} to {self.portfolio_dates[-1].date()}")
        print(f"  Duration: {metrics['Years']:.2f} years")
        
        print(f"\nStrategy Performance:")
        print(f"  Final Portfolio Value: Rs {metrics['Final_Portfolio_Value']:,.0f}")
        print(f"  Total Return: {metrics['Total_Return_Pct']:.2f}%")
        print(f"  CAGR: {metrics['CAGR_Pct']:.2f}%")
        print(f"  Max Drawdown: {metrics['Max_Drawdown_Pct']:.2f}%")
        print(f"  Sharpe Ratio: {metrics['Sharpe_Ratio']:.2f}")
        
        print(f"\nBenchmark (NiftyBees) Performance:")
        print(f"  Benchmark CAGR: {metrics['Benchmark_CAGR_Pct']:.2f}%")
        print(f"  Benchmark Total Return: {metrics['Benchmark_Total_Return_Pct']:.2f}%")
        
        print(f"\nAlpha Generated:")
        print(f"  CAGR Alpha: {metrics['Alpha_Pct']:+.2f}%")
        
        print(f"\nRebalancing:")
        print(f"  Total Rebalances: {len(self.rebalance_log)}")
        
        print("\n" + "="*70)

def main():
    try:
        backtest = MomentumRotationBacktest(initial_capital=50000, top_n=5)
        
        backtest.load_data()
        backtest.prepare_monthly_data()
        backtest.run_backtest()
        backtest.print_summary()
        backtest.save_results()
        
        print("\n✓ Backtest completed successfully!")
        
    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()