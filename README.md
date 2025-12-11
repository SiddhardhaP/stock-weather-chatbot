# Weather & Stock AI Agent

A full-stack AI-powered conversational agent that provides real-time weather information and stock market data through natural language queries. Built with React, FastAPI, and LangGraph, featuring streaming responses and intelligent conversation memory.

## 🌟 Features

### Core Functionality
- **Intelligent Query Routing**: Automatically detects whether user queries are about weather or stocks using keyword analysis
- **Real-time Streaming**: Responses stream word-by-word for a smooth, interactive experience
- **Conversation Memory**: Remembers context from previous queries (e.g., "that stock", "same city")
- **Natural Language Processing**: Extracts cities, stock symbols, and dates from conversational input
- **Multi-date Support**: Query current data, historical data, forecasts, and weekly averages

### Weather Features
- Current weather conditions for any city worldwide
- Historical weather data for specific dates
- Tomorrow's weather forecast
- Last week's weather summary
- Supports major Indian and international cities

### Stock Features
- Real-time stock prices for global companies
- Historical stock data for specific dates
- Last week's average prices with high/low ranges
- Automatic company name to ticker symbol conversion
- Support for major stock exchanges (NYSE, NASDAQ, NSE, etc.)

## 🛠️ Tech Stack

### Backend
- **FastAPI**: Modern, fast web framework for building APIs
- **LangGraph**: State machine framework for building AI agent workflows
- **yfinance**: Yahoo Finance API wrapper for stock data
- **Visual Crossing API**: Weather data provider
- **Python 3.8+**: Core programming language

### Frontend
- **React 19**: UI library with hooks
- **TypeScript**: Type-safe JavaScript
- **Vite**: Fast build tool and dev server
- **Tailwind CSS**: Utility-first CSS framework
- **Axios**: HTTP client for API requests

## 📋 Prerequisites

