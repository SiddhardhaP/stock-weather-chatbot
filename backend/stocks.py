import yfinance as yf
import requests
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import re
from dateutil import parser as date_parser

# Note: yfinance can sometimes be a bit slow or have intermittent issues.
# Consider adding more robust error handling or retries if this were for production.


class StockTool:
    """Tool for fetching global stock information"""

    @staticmethod
    def company_name_to_symbol(company: str, exchange: str = "") -> str:
        """
        Convert company name to stock ticker symbol using Yahoo Finance search

        Args:
            company: Company name (e.g., "Samsung")
            exchange: Optional exchange code (e.g., "NSI" for NSE India)

        Returns:
            Stock ticker symbol (e.g., "005930.KS" for Samsung)

        Raises:
            ValueError: If company not found
        """
        try:
            # Search using Yahoo Finance's auto-complete
            url = f"https://query2.finance.yahoo.com/v1/finance/search?q={company}"
            if exchange:
                url += f"&exchange={exchange}"

            response = requests.get(
                url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10
            )
            response.raise_for_status()
            data = response.json()

            if not data.get("quotes") or not data["quotes"]:
                raise ValueError(
                    f"No symbol found for '{company}' on exchange '{exchange if exchange else 'any'}'."
                )

            # Return the first result's symbol
            return data["quotes"][0]["symbol"]

        except requests.exceptions.RequestException as e:
            raise ValueError(
                f"Symbol lookup network request failed for '{company}': {str(e)}"
            )
        except Exception as e:
            raise ValueError(f"Symbol lookup failed for '{company}': {str(e)}")

    @staticmethod
    def _parse_date_string(specific_date_str: Optional[str]) -> Optional[datetime.date]:
        """
        Parse a date string into a datetime.date object, handling relative terms.
        Includes debug prints to trace execution.
        """
        if not specific_date_str:
            print("[STOCKS_PY_DEBUG] _parse_date_string received None or empty string.")
            return None

        print(f"[STOCKS_PY_DEBUG] _parse_date_string received: '{specific_date_str}'")

        sds_lower = specific_date_str.lower()
        today_date = datetime.now().date()

        if sds_lower == "yesterday":
            print(f"[STOCKS_PY_DEBUG] Matched 'yesterday', returning {today_date - timedelta(days=1)}")
            return today_date - timedelta(days=1)
        elif sds_lower == "today":
            print(f"[STOCKS_PY_DEBUG] Matched 'today', returning {today_date}")
            return today_date
        elif sds_lower == "tomorrow":
            print(f"[STOCKS_PY_DEBUG] Matched 'tomorrow', returning {today_date + timedelta(days=1)}")
            return today_date + timedelta(days=1)
        # "last_week" is handled by a separate 'if' block in get_stock_data before this function is called.

        # If not one of the common relative terms, try parsing as a specific date string
        try:
            print(f"[STOCKS_PY_DEBUG] Attempting date_parser.parse('{specific_date_str}')")
            parsed_dt_obj = date_parser.parse(specific_date_str)
            print(f"[STOCKS_PY_DEBUG] date_parser.parse initial result: {parsed_dt_obj}")

            # Re-integrate year correction logic for specific dates,
            # in case langgraph_core passes a date string without a year that dateutil might misinterpret.
            year_match_in_string = re.search(r'\b(\d{4})\b', specific_date_str)
            print(f"[STOCKS_PY_DEBUG] year_match_in_string: {year_match_in_string}")
            if year_match_in_string:
                explicit_year_from_string = int(year_match_in_string.group(1))
                print(f"[STOCKS_PY_DEBUG] Explicit year from string: {explicit_year_from_string}")
                if parsed_dt_obj.year != explicit_year_from_string:
                    parsed_dt_obj = parsed_dt_obj.replace(year=explicit_year_from_string)
                    print(f"[STOCKS_PY_DEBUG] After explicit year replacement: {parsed_dt_obj}")
            else: # No explicit year in string, dateutil might pick next year if M/D passed
                  # This case is less likely if langgraph_core._extract_date_from_input is robust
                today = datetime.now().date() # Need today's date here for comparison
                if parsed_dt_obj.year > today.year and \
                   (parsed_dt_obj.month < today.month or \
                   (parsed_dt_obj.month == today.month and parsed_dt_obj.day <= today.day)):
                    parsed_dt_obj = parsed_dt_obj.replace(year=today.year)
                    print(f"[STOCKS_PY_DEBUG] Rolled back year to current: {parsed_dt_obj}")

            final_date = parsed_dt_obj.date()
            print(f"[STOCKS_PY_DEBUG] Final parsed_date: {final_date}")
            return final_date
        except (ValueError, OverflowError) as date_err:
            print(f"[STOCKS_PY_DEBUG] date_parser.parse failed for '{specific_date_str}': {date_err}")
            # Append original error for more context if date_parser.parse fails for specific dates.
            raise ValueError(f"Invalid date format: '{specific_date_str}'. Please use a recognizable date. Original error: {date_err}")

    @staticmethod
    def _get_date_range(date_obj: datetime.date) -> tuple[datetime.date, datetime.date]:
        """Given a date, return a tuple of (start_date, end_date) for yfinance."""
        start_date = date_obj
        end_date = date_obj + timedelta(days=1) # yfinance's end date is exclusive
        return start_date, end_date

    def get_stock_data(
        symbol: str, specific_date_str: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get stock price information for any global stock, either current, for a specific date, or last week's average.

        Args:
            symbol: Stock ticker symbol (e.g., "TCS.NS" for Tata Consultancy on NSE)
            specific_date_str: Optional date string (e.g., "2023-06-05", "June 5", "yesterday", "last_week")

        Returns:
            Dictionary with stock data. Structure varies based on whether a date is provided.
        """
        try:
            stock = yf.Ticker(symbol)
            info = stock.info

            if specific_date_str == "last_week":
                today = datetime.now().date()
                # Calculate Monday of the current week
                start_of_this_week = today - timedelta(days=today.weekday())
                # End of last week is Sunday before this Monday
                end_of_last_week = start_of_this_week - timedelta(days=1)
                # Start of last week is Monday, 6 days before Sunday of last week
                start_of_last_week = end_of_last_week - timedelta(days=6)

                history = stock.history(
                    start=start_of_last_week.strftime("%Y-%m-%d"),
                    end=(end_of_last_week + timedelta(days=1)).strftime("%Y-%m-%d")
                )

                if history.empty or 'Close' not in history.columns or history['Close'].isna().all():
                    raise ValueError(
                        f"No trading data found for {symbol} for last week ({start_of_last_week.strftime('%Y-%m-%d')} to {end_of_last_week.strftime('%Y-%m-%d')})."
                    )

                average_price = history['Close'].mean()
                min_price = history['Low'].min()
                max_price = history['High'].max()
                total_volume = history['Volume'].sum()

                return {
                    "type": "weekly_average",
                    "start_date": start_of_last_week.strftime("%Y-%m-%d"),
                    "end_date": end_of_last_week.strftime("%Y-%m-%d"),
                    "average_price": f"{average_price:.2f}",
                    "min_price": f"{min_price:.2f}",
                    "max_price": f"{max_price:.2f}",
                    "total_volume": f"{int(total_volume):,}",
                    "symbol": symbol,
                    "name": info.get("longName", info.get("shortName", symbol)),
                    "currency": info.get("currency", "USD"),
                }

            if specific_date_str:
                # Use the dedicated parsing method
                parsed_date = StockTool._parse_date_string(specific_date_str)
                if not parsed_date:
                     # This case should ideally be caught by _parse_date_string raising ValueError
                     raise ValueError(f"Could not parse date string: '{specific_date_str}'.")


                start_date_dt, end_date_dt = StockTool._get_date_range(parsed_date)

                history = stock.history(
                    start=start_date_dt.strftime("%Y-%m-%d"),
                    end=end_date_dt.strftime("%Y-%m-%d"),
                )

                if history.empty:
                    raise ValueError(
                        f"No trading data found for {symbol} on {parsed_date.strftime('%Y-%m-%d')}. "
                        f"The date might be a weekend, a holiday, a future date for which no trading has occurred, "
                        f"or it's outside the stock's available historical range."
                    )

                day_data = history.iloc[0]
                return {
                    "type": "historical",
                    "date": parsed_date.strftime("%Y-%m-%d"),
                    "open": f"{day_data['Open']:.2f}",
                    "high": f"{day_data['High']:.2f}",
                    "low": f"{day_data['Low']:.2f}",
                    "close": f"{day_data['Close']:.2f}",
                    "volume": f"{int(day_data['Volume']):,}",
                    "symbol": symbol,
                    "name": info.get("longName", info.get("shortName", symbol)),
                    "currency": info.get("currency", "USD"),
                }
            else:
                # Fetch current data
                history = stock.history(period="2d")

                if (
                    history.empty
                    or "Close" not in history.columns
                    or len(history["Close"]) == 0
                ):
                    current_price_val = info.get(
                        "currentPrice", info.get("regularMarketPreviousClose")
                    )
                    if current_price_val is None:
                        raise ValueError(
                            f"No current price or trading data available for {symbol}"
                        )
                    return {
                        "type": "current",
                        "price": f"{current_price_val:.2f}",
                        "change": "N/A",
                        "change_percent": "N/A",
                        "symbol": symbol,
                        "name": info.get("longName", info.get("shortName", symbol)),
                        "currency": info.get("currency", "USD"),
                    }

                current_price = history["Close"].iloc[-1]
                previous_close = (
                    history["Close"].iloc[-2] if len(history["Close"]) > 1 else current_price
                )

                price_val = float(current_price)
                change_val = price_val - float(previous_close)
                change_pct_val = (
                    (change_val / float(previous_close)) * 100
                    if float(previous_close) != 0
                    else 0.0
                )

                return {
                    "type": "current",
                    "price": f"{price_val:.2f}",
                    "change": f"+{change_val:.2f}" if change_val >= 0 else f"{change_val:.2f}",
                    "change_percent": f"{change_pct_val:.2f}%",
                    "symbol": symbol,
                    "name": info.get("longName", info.get("shortName", symbol)),
                    "currency": info.get("currency", "USD"),
                }
        except Exception as e:
            raise ValueError(f"Failed to fetch stock data for {symbol} using yfinance: {str(e)}")


# This function will be imported by langgraph_core.py
def get_stock_price(ticker_or_company_name: str, date_str: Optional[str] = None) -> Dict[str, str]:
    """
    Fetches stock price for a given ticker/company name, optionally for a specific date or last week's average,
    and returns a structured dictionary.
    """
    try:
        if "." in ticker_or_company_name or ticker_or_company_name.isupper():
            symbol = ticker_or_company_name
        else:
            symbol = StockTool.company_name_to_symbol(ticker_or_company_name)

        stock_data = StockTool.get_stock_data(symbol, specific_date_str=date_str)

        company_display_name = stock_data.get("name", symbol)
        currency = stock_data.get("currency", "")

        response_content = ""
        if stock_data.get("type") == "historical":
            response_content = (
                f"📈 Here's the stock data for {company_display_name} ({stock_data['symbol']}) on {stock_data['date']}:\n"
                f"  🔵 Open: {currency} {stock_data['open']}\n"
                f"  🔼 High: {currency} {stock_data['high']}\n"
                f"  🔽 Low: {currency} {stock_data['low']}\n"
                f"  ⚫ Close: {currency} {stock_data['close']}\n"
                f"  📊 Volume: {stock_data['volume']}"
            )
        elif stock_data.get("type") == "weekly_average":
            response_content = (
                f"📈 Here's the stock summary for {company_display_name} ({stock_data['symbol']}) for last week ({stock_data['start_date']} to {stock_data['end_date']}):\n"
                f"  💵 Average Close: {currency} {stock_data['average_price']}\n"
                f"  🔼 Week's High: {currency} {stock_data['max_price']}\n"
                f"  🔽 Week's Low: {currency} {stock_data['min_price']}\n"
                f"  📊 Total Volume: {stock_data['total_volume']}"
            )
        elif stock_data.get("type") == "current":
            change_str = stock_data['change']
            change_icon = "📈" if not change_str.startswith('-') else "📉"
            response_content = (
                f"{change_icon} For {company_display_name} ({stock_data['symbol']}), the current price is **{currency} {stock_data['price']}**. "
                f"The daily change is {stock_data['change']} ({stock_data['change_percent']})."
            )
        else:
            response_content = f"Could not determine data type for {company_display_name}."

        return {"status": "success", "content": response_content}

    except ValueError as e:
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":

    def cli_main():
        print("🌍 Global Stock Lookup (CLI)")
        print("---------------------------")
        while True:
            try:
                company = input(
                    "\nEnter company name or ticker (or 'quit' to exit): "
                ).strip()
                if company.lower() == "quit":
                    break

                date_input_str = input(
                    "Enter specific date (e.g., YYYY-MM-DD, June 5, yesterday, last week) or leave blank for current: "
                ).strip()
                if not date_input_str:
                    date_input_str = None
                elif date_input_str.lower() == "last week":
                    date_input_str = "last_week"

                output_dict = get_stock_price(company, date_input_str)
                if output_dict["status"] == "success":
                    print(f"\n{output_dict['content']}\n")
                else:
                    print(f"\n❌ Error: {output_dict['message']}\n")

            except ValueError as e_cli:
                print(f"❌ Error: {e_cli}")
            except KeyboardInterrupt:
                print("\nGoodbye! 👋")
                break

    cli_main()