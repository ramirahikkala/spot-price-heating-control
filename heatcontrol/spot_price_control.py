
import json
import requests
import datetime
import schedule
import time

HALF_POWER_HOURS = 3
ZERP_POWER_HOURS = 3

class HourPrices:   

    def __init__(self):
        
        self.hour_prices = None

        while self.hour_prices == None:
            self.hour_prices = self.get_hour_prices()
            # sleep for 1 hour if hour prices are not available
            if self.hour_prices == None:
                time.sleep(3600)

    
    # Get hour prices for today from curl -X GET "https://api.spot-hinta.fi/Today" -H  "accept: application/json"
    def get_hour_prices(self):
        url = "https://api.spot-hinta.fi/Today"
        response = requests.get(url)
        #check if the response code is ok (200)
        if response.status_code != 200:
            #if response code is not ok (200), print the resulting http error code with description
            print("Error: " + str(response.status_code) + " " + response.text)
            return None
        return json.loads(response.text)

    # Get highest prices for today
    def get_highest_prices(self, number_of_hours_to_get, number_of_hours_to_skip):
        hour_prices = self.hour_prices
        hour_prices.sort(key=lambda x: x['Rank'], reverse=True)
        return hour_prices[number_of_hours_to_skip:number_of_hours_to_skip + number_of_hours_to_get]
    
    # Tää skip oli aika hieno
    def get_lowest_prices(self, number_of_hours_to_get, number_of_hours_to_skip):
        hour_prices = self.hour_prices
        hour_prices.sort(key=lambda x: x['Rank'])
        return hour_prices[number_of_hours_to_skip:number_of_hours_to_skip + number_of_hours_to_get]

    def get_average_price(self):
        hour_prices = self.hour_prices
        total = 0
        for hour_price in hour_prices:
            total += hour_price['PriceNoTax']
        return total / len(hour_prices)

    def get_average_price_for_hours(self, number_of_hours_to_get):
        hour_prices = self.hour_prices
        hour_prices.sort(key=lambda x: x['Rank'])
        total = 0
        for hour_price in hour_prices[:number_of_hours_to_get]:
            total += hour_price['PriceNoTax']
        return total / number_of_hours_to_get

    def get_price_difference_between_highest_and_lowest(self, number_of_hours_to_get):
        highest_prices = self.get_highest_prices(number_of_hours_to_get, 0)
        lowest_prices = self.get_lowest_prices(number_of_hours_to_get,0)
        return highest_prices[0]['PriceNoTax'] - lowest_prices[0]['PriceNoTax']
   


class HeatControl:

    def __init__(self):
        self.average_price = 0
        self.average_price_for_hours = 0
        self.price_difference_between_highest_and_lowest = 0
        self.highest_prices = []
        self.lowest_prices = []
        self.hour_prices = []

        self.new_day()

        self.set_heat()

        # Schedule set_heat() to run beginning of every hour
        schedule.every().hour.at(":00").do(self.set_heat)
        
        # schedule set_prices_for_today() to run every day at 00:00
        schedule.every().day.at("00:00").do(self.new_day)
    
    def new_day(self):
        self.set_prices_for_today()
        self.set_heat()
    
    def set_rasbperry_pi_gpio_pin(pin_number, state):
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(pin_number, GPIO.OUT)
        GPIO.output(pin_number, state)
        GPIO.cleanup()
    
    def set_heat_50_percent(self):
        set_rasbperry_pi_gpio_pin(17, True)
        set_rasbperry_pi_gpio_pin(27, False)
    
    def set_heat_100_percent(self):
        set_rasbperry_pi_gpio_pin(17, True)
        set_rasbperry_pi_gpio_pin(27, True)

    def set_heat_on(self):
        set_rasbperry_pi_gpio_pin(17, False)
        set_rasbperry_pi_gpio_pin(27, False)

    def set_prices_for_today(self):
        hour_prices = HourPrices()
        self.average_price = hour_prices.get_average_price()
        self.average_price_for_hours = hour_prices.get_average_price_for_hours(3)
        self.price_difference_between_highest_and_lowest = hour_prices.get_price_difference_between_highest_and_lowest(ZERP_POWER_HOURS + HALF_POWER_HOURS)
        self.hour_prices = hour_prices.hour_prices

        # Tää oli myös aika hieno kohta
        self.ZeroPowerHours = hour_prices.get_highest_prices(ZERP_POWER_HOURS, 0)
        self.HalfPowerHours = hour_prices.get_highest_prices(HALF_POWER_HOURS, ZERP_POWER_HOURS)

    def set_heat(self):
        reset_heat = True
        # Set heat on 50 % if we are on HalfPowerHours
        print('Setting heat half power')
        for hour in self.HalfPowerHours:
            # Parse hour from datetime string
            hour['Hour'] = datetime.datetime.strptime(hour['DateTime'], '%Y-%m-%dT%H:%M:%S%z').hour
            print(hour['Hour'])
            if hour['Hour'] == datetime.datetime.now().hour:
                # self.set_heat_50_percent()
                print(str( datetime.datetime.now()) + ': Half power')
                reset_heat = False
                break
        
        # Set heat on 100 % if we are on ZeroPowerHours
        print('Setting heat 100 %')
        for hour in self.ZeroPowerHours:
            # Parse hour from datetime string
            hour['Hour'] = datetime.datetime.strptime(hour['DateTime'], '%Y-%m-%dT%H:%M:%S%z').hour
            print(hour['Hour'])
            if hour['Hour'] == datetime.datetime.now().hour:
                # self.set_heat_100_percent()
                print(str( datetime.datetime.now()) + ': Zero power')  
                reset_heat = False
                break
        
        if reset_heat:
            # self.set_heat_on()
            print(str( datetime.datetime.now()) + ': Heat on')
            

ht = HeatControl()
# Keep the program running
while True:
    schedule.run_pending()
    time.sleep(1)
    