- Python 3.8 or higher
- Node.js 16+ and npm
- Visual Crossing API key ([Get one here](https://www.visualcrossing.com/weather-api))
- (Optional) Virtual environment tool (venv, conda, etc.)

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd weather_stock_agent
```

### 2. Backend Setup

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\Activate.ps1
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Frontend Setup

```bash
cd frontend
npm install
cd ..
```

### 4. Environment Configuration

Create a `.env` file in the `backend` directory:

```bash
# backend/.env
VISUALCROSSING_API_KEY=your_visual_crossing_api_key_here
ALLOWED_ORIGINS_CSV=http://localhost:5173,http://127.0.0.1:5173
```

**Note**: Replace `your_visual_crossing_api_key_here` with your actual Visual Crossing API key.

## 🎯 Usage

### Starting the Backend Server

From the project root directory:

```bash
# Activate virtual environment (if not already activated)
.\venv\Scripts\Activate.ps1  # Windows PowerShell
# or
source venv/bin/activate     # macOS/Linux

# Start the FastAPI server
python -m uvicorn backend.main:app --reload
```

The backend will be available at `http://localhost:8000`

### Starting the Frontend Development Server

From the project root directory:

```bash
cd frontend
npm run dev
```

The frontend will be available at `http://localhost:5173`

### Using the Application

1. Open your browser and navigate to `http://localhost:5173`
2. Type your question in the chat interface
3. Examples:
   - "What's the weather in Mumbai?"
   - "Show me Apple stock price"
   - "What was Google's stock price on June 5?"
   - "Weather tomorrow in Delhi"
   - "Amazon stock last week"

## 📁 Project Structure

```
weather_stock_agent/
├── backend/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application and endpoints
│   ├── langgraph_core.py       # LangGraph agent workflow and routing logic
│   ├── weather.py              # Weather API integration
│   ├── stocks.py               # Stock data fetching and processing
│   └── .env                    # Environment variables (create this)
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ChatBox.jsx     # Main chat interface component
│   │   │   └── WeatherDisplay.jsx
│   │   ├── App.jsx             # Main React component
│   │   └── main.tsx            # React entry point
│   ├── package.json
│   └── vite.config.ts
├── requirements.txt            # Python dependencies
├── README.md                   # This file
└── cmd.txt                     # Quick command reference
```

## 🔌 API Endpoints

### POST `/ask`

Streams AI agent responses for user queries.

**Request Body:**
```json
{
  "question": "What's the weather in London?"
}
```

**Response:**
- Content-Type: `text/plain`
- Streaming response with word-by-word output

**Example:**
```bash
curl -X POST "http://localhost:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the price of Apple stock?"}'
```

### GET `/`

Health check endpoint.

**Response:**
```json
{
  "message": "FastAPI backend is running"
}
```

## 💡 Example Queries

### Weather Queries
- "Weather in Hyderabad"
- "What's the temperature in New York today?"
- "Show me tomorrow's weather for Mumbai"
- "Weather yesterday in Bangalore"
- "What was the weather in Delhi last week?"

### Stock Queries
- "Apple stock price"
- "What's Google's current stock price?"
- "Show me Amazon stock on June 5, 2023"
- "Microsoft stock yesterday"
- "Tesla stock last week"
- "What was the price of Meta stock on January 15?"

### Contextual Queries (Uses Memory)
- "What's the weather there?" (after asking about a city)
- "What about that stock?" (after asking about a stock)
- "Same place tomorrow" (after asking about weather)

## 🧠 How It Works

1. **User Input**: User types a question in the chat interface
2. **Routing**: LangGraph router analyzes the query and determines if it's weather or stock-related
3. **Memory Processing**: The agent checks for contextual references and uses conversation memory
4. **Entity Extraction**: NLP extracts relevant entities (city names, stock symbols, dates)
5. **API Calls**: Appropriate tool (weather or stock) fetches data from external APIs
6. **Response Streaming**: Results are streamed back to the user word-by-word
7. **Memory Update**: Conversation context is saved for future queries


### Supported Stock Symbols

The agent recognizes common company names and converts them to ticker symbols:
- Google/Alphabet → GOOGL
- Amazon → AMZN
- Apple → AAPL
- Microsoft → MSFT
- Tesla → TSLA
- Meta/Facebook → META
- Netflix → NFLX
- NVIDIA → NVDA

For other companies, the agent uses Yahoo Finance's search API to find the correct ticker symbol.

## 🐛 Troubleshooting

### Backend Issues

**Issue**: `VISUALCROSSING_API_KEY environment variable not set`
- **Solution**: Create a `.env` file in the `backend` directory with your API key

**Issue**: CORS errors in browser
- **Solution**: Ensure `ALLOWED_ORIGINS_CSV` in `.env` includes your frontend URL

**Issue**: Module not found errors
- **Solution**: Ensure you're running from the project root and virtual environment is activated

### Frontend Issues

**Issue**: Cannot connect to backend
- **Solution**: Verify backend is running on port 8000 and check CORS settings

**Issue**: Streaming not working
- **Solution**: Check browser console for errors and ensure backend is sending proper streaming response

## 📝 Development

### Running Tests

Currently, the project includes CLI testing capabilities. You can test individual modules:

```bash
# Test weather module
python -m backend.weather

# Test stocks module
python -m backend.stocks

# Test LangGraph agent (interactive mode)
python -m backend.langgraph_core
```

### Adding New Features

1. **New Tools**: Add tool functions in `backend/weather.py` or `backend/stocks.py`
2. **New Routes**: Add routing logic in `backend/langgraph_core.py` `_router_node` method
3. **UI Components**: Add React components in `frontend/src/components/`

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 🙏 Acknowledgments

- [LangGraph](https://github.com/langchain-ai/langgraph) for the agent framework
- [Visual Crossing](https://www.visualcrossing.com/) for weather data
- [Yahoo Finance](https://finance.yahoo.com/) for stock market data
- [FastAPI](https://fastapi.tiangolo.com/) for the excellent web framework
- [React](https://react.dev/) for the UI library
