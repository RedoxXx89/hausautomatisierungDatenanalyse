import dataclasses
import requests
import mysql.connector
from weatherSecrets import openWeatherMapSecrets
from mysqlSecrets import databaseLoginSecrets

@dataclasses.dataclass
class currentWeatherData:
    time: int               # Unix Timestamp of the measurement
    city: str               # City name
    country: str            # Country code
    temperature: float      # Temperature in °C
    feels_like: float       # Feels like temperature in °C
    temp_min: float         # Minimum temperature in °C
    temp_max: float         # Maximum temperature in °C
    pressure: int           # Atmospheric pressure in hPa
    humidity: int           # Humidity in %
    visibility: int         # Visibility in meters
    wind_speed: float       # Wind speed in m/s
    wind_direction: int     # Wind direction in degrees
    wind_gust: float        # Wind gust speed in m/s
    clouds: int             # Cloudiness in %
    weather_main: str       # Main weather condition (e.g. "Clouds")
    weather_description: str # Detailed weather description (e.g. "overcast clouds")
    sunrise: int            # Unix Timestamp of sunrise
    sunset: int             # Unix Timestamp of sunset


def uploadCurrentWeatherData():
    """Fetches current weather data and stores it in the database."""
    weather = getCurrentWeatherData()
    if weather is None:
        print("Skipping database insert due to failed weather data fetch.")
        return
    print("Fetched current weather data:", weather)
    insertCurrentWeatherData(weather)
    print("Weather data inserted into database.")


def getCurrentWeatherData() -> currentWeatherData | None:
    """Fetches current weather data from the OpenWeatherMap API and returns it as a currentWeatherData object."""
    url = (
        f"https://api.openweathermap.org/data/2.5/weather"
        f"?q={openWeatherMapSecrets.city},{openWeatherMapSecrets.country_code}"
        f"&appid={openWeatherMapSecrets.api_key}"
        f"&units=metric"
    )

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"Failed to fetch weather data: {e}")
        return None

    return currentWeatherData(
        time=data["dt"],
        city=data["name"],
        country=data["sys"]["country"],
        temperature=data["main"]["temp"],
        feels_like=data["main"]["feels_like"],
        temp_min=data["main"]["temp_min"],
        temp_max=data["main"]["temp_max"],
        pressure=data["main"]["pressure"],
        humidity=data["main"]["humidity"],
        visibility=data.get("visibility", 0),
        wind_speed=data["wind"]["speed"],
        wind_direction=data["wind"].get("deg", 0),
        wind_gust=data["wind"].get("gust", 0.0),
        clouds=data["clouds"]["all"],
        weather_main=data["weather"][0]["main"],
        weather_description=data["weather"][0]["description"],
        sunrise=data["sys"]["sunrise"],
        sunset=data["sys"]["sunset"],
    )


def insertCurrentWeatherData(weather: currentWeatherData):
    """Inserts the current weather data into the wetterdaten.currentWeather table."""
    conn = mysql.connector.connect(
        host=databaseLoginSecrets.host,
        user=databaseLoginSecrets.user,
        password=databaseLoginSecrets.password,
        database=databaseLoginSecrets.database_wetterdaten
    )

    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO wetterdaten.currentWeather
            (temperature, feels_like, temp_min, temp_max, pressure, humidity,
             visibility, wind_speed, wind_direction, wind_gust, clouds,
             weather_main, weather_description, sunrise, sunset)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                FROM_UNIXTIME(%s), FROM_UNIXTIME(%s))
    """, (
        weather.temperature,
        weather.feels_like,
        weather.temp_min,
        weather.temp_max,
        weather.pressure,
        weather.humidity,
        weather.visibility,
        weather.wind_speed,
        weather.wind_direction,
        weather.wind_gust,
        weather.clouds,
        weather.weather_main,
        weather.weather_description,
        weather.sunrise,
        weather.sunset,
    ))

    conn.commit()
    cursor.close()
    conn.close()


if __name__ == "__main__":
    weather = getCurrentWeatherData()
    print(weather)
    insertCurrentWeatherData(weather)
    print("Weather data inserted into database.")
