import React from 'react';

// Using emojis for simplicity, can be replaced with SVGs or an icon library
const ThermometerIcon = () => <span role="img" aria-label="temperature" className="mr-2">🌡️</span>;
const CloudIcon = () => <span role="img" aria-label="condition" className="mr-2">☁️</span>;
const DropletIcon = () => <span role="img" aria-label="humidity" className="mr-2">💧</span>;
const WindIcon = () => <span role="img" aria-label="wind" className="mr-2">💨</span>;
const CalendarIcon = () => <span role="img" aria-label="day" className="mr-2">📅</span>;
const LocationIcon = () => <span role="img" aria-label="city" className="mr-2">📍</span>;

function WeatherDisplay({ weatherData }) {
  if (!weatherData) {
    return null;
  }

  const { city, day, temperature, feels_like, description, humidity, wind_speed } = weatherData;

  return (
    <div className="mt-4 p-4 bg-blue-50 border-2 border-blue-200 rounded-lg shadow-md text-gray-700">
      <div className="flex items-center mb-3">
        <LocationIcon />
        <h3 className="text-xl font-semibold text-blue-700">
          Weather in {city}
        </h3>
      </div>
      <div className="flex items-center mb-3 text-md text-blue-600">
        <CalendarIcon />
        <span>{day}</span>
      </div>
      
      <ul className="space-y-2">
        <li className="flex items-center">
          <ThermometerIcon />
          <span><strong>Temperature:</strong> {temperature} (feels like {feels_like})</span>
        </li>
        <li className="flex items-center">
          <CloudIcon />
          <span><strong>Conditions:</strong> {description}</span>
        </li>
        <li className="flex items-center">
          <DropletIcon />
          <span><strong>Humidity:</strong> {humidity}</span>
        </li>
        <li className="flex items-center">
          <WindIcon />
          <span><strong>Wind:</strong> {wind_speed}</span>
        </li>
      </ul>
    </div>
  );
}
export default WeatherDisplay;
