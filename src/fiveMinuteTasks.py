import oilburnerExhaustTemperatureAnalysis as oilburner
import ambientWeatherData as weather

if __name__ == "__main__":
    #check database for unprocessed events and process them
    oilburner.exhaustTemperatureAnalysis()
    #get current weather data and insert it into the database
    weather.uploadCurrentWeatherData()
