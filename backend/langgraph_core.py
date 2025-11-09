from typing import TypedDict, Optional, Literal, Dict, Any, Iterator, List, Annotated, AsyncIterator
from langgraph.graph import StateGraph, END
import time
import re
import sys 
import asyncio # Added for asyncio.sleep
import requests # Added for requests.exceptions.RequestException in _retry_with_backoff
from datetime import datetime
from dateutil import parser as date_parser 

print(f"langgraph_core.py: __name__ = {__name__}, __package__ = {__package__}") 
from .weather import get_weather_info
from .stocks import get_stock_price


class AgentState(TypedDict):
    """State management for the AI Agent workflow"""
    user_input: str
    result: Optional[str]
    tool_used: Optional[str]
    error: Optional[str]
    metadata: Optional[Dict[str, Any]]

class WeatherStockAgent:
    """
    Complete LangGraph-based AI Agent for Weather and Stock Information
    Features: Streaming, Memory, Retry Logic, Enhanced routing, Error handling
    """
    
    def __init__(self):
        self.graph = self._build_graph()
        self.streaming_enabled = True 
        
        self.conversation_memory = {
            'last_city': None,
            'last_stock_query': None, 
            'last_stock_date_query': None, 
            'last_query_type': None,
            'query_history': []
        }
        
        self.stock_symbols_cache = { 
            'google': 'GOOGL', 'alphabet': 'GOOGL',
            'amazon': 'AMZN', 'apple': 'AAPL',
            'microsoft': 'MSFT', 'tesla': 'TSLA',
            'meta': 'META', 'facebook': 'META',
            'netflix': 'NFLX', 'nvidia': 'NVDA',
        }
    
    stock_context_keywords = ['that stock', 'same company', 'it'] 
    
    def _build_graph(self) -> StateGraph:
        """Build and configure the LangGraph workflow"""
        workflow = StateGraph(AgentState)
        
        workflow.add_node("router", self._router_node)
        workflow.add_node("weather_tool_node", self._weather_tool_node_executor) 
        workflow.add_node("stock_tool_node", self._stock_tool_node_executor)   
        workflow.add_node("final_result_node", self._final_result_node) 
        
        workflow.set_entry_point("router")
        
        workflow.add_conditional_edges(
            "router",
            self._route_decision,
            {
                "weather": "weather_tool_node",
                "stock": "stock_tool_node",
                "unknown": "final_result_node" 
            }
        )
        
        workflow.add_edge("weather_tool_node", "final_result_node")
        workflow.add_edge("stock_tool_node", "final_result_node")
        workflow.add_edge("final_result_node", END) 
        
        return workflow.compile()
    
    def _console_log_step(self, event_type: str, data: Dict[str, Any]) -> None:
        """Helper to print progress steps to the console for backend debugging."""
        if self.streaming_enabled: # Check if streaming (and thus console logging) is enabled
            timestamp = datetime.now().strftime("%H:%M:%S")
            message = data.get("message", str(data)) # Default to string representation of data if no message key
            formatted_output = f"[{timestamp}] {event_type}: {message}\n"
            print(formatted_output.strip()) # Use print for direct console output
    
    def _preprocess_input_with_memory(self, user_input: str) -> str: 
        """Handle contextual references using memory"""
        processed_input = user_input.lower()
        original_input = user_input
        
        city_context_keywords = ['there', 'same place', 'that city', 'that location']
        if any(word in processed_input for word in city_context_keywords):
            if self.conversation_memory['last_city']:
                replacement_city = self.conversation_memory['last_city']
                for keyword in city_context_keywords:
                    processed_input = processed_input.replace(keyword, replacement_city)
                self._console_log_step("MEMORY_UPDATE", {"message": f"Using remembered city: {replacement_city}"})
        
        if any(word in processed_input for word in self.stock_context_keywords): # Use self.stock_context_keywords
            if self.conversation_memory['last_stock_query']: 
                replacement_stock = self.conversation_memory['last_stock_query']
                if 'it' in processed_input.split() and self.conversation_memory['last_query_type'] == 'stock':
                    processed_input = processed_input.replace('it', replacement_stock)
                else: 
                    for keyword in self.stock_context_keywords: # Use self.stock_context_keywords
                        if keyword != 'it': 
                            processed_input = processed_input.replace(keyword, replacement_stock)
                self._console_log_step("MEMORY_UPDATE", {"message": f"Using remembered stock query: {replacement_stock}"})
        
        self.conversation_memory['query_history'].append(original_input)
        if len(self.conversation_memory['query_history']) > 5: 
            self.conversation_memory['query_history'] = self.conversation_memory['query_history'][-5:]
        
        return processed_input if processed_input != user_input.lower() else user_input

    def _save_to_memory(self, tool_used: str, entity: Optional[str], date_entity: Optional[str] = None):
        """Save context to memory. Entity is city name or stock query."""
        if entity: 
            if tool_used == 'weather':
                self.conversation_memory['last_city'] = entity.title()
            elif tool_used == 'stock':
                self.conversation_memory['last_stock_query'] = entity 
                self.conversation_memory['last_stock_date_query'] = date_entity 
        
        self.conversation_memory['last_query_type'] = tool_used
    
    def _retry_with_backoff(self, func, *args, max_retries: int = 2, relevant_exceptions=(ValueError, requests.exceptions.RequestException)) -> Any:
        last_exception = None
        for attempt in range(max_retries):
            try:
                return func(*args) 
            except relevant_exceptions as e: 
                last_exception = e
                self._console_log_step("RETRY_ATTEMPT", {"message": f"Attempt {attempt + 1} for {func.__name__} failed. Error: {str(e)}"})
                if attempt == max_retries - 1:
                    self._console_log_step("RETRY_FAILURE", {"message": f"All {max_retries} attempts for {func.__name__} failed."})
                    raise last_exception 
                
                wait_time = 2 ** attempt  
                self._console_log_step("RETRY_WAIT", {"message": f"Retrying in {wait_time}s..."})
                time.sleep(wait_time)
            except Exception as e: 
                self._console_log_step("UNEXPECTED_ERROR", {"message": f"Unexpected error in {func.__name__}: {str(e)}"})
                raise 
        return None 
    
    def _router_node(self, state: AgentState) -> AgentState: 
        self._console_log_step("ROUTER_START", {"message": f"Analyzing request: '{state['user_input']}'"})
        
        user_input = state['user_input'].lower()
        
        weather_keywords = [
            'weather', 'temperature', 'temp', 'rain', 'sunny', 'cloudy',
            'forecast', 'climate', 'humidity', 'wind', 'degrees', 'celsius',
            'fahrenheit', 'hot', 'cold', 'storm', 'snow', 'today', 'tomorrow', 'yesterday'
        ]
        stock_keywords = [
            'stock', 'price', 'share', 'trading', 'market', 'nasdaq',
            'nyse', 'equity', 'ticker', 'investment', 'portfolio',
            'dividend', 'earnings', 'valuation', 'shares', 'stock price', 'share price',
            'last week', 'previous week' # Added for stock context
        ]
        company_keywords = list(self.stock_symbols_cache.keys())
        
        weather_score = sum(1 for keyword in weather_keywords if keyword in user_input)
        stock_score = sum(1 for keyword in stock_keywords if keyword in user_input)
        company_score = sum(1 for company in company_keywords if company in user_input)
        
        total_stock_score = stock_score + company_score
        
        self._console_log_step("ROUTER_ANALYSIS", {"message": f"Scores - Weather: {weather_score}, Stock: {total_stock_score}"})
        
        state['metadata'] = {
            'weather_score': weather_score,
            'stock_score': stock_score, 
            'company_score': company_score,
            'total_stock_score': total_stock_score, 
            'analysis_time': datetime.now().isoformat()
        }
        time.sleep(0.3)
        return state 
    
    def _route_decision(self, state: AgentState) -> Literal["weather", "stock", "unknown"]: 
        metadata = state.get('metadata', {})
        weather_score = metadata.get('weather_score', 0)
        total_stock_score = metadata.get('total_stock_score', 0) 
        user_input_lower = state['user_input'].lower()
        
        decision = "unknown"
        if weather_score > total_stock_score and weather_score > 0:
            decision = "weather"
        elif total_stock_score > weather_score and total_stock_score > 0:
            decision = "stock"
        elif weather_score > 0 and total_stock_score > 0 and weather_score == total_stock_score:
            # Tie-breaking: If scores are tied and both domains have keywords
            has_weather_keyword = 'weather' in user_input_lower
            has_core_stock_keyword = any(k in user_input_lower for k in ['stock', 'price', 'share', 'company'])

            if has_weather_keyword and not has_core_stock_keyword:
                 decision = "weather"
            elif has_core_stock_keyword:
                decision = "stock"
            else:
                 # Ambiguous tie, e.g., "yesterday's data".
                 # It's better to admit we don't know than to guess wrong.
                 decision = "unknown"
        
        self._console_log_step("ROUTE_DECISION", {"message": f"Decision: {decision} (W: {weather_score}, S_Total: {total_stock_score})"})
        return decision
    
    def _weather_tool_node_executor(self, state: AgentState) -> AgentState: 
        self._console_log_step("WEATHER_TOOL_START", {"message": "Initializing..."})
        time.sleep(0.2)
        
        try:
            city = self._extract_city_from_input(state['user_input'])
            if not city:
                city = self.conversation_memory.get('last_city') or "Hyderabad" 
                self._console_log_step("WEATHER_TOOL_INFO", {"message": f"Using city: {city} (from memory or default)"})
            else:
                self._console_log_step("WEATHER_TOOL_INFO", {"message": f"City identified: {city}"})
            
            day_param = "today" 
            extracted_date_str = self._extract_date_from_input(state['user_input'])

            if extracted_date_str:
                day_param = extracted_date_str 
            elif self._is_yesterday_request(state['user_input']): 
                day_param = "yesterday"
            elif self._is_tomorrow_request(state['user_input']): 
                day_param = "tomorrow"
            
            self._console_log_step("WEATHER_TOOL_INFO", {"message": f"Fetching {day_param}'s weather for {city}..."})
            
            result = self._retry_with_backoff(get_weather_info, city, day_param)
            
            if "failed" in result.lower() or "error" in result.lower() or "unavailable" in result.lower():
                self._console_log_step("WEATHER_TOOL_ERROR", {"message": f"Tool reported: {result}"})
                state['result'] = f"Sorry, I couldn't fetch the weather information for '{city}'. The tool said: {result}"
            else:
                self._console_log_step("WEATHER_TOOL_SUCCESS", {"message": "Data processed!"})
                state['result'] = result
            
            state['tool_used'] = 'weather'
            self._save_to_memory('weather', city) 
            
        except Exception as e:
            error_msg = f"Error in weather tool: {str(e)}"
            self._console_log_step("WEATHER_TOOL_ERROR", {"message": f"Final error: {error_msg}"})
            state['result'] = error_msg
            state['error'] = str(e)
            state['tool_used'] = 'weather'
        
        return state 
    
    def _stock_tool_node_executor(self, state: AgentState) -> AgentState: 
        self._console_log_step("STOCK_TOOL_START", {"message": "Initializing..."})
        time.sleep(0.2)
        
        try:
            stock_query, date_str = self._extract_stock_query_and_date(state['user_input'])
            
            if not stock_query:
                stock_query = self.conversation_memory.get('last_stock_query')
                if stock_query:
                    self._console_log_step("STOCK_TOOL_INFO", {"message": f"Using remembered stock query: {stock_query}"})
                    if not date_str : # If no new date in current query, check memory
                        # Prioritize newly parsed date_str. If user says "that stock yesterday",
                        # date_str will be "yesterday". If "that stock", date_str is None.
                        # Only use remembered date if current query has NO date info.
                        if not self._extract_date_from_input(state['user_input']) and \
                           not self._is_yesterday_request(state['user_input']) and \
                           not self._is_last_week_request(state['user_input']):
                           date_str = self.conversation_memory.get('last_stock_date_query')
                           if date_str:
                               self._console_log_step("STOCK_TOOL_INFO", {"message": f"Using remembered date: {date_str}"})
            
            if not stock_query:
                state['result'] = "Sorry, I couldn't identify which stock you're asking about. Please specify a company name like Google, Amazon, Apple, etc."
                state['tool_used'] = 'stock'
                self._console_log_step("STOCK_TOOL_ERROR", {"message": "Could not identify stock query."})
                return state 
            
            log_message = f"Stock query identified: {stock_query}"
            if date_str:
                log_message += f" for date/period: {date_str}"
            self._console_log_step("STOCK_TOOL_INFO", {"message": log_message})
            
            self._console_log_step("STOCK_TOOL_INFO", {"message": f"Fetching stock data for {stock_query}..."})
            time.sleep(0.2) 
            
            tool_response = self._retry_with_backoff(get_stock_price, stock_query, date_str) 
            self._console_log_step("STOCK_TOOL_INFO", {"message": "Processing stock data..."})
            time.sleep(0.1) 
            
            if tool_response.get("status") == "error":
                error_message = tool_response.get('message', 'An unknown error occurred in the stock tool.')
                self._console_log_step("STOCK_TOOL_ERROR", {"message": f"Stock tool reported: {error_message}"})
                state['result'] = f"Sorry, I couldn't fetch the stock information for '{stock_query}'. The tool said: {error_message}"
            else:
                self._console_log_step("STOCK_TOOL_SUCCESS", {"message": "Stock data processed successfully!"})
                state['result'] = tool_response.get('content', 'No content received from the stock tool.')
            
            state['tool_used'] = 'stock'
            self._save_to_memory('stock', stock_query, date_str) 
            
        except Exception as e:
            error_msg = f"Error in stock tool: {str(e)}"
            self._console_log_step("STOCK_TOOL_ERROR", {"message": f"Final error: {error_msg}"})
            state['result'] = error_msg
            state['error'] = str(e)
            state['tool_used'] = 'stock'
        
        return state 
    
    def _final_result_node(self, state: AgentState) -> AgentState: 
        if not state.get('result'):
            state['result'] = "I'm sorry, I couldn't understand your request. I can help you with:\n" \
                             "• Weather information (e.g., 'weather in Chennai', 'weather tomorrow', 'weather yesterday')\n" \
                             "• Stock prices (e.g., 'price of Google stock', 'Amazon share price on June 5', 'Apple stock last week')"
        
        self._console_log_step("FINALIZING", {"message": "Finalizing response..."})
        time.sleep(0.1) 
        self._console_log_step("REQUEST_COMPLETE", {"message": "✅ Request completed successfully!"})
        
        return state
    
    def _extract_city_from_input(self, user_input: str) -> Optional[str]:
        user_input_lower = user_input.lower()
        
        indian_cities = [
            'mumbai', 'delhi', 'bangalore', 'bengaluru', 'chennai', 'hyderabad',
            'pune', 'kolkata', 'ahmedabad', 'jaipur', 'surat', 'lucknow',
            'kanpur', 'nagpur', 'indore', 'thane', 'bhopal', 'visakhapatnam', 'vizag',
            'patna', 'vadodara', 'ghaziabad', 'ludhiana', 'agra', 'nashik'
        ]
        
        international_cities = [
            'london', 'paris', 'tokyo', 'new york', 'los angeles', 'chicago',
            'toronto', 'sydney', 'melbourne', 'singapore', 'dubai', 'bangkok'
        ]
        
        all_cities = indian_cities + international_cities
        
        patterns = [
            r'weather in (\w+(?:\s+\w+)?)',
            r'temperature in (\w+(?:\s+\w+)?)',
            r'forecast for (\w+(?:\s+\w+)?)',
            r'weather at (\w+(?:\s+\w+)?)',
            r'weather for (\w+(?:\s+\w+)?)',
            r'in (\w+(?:\s+\w+)?)(?=\s+(?:today|tomorrow|yesterday|weather|temperature|forecast))', 
            r'(\w+(?:\s+\w+)?)\s+weather' 
        ]
        
        for pattern in patterns:
            match = re.search(pattern, user_input_lower)
            if match:
                potential_city = match.group(1).strip()

                # Keywords that should not be part of a city name
                # "week" is added here to handle "last week" specifically
                day_and_period_keywords = ["today", "tomorrow", "tmrw", "tom", "toady", "tody", "tomorow", "yesterday", "yestarday", "ystday", "week"]

                if potential_city.lower() in day_and_period_keywords:
                    continue

                # If "last week" is in the input, ensure "last" isn't part of the city
                if "last week" in user_input_lower and potential_city.lower().endswith(" last"):
                    potential_city = potential_city.lower().replace(" last", "").strip()

                for day_keyword in day_and_period_keywords:
                    if potential_city.lower().endswith(f" {day_keyword}"):
                        potential_city = potential_city.lower().replace(f" {day_keyword}", "").strip()

                if "new york" in potential_city: return "New York"
                if "los angeles" in potential_city: return "Los Angeles"
                if potential_city in all_cities:
                    return potential_city.title()
                if len(potential_city.split()) <= 3 and potential_city: 
                    return potential_city.title() 
        
        for city in all_cities: 
            day_keywords_and_misspellings_for_direct_match = ["today", "tomorrow", "toady", "yesterday"] 
            if city.lower() in day_keywords_and_misspellings_for_direct_match:
                continue
            if re.search(r'\b' + re.escape(city) + r'\b', user_input_lower):

                if "new york" in user_input_lower: return "New York" 
                if "los angeles" in user_input_lower: return "Los Angeles"
                return city.title()
        
        return None
    
    def _is_tomorrow_request(self, user_input: str) -> bool:
        tomorrow_keywords = ['tomorrow', 'next day', 'tmrw', 'tom'] 
        # Removed 'forecast' as it's too ambiguous for just 'tomorrow'
        return any(keyword in user_input.lower() for keyword in tomorrow_keywords)

    def _is_yesterday_request(self, user_input: str) -> bool:
        yesterday_keywords = ['yesterday', 'yestarday', 'prev day', 'previous day', 'ystday'] 
        return any(keyword in user_input.lower() for keyword in yesterday_keywords)
    
    def _is_last_week_request(self, user_input: str) -> bool:
        """Check if user is asking for last week's data."""
        last_week_keywords = ['last week', 'previous week']
        return any(keyword in user_input.lower() for keyword in last_week_keywords)

    def _extract_date_from_input(self, user_input: str) -> Optional[str]:
        date_patterns = [
            # Modified to make comma optional before year: Month Day Year or Month Day, Year
            r'\b((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?(?:(?:,\s*|\s+)\d{2,4})?)\b',
            r'\b(\d{1,2}(?:st|nd|rd|th)?\s+(?:of\s+)?(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)(?:\s+\d{2,4})?)\b',
            r'\b(\d{4}-\d{1,2}-\d{1,2})\b',
            r'\b(\d{1,2}/\d{1,2}/\d{2,4})\b',
            r'\b(\d{1,2}\.\d{1,2}\.\d{2,4})\b',
        ]
        user_input_lower = user_input.lower()
        for pattern in date_patterns:
            match = re.search(pattern, user_input_lower, re.IGNORECASE)
            if match:
                date_str = match.group(1).strip()
                try:
                    date_parser.parse(date_str)
                    return date_str 
                except (ValueError, OverflowError):
                    continue 
        yesterday_keywords = ['yesterday', 'yestarday', 'prev day', 'previous day', 'ystday'] 
        if any(keyword in user_input.lower() for keyword in yesterday_keywords):
            return "yesterday"
        tommorow_keywords = ['tomorrow', 'tmrw', 'next day', 'tom']
        if any(keyword in user_input.lower() for keyword in tommorow_keywords):
            return "tomorrow"
        lastweek_keywords = ['previous week', 'last week']
        if any(keyword in user_input.lower() for keyword in lastweek_keywords):
            return "last_week"
        return None

    def _extract_stock_query_and_date(self, user_input: str) -> tuple[Optional[str], Optional[str]]:
        """Extracts stock query and an optional date string (specific, "yesterday", or "last_week") from user input."""
        input_for_stock_extraction = user_input
        date_str: Optional[str] = None

        # Priority: 1. Specific Date, 2. Yesterday, 3. Last Week
        specific_date_match = self._extract_date_from_input(user_input)
        if specific_date_match:
            date_str = specific_date_match
            # Remove the specific date phrase to avoid it being part of the stock query
            # This logic attempts to remove the date phrase along with common prepositions.
            for pattern in [ 
                r'\b((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?(?:,\s*\d{2,4})?)\b',
                r'\b(\d{1,2}(?:st|nd|rd|th)?\s+(?:of\s+)?(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)(?:\s+\d{2,4})?)\b',
                r'\b(\d{4}-\d{1,2}-\d{1,2})\b', r'\b(\d{1,2}/\d{1,2}/\d{2,4})\b', r'\b(\d{1,2}\.\d{1,2}\.\d{2,4})\b'
            ]:
                match_obj = re.search(pattern, input_for_stock_extraction, re.IGNORECASE)
                if match_obj and match_obj.group(1).lower() == date_str.lower():
                    phrase_to_remove_match = re.search(r'\b(?:on|for|at)\s+' + re.escape(match_obj.group(1)) + r'\b', input_for_stock_extraction, re.IGNORECASE)
                    if phrase_to_remove_match:
                        input_for_stock_extraction = input_for_stock_extraction.replace(phrase_to_remove_match.group(0), "", 1)
                    else:
                        input_for_stock_extraction = input_for_stock_extraction.replace(match_obj.group(1), "", 1)
                    input_for_stock_extraction = input_for_stock_extraction.strip().strip(',').strip()
                    break
        
        elif self._is_yesterday_request(user_input): 
            date_str = "yesterday" 
            yesterday_keywords_for_removal = ['previous day', 'prev day', 'yestarday', 'ystday', 'yesterday'] 
            
            original_case_input_for_stock_extraction = input_for_stock_extraction 
            temp_input_lower = input_for_stock_extraction.lower()
            
            for keyword in yesterday_keywords_for_removal:
                prefixed_keyword_pattern = r'\b(?:on|for|as of)\s+' + re.escape(keyword) + r'\b'
                match_obj = re.search(prefixed_keyword_pattern, temp_input_lower)
                if match_obj:
                    start, end = match_obj.span()
                    input_for_stock_extraction = original_case_input_for_stock_extraction[:start] + original_case_input_for_stock_extraction[end:]
                    break 
                keyword_pattern = r'\b' + re.escape(keyword) + r'\b'
                match_obj = re.search(keyword_pattern, temp_input_lower)
                if match_obj:
                    start, end = match_obj.span()
                    input_for_stock_extraction = original_case_input_for_stock_extraction[:start] + original_case_input_for_stock_extraction[end:]
                    break
            input_for_stock_extraction = input_for_stock_extraction.strip().strip(',').strip()

        elif self._is_last_week_request(user_input):
            date_str = "last_week" # Special identifier for the stock tool
            # Remove "last week" or "previous week" from the input string
            input_for_stock_extraction = re.sub(r'\b(last\s*week|previous\s*week)\b', '', input_for_stock_extraction, flags=re.IGNORECASE).strip().strip(',').strip()

        stock_query = self._extract_stock_query_from_input(input_for_stock_extraction.strip())

        if not stock_query and self.conversation_memory.get('last_stock_query'):
            if any(context_word in user_input.lower() for context_word in self.stock_context_keywords): 
                 stock_query = self.conversation_memory.get('last_stock_query')
                 self._console_log_step("STOCK_TOOL_MEMORY", {"message": f"Using remembered stock query due to context: {stock_query}"})

        return stock_query, date_str

    def _extract_stock_query_from_input(self, user_input: str) -> Optional[str]: 
        user_input_lower = user_input.lower()
        
        for company, symbol in self.stock_symbols_cache.items(): 
            if company in user_input_lower:
                return symbol 
        
        patterns = [
            r'(?:stock|price|shares?)\s+(?:of|for|in)?\s*([a-zA-Z0-9\s\.\-]+)', 
            r'([a-zA-Z0-9\s\.\-]+)\s+(?:stock|price|shares?)'
        ]
        for pattern in patterns:
            match = re.search(pattern, user_input_lower)
            if match:
                query = match.group(1).strip()
                # Further clean up common stock-related terms if they are at the end
                for term in [" stock", " price", " share", " shares", " stock price", " share price"]:
                    if query.endswith(term):
                        query = query[:-len(term)].strip()
                if query: return query.title() # Title case for better lookup if it's a name
        
        # Attempt to find a ticker symbol (e.g., AAPL, MSFT.MX)
        # This regex looks for 1-5 uppercase letters, optionally followed by a dot and 1-3 more uppercase letters.
        symbol_match = re.search(r'\b([A-Z]{1,5}(?:\.[A-Z]{1,3})?)\b', user_input) # Note: user_input, not user_input_lower
        if symbol_match:
            return symbol_match.group(1)
            
        # Fallback: if no clear pattern or symbol, return the cleaned input if it's short
        # This is a bit of a guess and might need refinement.
        # Avoid returning very long strings as stock queries.
        if len(user_input.split()) <= 4 and user_input: # If it's a few words
            # Remove common phrases that are not part of the stock name
            cleaned_input = user_input_lower
            phrases_to_remove = ["price of", "stock price of", "shares of", "stock of", "how is", "what is", "what's", "give me the"]
            for phrase in phrases_to_remove:
                cleaned_input = cleaned_input.replace(phrase, "").strip()
            if cleaned_input:
                return cleaned_input.title()

        return None
    
    def _get_company_name(self, symbol: str) -> str:
        symbol_to_company = {v: k for k, v in self.stock_symbols_cache.items()} 
        return symbol_to_company.get(symbol.upper(), symbol).title() 
    
    def _format_weather_response(self, weather_data: Dict[str, Any], city: str) -> str:
        temp = weather_data.get('temperature', 'N/A')
        day = weather_data.get('day', 'N/A') 
        description = weather_data.get('description', 'N/A')
        humidity = weather_data.get('humidity', 'N/A')
        feels_like = weather_data.get('feels_like', 'N/A') 
        wind_speed = weather_data.get('wind_speed', 'N/A') 
        
        return (f"🌤️ Weather for {day} in {city.title()}:\n" 
               f"   🌡️ Temperature: {temp} (feels like {feels_like})\n" 
               f"   ☁️ Conditions: {description.title() if description != 'N/A' else 'N/A'}\n" 
               f"   💧 Humidity: {humidity}\n"
               f"   💨 Wind: {wind_speed}") 
    
    def _format_forecast_response(self, forecast_data: Dict[str, Any], city: str) -> str:
        if forecast_data: 
            day = forecast_data.get('day', 'Tomorrow')
            temp = forecast_data.get('temperature', 'N/A')
            description = forecast_data.get('description', 'N/A')
            return f"🌤️ {day}'s Weather Forecast for {city.title()}:\n   🌡️ Temp: {temp}, ☁️ Conditions: {description.title()}"
        else:
            return f"🌤️ Weather forecast for {city.title()} is currently unavailable."
    
    def _format_stock_response(self, stock_data_str: str, query: str) -> str: 
        if "failed" in stock_data_str.lower() or "error" in stock_data_str.lower() or "unavailable" in stock_data_str.lower():
            return stock_data_str
        return f"📈 {stock_data_str}" 
    
    async def run_with_streaming(self, user_input: str) -> AsyncIterator[str]: # Changed to async generator
        self.streaming_enabled = True # This flag is mostly for _console_log_step now
        original_input_for_log = user_input
        
        processed_input = self._preprocess_input_with_memory(user_input)
        
        yield f"[{datetime.now().strftime('%H:%M:%S')}] START: Processing '{original_input_for_log}'...\n"
        if processed_input.lower() != original_input_for_log.lower(): # Compare lowercased versions
             yield f"[{datetime.now().strftime('%H:%M:%S')}] MEMORY_INFO: Interpreted as '{processed_input}'.\n"

        yield f"[{datetime.now().strftime('%H:%M:%S')}] PROCESSING: Thinking...\n"
        
        final_state = None
        try:
            initial_state = AgentState(
                user_input=processed_input, 
                result=None, tool_used=None, error=None, metadata=None
            )
            # Use ainvoke for asynchronous graph execution if graph nodes are async
            # If nodes are synchronous, ainvoke runs them in a thread pool.
            final_state = await self.graph.ainvoke(initial_state)
        except Exception as e:
            self._console_log_step("FATAL_ERROR", {"message": str(e)}) # Keep console log
            error_message = f"An internal error occurred while processing your request: {str(e)}"
            # Stream the error message word by word
            words = error_message.split(' ')
            for i, word in enumerate(words):
                yield word
                if i < len(words) - 1:
                    yield " "
                await asyncio.sleep(0.02) # Simulate delay
            yield "\n"
            return
        
        final_result_message = final_state.get('result', "I'm sorry, I could not retrieve a result.")
        
        # Stream the actual final_result_message word by word
        if final_result_message:
            words = final_result_message.split(' ')
            for i, word in enumerate(words):
                yield word
                if i < len(words) - 1: # Add space if not the last word
                    yield " "
                await asyncio.sleep(0.05) # Delay between words for streaming effect
            yield "\n" # Ensure a newline at the end of the streamed message
    
    def run(self, user_input: str) -> str:
        self.streaming_enabled = True 
        original_input_for_log = user_input
        processed_input = self._preprocess_input_with_memory(user_input) 
        
        print(f"\n🚀 Processing: '{original_input_for_log}'")
        if processed_input != original_input_for_log.lower():
            print(f"💭 Interpreted as: '{processed_input}'")
        print("=" * 50)
        
        initial_state = AgentState(user_input=processed_input, result=None, tool_used=None, error=None, metadata=None)
        final_state = self.graph.invoke(initial_state) 
        
        print(f"\n🎯 Tool used: {final_state.get('tool_used', 'N/A')}")
        print(f"Memory (at end): {self.conversation_memory}")
        print("=" * 50)
        return final_state.get('result', "No result obtained.")

    def run_silent(self, user_input: str) -> str:
        self.streaming_enabled = False 
        processed_input = self._preprocess_input_with_memory(user_input) 
        initial_state = AgentState(user_input=processed_input, result=None, tool_used=None, error=None, metadata=None)
        final_state = self.graph.invoke(initial_state)
        return final_state.get('result', "No result obtained.")

    def get_memory_status(self) -> Dict[str, Any]:
        return {"conversation_memory": self.conversation_memory.copy()}

    def clear_memory(self) -> None: 
        self.conversation_memory = {
            'last_city': None, 'last_stock_query': None, 'last_stock_date_query': None,
            'last_query_type': None, 'query_history': [] 
        }
        print("🧹 Memory cleared!")

agent_instance = WeatherStockAgent() 

if __name__ == "__main__": 
    args = sys.argv
    # Demos removed for brevity, assuming they are not the primary focus for this fix.
    # You can add them back if needed.
    print("🤖 Weather Stock Agent (Enhanced Interactive Mode - Console Streaming)")
    print("=" * 60)
    print("Ask about weather (e.g., 'weather in London') or stocks (e.g., 'Google stock price', 'Apple stock on June 5', 'MSFT stock last week').")
    print("Type 'memory', 'clear', or 'quit'.\n")
    while True:
        try:
            user_input_cli = input("You: ").strip()
            if user_input_cli.lower() in ['quit', 'exit', 'q']: print("👋 Goodbye!"); break
            elif user_input_cli.lower() == 'memory': print(f"💭 Memory: {agent_instance.get_memory_status()}"); continue
            elif user_input_cli.lower() == 'clear': agent_instance.clear_memory(); continue
            elif user_input_cli:
                response_cli = agent_instance.run(user_input_cli) 
                print(f"Agent: {response_cli}\n")
        except KeyboardInterrupt: print("\n👋 Goodbye!"); break
        except Exception as e_cli: print(f"❌ CLI Error: {str(e_cli)}\n")