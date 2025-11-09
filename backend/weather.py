import requests
from typing import Dict, Any, Optional
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta # Needed for tomorrow's forecast logic
from dateutil import parser as date_parser # For parsing general date strings
import re # Needed for date parsing in CLI example

load_dotenv() # Ensures .env variables are loaded when this module is imported

class WeatherTool:
    """Weather information fetcher with day selection using Visual Crossing"""

    def __init__(self):
        self.api_key: Optional[str] = os.getenv("VISUALCROSSING_API_KEY")
        if not self.api_key:
            raise ValueError("VISUALCROSSING_API_KEY environment variable not set. Weather tool cannot function.")
        # Visual Crossing base URL for timeline service
        self.base_url = "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline"

    def get_current_weather(self, city: str) -> Dict[str, Any]:
        """Get current weather for a city using Visual Crossing"""
        if not self.api_key:
            raise ValueError("API key for Visual Crossing is not configured.")
        try:
            response = requests.get(
                f"{self.base_url}/{city}/today",
                params={
                    "key": self.api_key,
                    "unitGroup": "metric", # Use metric units (Celsius, km/h, etc.)
                    "include": "current", # Request current conditions
                    "contentType": "json"
                },
                timeout=10
            )
            response.raise_for_status() # Raises an HTTPError for bad responses (4XX or 5XX)
            data = response.json()

            if not data.get('currentConditions'):
                raise ValueError("Current conditions data is missing in API response.")

            current_data = data['currentConditions'] # Visual Crossing nests current data here
            # Use resolved address if available, take the first part (city name)
            city_name = data.get('resolvedAddress', city).split(',')[0]

            return {
                "city": city_name,
                "temperature": f"{current_data['temp']}°C",
                "day": "Today", # Add day information
                "feels_like": f"{current_data['feelslike']}°C",
                "description": current_data['conditions'].capitalize(),
                "humidity": f"{current_data['humidity']}%",
                # Visual Crossing windspeed is often in km/h with metric
                "wind_speed": f"{current_data.get('windspeed', 0)} km/h"
            }
        except requests.exceptions.RequestException as e:
            raise ValueError(f"Network error or API issue fetching weather for {city}: {str(e)}")
        except (KeyError, TypeError, IndexError) as e:
            raise ValueError(f"Unexpected API response format for {city}: {str(e)}")
        except Exception as e:
            raise ValueError(f"Could not retrieve weather data for {city}: {str(e)}")


    def _get_tomorrows_weather(self, city: str) -> Dict[str, Any]:
        """Get tomorrow's weather forecast using Visual Crossing"""
        if not self.api_key:
            raise ValueError("API key for Visual Crossing is not configured.")
        try:
            response = requests.get(
                f"{self.base_url}/{city}/tomorrow",
                params={
                    "key": self.api_key,
                    "unitGroup": "metric", # Use metric units
                    "include": "days", # Request daily forecast data
                    "contentType": "json"
                },
                timeout=10
            )
            response.raise_for_status()
            data = response.json()

            if not data.get('days') or not data['days'][0]:
                raise ValueError("Forecast data for tomorrow is missing in API response.")

            forecast_data = data['days'][0] # Tomorrow's data should be the first in the 'days' array
            city_name = data.get('resolvedAddress', city).split(',')[0]

            return {
                "city": city_name,
                "day": "Tomorrow", # Add day information
                "temperature": f"{forecast_data['temp']}°C", # Daily average temp
                "feels_like": f"{forecast_data['feelslike']}°C",
                "description": forecast_data['conditions'].capitalize(),
                "humidity": f"{forecast_data['humidity']}%",
                "wind_speed": f"{forecast_data.get('windspeed', 0)} km/h"
            }
        except requests.exceptions.RequestException as e:
            raise ValueError(f"Network error or API issue fetching weather for {city} (tomorrow): {str(e)}")
        except (KeyError, TypeError, IndexError) as e:
            raise ValueError(f"Unexpected API response format for {city} (tomorrow): {str(e)}")
        except Exception as e:
            raise ValueError(f"Could not retrieve weather forecast for {city} (tomorrow): {str(e)}")

    def _get_last_weeks_weather_summary(self, city: str) -> Dict[str, Any]:
        """Get a summary of weather for the last 7 days (previous to today) using Visual Crossing."""
        if not self.api_key:
            raise ValueError("API key for Visual Crossing is not configured.")
        try:
            today = datetime.now().date()
            end_date_obj = today - timedelta(days=1) # Yesterday is the last day of the period
            start_date_obj = end_date_obj - timedelta(days=6) # 7 days in total

            start_date_str = start_date_obj.strftime('%Y-%m-%d')
            end_date_str = end_date_obj.strftime('%Y-%m-%d')

            response = requests.get(
                f"{self.base_url}/{city}/{start_date_str}/{end_date_str}",
                params={
                    "key": self.api_key,
                    "unitGroup": "metric",
                    "include": "days", # Request daily data for the range
                    "contentType": "json"
                },
                timeout=20 # Slightly longer for a date range
            )
            response.raise_for_status()
            data = response.json()

            if not data.get('days') or not data['days']:
                raise ValueError(f"Weather data not found for {city} for the period {start_date_str} to {end_date_str}")

            daily_data = data['days']
            city_name = data.get('resolvedAddress', city).split(',')[0]

            avg_temp = sum(day_data['temp'] for day_data in daily_data) / len(daily_data)
            avg_feelslike = sum(day_data['feelslike'] for day_data in daily_data) / len(daily_data)
            avg_humidity = sum(day_data['humidity'] for day_data in daily_data) / len(daily_data)
            avg_windspeed = sum(day_data.get('windspeed', 0) for day_data in daily_data) / len(daily_data)
            
            # For conditions, we can take the most frequent or just a general summary
            # For simplicity, let's take conditions from the middle day of the period
            conditions_summary = daily_data[len(daily_data) // 2]['conditions'].capitalize()

            return {
                "city": city_name,
                "day": f"Last Week ({start_date_str} to {end_date_str})",
                "temperature": f"{avg_temp:.1f}°C (average)",
                "feels_like": f"{avg_feelslike:.1f}°C (average feels like)",
                "description": f"Varied, e.g., {conditions_summary}", # More sophisticated summary could be added
                "humidity": f"{avg_humidity:.1f}% (average)",
                "wind_speed": f"{avg_windspeed:.1f} km/h (average)"
            }
        except requests.exceptions.RequestException as e:
            raise ValueError(f"Network error or API issue fetching weather for {city} (last week): {str(e)}")
        except (KeyError, TypeError, IndexError, ZeroDivisionError) as e:
            raise ValueError(f"Unexpected API response format or no data for {city} (last week): {str(e)}")
        except Exception as e:
            raise ValueError(f"Could not retrieve weather summary for {city} (last week): {str(e)}")

    def _get_historical_weather(self, city: str, date_obj: datetime.date) -> Dict[str, Any]:
        """Get historical weather for a city on a specific date using Visual Crossing."""
        if not self.api_key:
            raise ValueError("API key for Visual Crossing is not configured.")
        try:
            today_date = datetime.now().date()
            # Simple check to prevent querying future dates for historical data
            if date_obj > today_date:
                 raise ValueError(f"Cannot fetch historical weather for a future date: {date_obj.strftime('%Y-%m-%d')}.")
            # If the date is today, it's not historical in the same way
            if date_obj == today_date:
                 raise ValueError(f"For today's weather, please ask for 'today'. Historical data is for past dates.")


            formatted_date = date_obj.strftime('%Y-%m-%d')

            response = requests.get(
                # Visual Crossing timeline API uses start/end date for range, use same date for single day
                f"{self.base_url}/{city}/{formatted_date}/{formatted_date}",
                params={
                    "key": self.api_key,
                    "unitGroup": "metric", # Use metric units
                    "include": "days", # Request daily historical data
                    "contentType": "json"
                },
                timeout=15 # Slightly longer timeout for potentially more complex API call
            )
            response.raise_for_status()
            data = response.json()

            if not data.get('days') or not data['days'][0]:
                raise ValueError(f"Historical weather data not found for {city} on {formatted_date}")

            hist_data = data['days'][0] # Historical data for the day is in the 'days' array
            city_name = data.get('resolvedAddress', city).split(',')[0]

            return {
                "city": city_name,
                "day": date_obj.strftime('%B %d, %Y'), # Format the date nicely
                "temperature": f"{hist_data['temp']}°C",
                "feels_like": f"{hist_data['feelslike']}°C",
                "description": hist_data['conditions'].capitalize(),
                "humidity": f"{hist_data['humidity']}%",
                "wind_speed": f"{hist_data.get('windspeed', 0)} km/h"
            }
        except requests.exceptions.RequestException as e:
            raise ValueError(f"Network error or API issue fetching historical weather for {city} on {date_obj.strftime('%Y-%m-%d')}: {str(e)}")
        except (KeyError, TypeError, IndexError) as e:
            raise ValueError(f"Unexpected API response format for historical weather for {city} on {date_obj.strftime('%Y-%m-%d')}: {str(e)}")
        except ValueError as e: # Catch ValueErrors raised by our own date checks
             raise e
        except Exception as e: # Catch-all for other errors
            raise ValueError(f"Historical weather data unavailable for {city} on {date_obj.strftime('%Y-%m-%d')}: {str(e)}")


    def get_weather(self, city: str, day: str = "today") -> Dict[str, Any]:
        """
        Get weather for a specific day (today, tomorrow, yesterday, or a specific date)
        Args:
            city: City name
            day: Either 'today', 'tomorrow', 'yesterday', or a date string (e.g., 'June 5, 2023')
        Returns:
            Weather data dictionary
        """
        if not self.api_key:
            raise ValueError("API key for Visual Crossing is not configured.")
        try:
            day_lower = day.lower()
            if day_lower == "today":
                return self.get_current_weather(city)
            elif day_lower == "tomorrow":
                return self._get_tomorrows_weather(city)
            elif day_lower == "yesterday":
                yesterday_date = (datetime.now() - timedelta(days=1)).date()
                data = self._get_historical_weather(city, yesterday_date)
                data["day"] = "Yesterday" # Override the formatted date with "Yesterday"
                return data
            elif day_lower == "last_week": # Handle "last_week"
                data = self._get_last_weeks_weather_summary(city)
                return data
            else:
                # Try to parse as a specific date
                try:
                    # Attempt to parse the date string.
                    # dateutil.parser is flexible.
                    parsed_dt_obj = date_parser.parse(day)
                    final_date_for_historical = parsed_dt_obj.date()
                    return self._get_historical_weather(city, final_date_for_historical)
                except (ValueError, OverflowError) as date_parse_err:
                    raise ValueError(f"Invalid day or date format: '{day}'. Please use 'today', 'tomorrow', 'yesterday', or a specific date like 'June 5, 2023'. Error: {date_parse_err}")
        except ValueError as e: # Re-raise ValueErrors from internal methods
             raise e
        except requests.exceptions.RequestException as e:
            raise ValueError(f"Network error or API issue fetching weather for {city} ({day}): {str(e)}")
        except (KeyError, TypeError, IndexError) as e:
            raise ValueError(f"Unexpected API response format for {city} ({day}): {str(e)}")
        except Exception as e: # Catch-all for other errors
            raise ValueError(f"Weather data unavailable for {city} ({day}): {str(e)}")


# This function will be imported by langgraph_core.py
def get_weather_info(location: str, day: str = "today") -> str: # Added day parameter
    tool = WeatherTool()
    try:
        weather_data = tool.get_weather(location, day) # Use the new get_weather method
        day_info = weather_data['day']
        city_name = weather_data['city']

        if "Last Week" in day_info:
            # Specific format for weekly summary
            return (
                f"Here's the weather summary for {day_info} in {city_name}:\n"
                f"  🌡️ Average Temperature: {weather_data['temperature']}\n"
                f"  🤔 Average Feels Like: {weather_data['feels_like']}\n"
                f"  💧 Average Humidity: {weather_data['humidity']}\n"
                f"  💨 Average Wind Speed: {weather_data['wind_speed']}\n"
                f"  ☁️ Conditions were varied, for example: {weather_data['description']}"
            )
        else:
            # Format for single day (today, tomorrow, yesterday, specific date)
            return (
                f"Here is the weather for {day_info} in {city_name}:\n"
                f"  🌡️ Temperature: {weather_data['temperature']} (feels like {weather_data['feels_like']})\n"
                f"  ☁️ Conditions: {weather_data['description']}\n"
                f"  💧 Humidity: {weather_data['humidity']}\n"
                f"  💨 Wind Speed: {weather_data['wind_speed']}"
            )
    except ValueError as e:
        return str(e) # Return the error message as a string
    except Exception as e:
        # Catch any unexpected errors from the tool and return a generic message
        return f"An error occurred while fetching weather data: {str(e)}"


# The main() function for command-line testing can be kept for development
# but won't be used by the FastAPI app or LangGraph agent directly.
if __name__ == "__main__":
    def cli_main():
        print("🌤️ Weather Checker (CLI) 🌤️")
        print("---------------------------")

        while True:
            city_input = input("\nEnter city name (or 'quit' to exit): ").strip()
            if city_input.lower() == 'quit':
                print("Goodbye! 👋")
                break

            day_input = input("Enter day ('today', 'tomorrow', 'yesterday', or a date like 'June 5, 2023'): ").strip()
            if not day_input:
                day_input = "today"

            # Basic validation for CLI, more robust parsing happens in get_weather
            if day_input.lower() not in ["today", "tomorrow", "yesterday"]:
                try:
                    # Just check if it's a parsable date format for the CLI input
                    date_parser.parse(day_input)
                except (ValueError, OverflowError):
                    print("Invalid day or date format. Please use 'today', 'tomorrow', 'yesterday', or a recognized date format.")
                    continue

            try:
                # Using the new get_weather_info for consistency in output format
                weather_output_str = get_weather_info(city_input, day_input)
                print(f"\n{weather_output_str}\n")
            except Exception as e_cli: # Catch any error during CLI run
                print(f"❌ An error occurred: {e_cli}")

    cli_main()