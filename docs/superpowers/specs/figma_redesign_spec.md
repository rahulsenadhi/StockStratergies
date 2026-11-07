# Redesign Specification: NSE Strategy Hub (Next.js Version)

This document provides a screen-by-screen feature list and structured Figma design prompts for recreating the screens of the **NSE Strategy Hub** web application in Figma. After designing these screens in Figma, you can paste the frame links or use the Figma MCP server to inspect the layouts, allowing us to accurately translate your new designs into clean React code.

---

## 1. Global Navigation Layout
*   **Source File:** [layout.tsx](file:///c:/Users/User/Documents/Stocks/Nifty%20Momentum%20Rotation%20Stratergy/web/app/layout.tsx)
*   **Layout & Hierarchy:** 
    *   Top sticky navigation bar.
    *   Left-aligned logo/title: "NSE Strategy Hub" (bold, premium sans-serif).
    *   Horizontal links: Home (`/`), Leaderboard (`/leaderboard`), Screener (`/screener`), Suggestions (`/suggestions`), Insights (`/insights`).
    *   Clean dark mode background (slate-950 or neutral-950) with glassmorphism header border.
*   **Figma Prompt:**
    ```text
    Design a sticky global navigation header for a premium dark-themed finance application. Left-align the title "NSE Strategy Hub" in a bold modern font. On the right, include horizontal nav links with hover states for: Home, Leaderboard, Screener, Suggestions, and Insights. Background should be glassmorphic semi-transparent dark grey (e.g. #090d16 at 80% opacity) with a thin subtle border underneath.
    ```

---

## 2. Dashboard Home Page
*   **Source File:** [page.tsx](file:///c:/Users/User/Documents/Stocks/Nifty%20Momentum%20Rotation%20Stratergy/web/app/page.tsx)
*   **Features:**
    1.  **Overview Title:** "NSE Strategy Hub"
    2.  **Home KPI Strip:** Shows total assets, composite CAGR, active positions, and last run time.
    3.  **Combined Equity Chart:** LWC Multi-line overlay showing all 4 strategies rebased to a starting value of 0%. Uses distinct harmonious colors.
    4.  **Top Performers (3 Cards):** Small cards showing Strategy Name, Sharpe Ratio, CAGR, and Max Drawdown.
    5.  **Recent Backtests (Table/List of 5):** Strategy Name, Type, Run Date, Status badge (e.g., green "Ready", blue "Running").
    6.  **Live Signals Feed:** Multi-column view (one for each strategy with signal data, e.g., Monthly Rotation, Momentum Edge) displaying the top stock ticker picks and their signal badges (Strong BUY, Mild BUY, Watch).
*   **Figma Prompt:**
    ```text
    Design a dashboard homepage for a stock trading strategy application.
    Section 1: A horizontal grid of 4 KPI metrics: Total Assets, Composite CAGR (%), Active Positions, and Last Update Timestamp.
    Section 2: A large interactive multi-line chart titled "Combined Equity (rebased to 0%)" showing the cumulative growth overlay of 4 strategies with a chart legend.
    Section 3: A two-column grid. Left column has "Top Performers" (3 compact summary cards showing Name, Sharpe Ratio, CAGR, and Max Drawdown). Right column has "Recent Backtests" listing the 5 most recently run strategies with date, type, and progress badges.
    Section 4: A full-width section titled "Live Signals" containing a horizontal flex container of columns, one for each strategy, showing lists of top picks (e.g., "ZEEL", "COALINDIA") with colorful signal badges (Strong BUY, Mild BUY, Watch).
    ```

---

## 3. Strategy Leaderboard Page
*   **Source File:** [page.tsx](file:///c:/Users/User/Documents/Stocks/Nifty%20Momentum%20Rotation%20Stratergy/web/app/leaderboard/page.tsx)
*   **Features:**
    1.  **Title & Subtitle:** "Strategy Leaderboard" and "Ranked by composite score · 4 strategies".
    2.  **Action Buttons (Right-aligned):** "+ New strategy" button (solid primary accent color), "Recompute" button (outlined), "Rebuild All" button (outlined).
    3.  **Leaderboard Table:**
        *   Columns: Rank (#), Strategy Name (clickable link to details), Type (badge), CAGR (%), Sharpe Ratio, Max Drawdown (%), Win Rate (%), Annualized Return, and 3-Year Equity Sparkline (showing a small inline path representing performance trend).
        *   Row highlight: Hover states, alternating row backgrounds.
*   **Figma Prompt:**
    ```text
    Design a "Strategy Leaderboard" dashboard screen.
    Header: "Strategy Leaderboard" title with subtitle "Ranked by composite score". On the right, place three buttons: "+ New Strategy" (primary filled accent button), "Recompute" (outlined), and "Rebuild All" (outlined).
    Main: A large, dense data table containing strategy rankings. Columns: Rank, Strategy Name, Type (Badge), CAGR, Sharpe Ratio, Max Drawdown, Win Rate, and a Sparkline column showing a green trend line of equity growth. Highlight row hover states. Premium modern dark interface.
    ```

---

## 4. Strategy Detail Page
*   **Source File:** [page.tsx](file:///c:/Users/User/Documents/Stocks/Nifty%20Momentum%20Rotation%20Stratergy/web/app/strategy/%5Bid%5D/page.tsx)
*   **Features:**
    1.  **Header:** Strategy Name, Type and Status subtitle. Action buttons on the right: "Edit", "Clone", "Delete" (destructive outline), and "Run Backtest".
    2.  **KPI Strip (5 Cards):** CAGR, Sharpe Ratio, Max Drawdown, Win Rate, Total Trades.
    3.  **Confidence Verdict:** An alert box displaying safety status (e.g., "High Confidence", "Warning: High Drawdown") calculated from CAGR/Sharpe and annual return distributions.
    4.  **Strategy Explainer Box:** Expandable rich-text box explaining how the strategy entries and exits work in plain English.
    5.  **Exit Playbook Table:** Lists rules (Take Profit, Stop Loss, Trailing, Invalidation triggers).
    6.  **Position Sizer Component:** Simple interactive UI where the user inputs their capital, and it calculates the shares to buy for each position based on current prices and hard-stops.
    7.  **Charts Section:**
        *   **Equity Curve Chart:** Clean single-line Area Chart showing portfolio value over time (green fill under line).
        *   **Drawdown Chart:** Underneath the equity curve, a negative-value Area Chart showing peak-to-trough drawdowns (red fill under line).
    8.  **Monthly Returns Heatmap:** A grid table of Years (rows) vs Months (columns: Jan–Dec, plus YTD column). Color-coded cells: deep green for large positive months, light green for small positive, white/gray for neutral, red for negative.
    9.  **History Proof Section:** Box verifying that the trade logs match the equity curve math.
    10. **Trade History Table:** Columns for Date, Action (BUY/SELL), Ticker, Price, Shares, PnL (%), and Exit Reason.
    11. **Strategy-Specific Parity Section:**
        *   **Monthly Rotation Section:** Equity vs Nifty benchmark line chart, Alpha performance metric, and full Relative Strength (RS) Ranked Stock Table (Top 5 rows highlighted with a green left-accent border).
        *   **IPO Edge Section:** Stock selector, Price & Indicator Chart (with candles/line plus indicators: SMA, EMA, BB, RSI, MACD).
        *   **Momentum Edge Section:** Price chart block, Live Actionable Signals table, Filter Funnel horizontal bar chart (narrowing down from universe to picks), and Recent Breakouts list.
        *   **PEAD Section:** Price chart block and SUE Decile Spread horizontal bar chart showing average 60-day return by Deciles 1–10.
*   **Figma Prompt:**
    ```text
    Design a comprehensive "Strategy Detail" dashboard screen.
    Section 1 (Header): Title "Monthly Rotation" with buttons "Edit", "Clone", "Delete" (red outlined), and "Run Backtest" (filled accent).
    Section 2 (KPIs): A grid of 5 tiles (CAGR, Sharpe, Max Drawdown, Win Rate, Total Trades). Below it, place a modern alert banner named "Confidence Verdict" showing a checkmark with "High Confidence" text.
    Section 3: A side-by-side widget block: Left widget is an interactive "Position Sizer" card with input fields for capital and output text showing trade sizing; right widget is "Exit Playbook" listing exit triggers.
    Section 4 (Charts): A full-width vertical stack of charts. First chart: "Equity Curve" area chart with a green line and light green gradient fill. Second chart: "Drawdown" area chart showing negative spikes with a red line and light red gradient fill.
    Section 5: "Monthly Returns Heatmap" showing a grid of years (y-axis) vs months (x-axis, Jan-Dec) with a YTD column. Cells must be color-coded on a green-to-red scale representing positive to negative returns.
    Section 6: A tabbed or stacked "Strategy Section" containing:
      - Option A: "Growth vs Nifty" overlay line chart with Nifty (amber) and strategy (green) lines, featuring an "Alpha" stat badge. Below it, "All Stocks Ranked by Strength" table where the top 5 rows have a green accent bar on the left edge.
      - Option B: "Filter Funnel" horizontal bar chart displaying stages like "Total Universe", "EMA Filter", "Price > 100", "Breakout" with percentages, highlighting the final bar.
    Section 7: "Trade History" data table showing columns: Date, Action (BUY/SELL badges), Ticker, Price, Shares, PnL %, and Exit Reason.
    ```

---

## 5. Insights Page
*   **Source File:** [page.tsx](file:///c:/Users/User/Documents/Stocks/Nifty%20Momentum%20Rotation%20Stratergy/web/app/insights/page.tsx)
*   **Features:**
    1.  **Title & Description:** "Insights — What Predicts Winners?" and explanation about closed-trade statistics.
    2.  **Closed-Trade Analytics Charts/Cards:**
        *   Grouped blocks/tables showing Win Rate, Average Trade PnL, and Total Trades.
        *   Groupings include: Setup Type (e.g., standard breakout, early boom), Recovery Speed, Relative Strength Score bucket, and Exit Reason (e.g., stop loss, time exit, target reached).
*   **Figma Prompt:**
    ```text
    Design an "Insights Dashboard" screen displaying historical trade analytics.
    Header: "Insights — What Predicts Winners?" with explanatory text.
    Body: A grid of 4 cards/tables. Each card represents a metric grouping:
      1. "Win Rate by Setup Type" (visual progress bars or horizontal bars for Standard, Early Boom, Flag setups).
      2. "Average PnL by Recovery Speed" (bar chart or list showing PnL percentage based on speed).
      3. "Performance by Relative Strength Score" (grouped table showing Win Rate and PnL for score brackets).
      4. "Exits Analysis" (donut chart or bar list showing count and PnL grouped by exit reasons like Time Exit, Hard Stop, Target Reached).
    ```

---

## 6. PEAD Screener Page
*   **Source File:** [page.tsx](file:///c:/Users/User/Documents/Stocks/Nifty%20Momentum%20Rotation%20Stratergy/web/app/screener/page.tsx)
*   **Features:**
    1.  **Title & Description:** "PEAD Screener" and explanation of post-earnings announcement drift candidates.
    2.  **Filter Controls Bar:** Input search (ticker/company), dropdown for Sector, dropdown for Piotroski Score, slider/range for SUE score, slider for P/B valuation.
    3.  **Filtered Candidates Table:** Ticker, Company, Earnings Date, SUE (earnings surprise score), Piotroski F-Score (1-9), P/B Ratio, Sector Median P/B, and Signal (Buy/Hold/Sell).
*   **Figma Prompt:**
    ```text
    Design a "PEAD Screener" search and filtering tool.
    Header: "PEAD Screener" with description of post-earnings announcement drift.
    Filter Bar: A horizontal strip of filters: text input search for ticker, dropdown for Sector, dropdown selector for Piotroski F-Score (e.g., >=7, >=8), and a range input/slider for SUE score.
    Results: A data table with columns: Ticker, Company, Earnings Date, SUE Score, Piotroski Score, P/B Ratio, Sector Median P/B, and Actionable Signal (e.g., green BUY, grey HOLD badges). Clean dark mode layout.
    ```

---

## 7. Suggestions Page
*   **Source File:** [page.tsx](file:///c:/Users/User/Documents/Stocks/Nifty%20Momentum%20Rotation%20Stratergy/web/app/suggestions/page.tsx)
*   **Features:**
    1.  **Title & Description:** "Buy These Now — Risk-Filtered Picks" and explanation of live picks ranked by edge.
    2.  **Suggestions Feed List:**
        *   Vertical list of action cards.
        *   Each card features: Large Ticker Name, Company, Strategy Source (e.g., PEAD, Momentum Edge), Rebalance Date, Current Price, Target Stop-Loss (%), Position Size Allocation (%) recommendation, and a "Buy" or "Copy Order" button.
*   **Figma Prompt:**
    ```text
    Design a "Suggestions Feed" screen displaying active buy recommendations.
    Header: "Buy These Now — Risk-Filtered Picks" with text explaining position sizing and stops.
    Feed: A vertical stack of premium cards. Each card represents a suggestion:
      - Left side: Large ticker letters (e.g., "INFY"), company name, and strategy badge (e.g., "Momentum Edge" in blue, "PEAD" in green).
      - Center: Current price, Stop-Loss price, and Recommended Position Allocation (e.g., "Allocate 15%").
      - Right side: Large CTA button "Copy Order" or "Execute Buy".
    ```

---

## 8. Create & Edit Strategy Forms
*   **Source Files:** [new/page.tsx](file:///c:/Users/User/Documents/Stocks/Nifty%20Momentum%20Rotation%20Stratergy/web/app/strategy/new/page.tsx) and [edit/page.tsx](file:///c:/Users/User/Documents/Stocks/Nifty%20Momentum%20Rotation%20Stratergy/web/app/strategy/%5Bid%5D/edit/page.tsx)
*   **Form Fields:**
    1.  **General Info Section:** Strategy Name (input text), Type (select dropdown: Momentum, Mean Reversion, PEAD, etc.), Description (textarea), Universe (select dropdown: Nifty 50, Nifty 200, All NSE).
    2.  **Formula Input Section:** Entry Formula (rich text area / code block input for systematic conditions).
    3.  **Risk & Exits Section (Checkboxes & Numerical Inputs):**
        *   Time Exit: Enabled (checkbox) + Days (number input).
        *   Hard Stop Loss: Enabled (checkbox) + Stop Loss % (number input).
        *   Trailing Stop Loss: Enabled (checkbox) + Trailing % (number input).
    4.  **Capital Sizing Section:** Max Positions (number input), Initial Capital (number input).
    5.  **Form Actions:** "Submit" button (filled primary accent, label changes from "Run Backtest" or "Save Changes"), "Cancel" button.
*   **Figma Prompt:**
    ```text
    Design a clean, multi-section configuration form for creating/editing a trading strategy.
    Section 1 (General Info): Text inputs for Strategy Name, Description, and dropdown selectors for Strategy Type and Universe.
    Section 2 (Systematic Logic): A large text area styled like a code editor input for "Entry Formula".
    Section 3 (Exits & Risk): A grid containing 3 rows of checkboxes with associated number inputs:
      - "Time-based Exit" checkbox with "Exit after [30] days" input.
      - "Hard Stop Loss" checkbox with "Stop at [8] %" input.
      - "Trailing Stop" checkbox with "Trail at [12] %" input.
    Section 4 (Capital Allocation): Numerical inputs for "Max Positions" and "Initial Capital (₹)".
    Footer: Bottom action buttons: "Run Backtest / Save Changes" (filled active state) and "Cancel" (outlined).
    ```
