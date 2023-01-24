import sys
import json
import requests
import datetime
import schedule
import time
from itertools import groupby
from operator import itemgetter

HALF_POWER_HOURS = 8
ZERO_POWER_HOURS = 6
MAX_ULTIMATE_LOWEST_PRICE_HOURS = 5
MAX_CONSECUTIVE_ZERO_POWER_HOURS = 2
ULTIMATE_LOWEST_PRICE = 0.03
ULTIMATE_HIGHEST_PRICE = 0.35

# Ultimate maximum number of zero power hours
SAFE_ZERO_POWER_HOURS = 12

class HourPrices:
    def __init__(self):

        self.hour_prices = None

        while self.hour_prices == None:
            self.hour_prices = self.__set_hour_prices()
            # sleep for 1 hour if hour prices are not available
            if self.hour_prices == None:
                time.sleep(3600)

    # Get hour prices for today from curl -X GET "https://api.spot-hinta.fi/Today" -H  "accept: application/json"
    def __set_hour_prices(self):
        url = "https://api.spot-hinta.fi/Today"
        response = requests.get(url)
        # check if the response code is ok (200)
        if response.status_code != 200:
            # if response code is not ok (200), print the resulting http error code with description
            print("Error: " + str(response.status_code) + " " + response.text)
            return None
        hour_prices = json.loads(response.text)

        for hour_price in hour_prices:
            hour_price["Hour"] = datetime.datetime.strptime(
                hour_price["DateTime"], "%Y-%m-%dT%H:%M:%S%z"
            ).hour

        return hour_prices

    # Get highest prices for today
    def get_highest_prices(self, number_of_hours_to_get, number_of_hours_to_skip):
        hour_prices = self.hour_prices
        hour_prices.sort(key=lambda x: x["Rank"], reverse=True)
        return hour_prices[
            number_of_hours_to_skip : number_of_hours_to_skip + number_of_hours_to_get
        ]

    def get_lowest_prices(self, number_of_hours_to_get, number_of_hours_to_skip):
        hour_prices = self.hour_prices
        hour_prices.sort(key=lambda x: x["Rank"])
        return hour_prices[
            number_of_hours_to_skip : number_of_hours_to_skip + number_of_hours_to_get
        ]

    def get_average_price(self):
        hour_prices = self.hour_prices
        total = 0
        for hour_price in hour_prices:
            total += hour_price["PriceNoTax"]
        return total / len(hour_prices)

    def get_average_price_for_hours(self, number_of_hours_to_get):
        hour_prices = self.hour_prices
        hour_prices.sort(key=lambda x: x["Rank"])
        total = 0
        for hour_price in hour_prices[:number_of_hours_to_get]:
            total += hour_price["PriceNoTax"]
        return total / number_of_hours_to_get

    def get_price_difference_between_highest_and_lowest(self, number_of_hours_to_get):
        highest_prices = self.get_highest_prices(number_of_hours_to_get, 0)
        lowest_prices = self.get_lowest_prices(number_of_hours_to_get, 0)
        return highest_prices[0]["PriceNoTax"] - lowest_prices[0]["PriceNoTax"]


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

        # Print half power hours
        print("Half power hours:")
        for hour in self.HalfPowerHours:
            print(str(hour["Hour"]) + " " + str(hour["PriceNoTax"]))

        # Print zero power hours
        print("Zero power hours:")
        for hour in self.ZeroPowerHours:
            print(str(hour["Hour"]) + " " + str(hour["PriceNoTax"]))

        # Print hour prices
        print("Hour prices:")
        self.hour_prices.sort(key=lambda x: x["Rank"])
        for hour in self.hour_prices:
            print(str(hour["Hour"]) + " " + str(hour["PriceNoTax"]))

    def set_rasbperry_pi_gpio_pin(pin_number, state):
        import RPi.GPIO as GPIO

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(pin_number, GPIO.OUT)
        GPIO.output(pin_number, state)
        GPIO.cleanup()

    def set_heat_50_percent(self):
        self.set_rasbperry_pi_gpio_pin(17, True)
        self.set_rasbperry_pi_gpio_pin(27, False)

    def set_heat_100_percent(self):
        self.set_rasbperry_pi_gpio_pin(17, True)
        self.set_rasbperry_pi_gpio_pin(27, True)

    def set_heat_on(self):
        self.set_rasbperry_pi_gpio_pin(17, False)
        self.set_rasbperry_pi_gpio_pin(27, False)
    
    def get_number_of_consecutive_zero_power_hours(self, hour):
        
        # Calculate number of consecutive hours
        hours = [h['Hour'] for h in self.ZeroPowerHours]

        # Add next hour to test if it is consecutive
        hours.append(hour['Hour'])
        
        hours.sort()

        def max_consecutive(numbers):
            max_count = 0
            current_count = 1
            for i in range(1, len(numbers)):
                if numbers[i] == numbers[i-1] + 1:
                    current_count += 1
                else:
                    max_count = max(max_count, current_count)
                    current_count = 1
            return max(max_count, current_count)

        return max_consecutive(hours)

    def set_prices_for_today(self):

        self.hour_prices = HourPrices().hour_prices

        self.hour_prices.sort(key=lambda x: x["Rank"], reverse=True)

        self.ZeroPowerHours = []
        self.HalfPowerHours = []
        add_to_zero_power_hours = False
        
        for hour in self.hour_prices:

            if len(self.ZeroPowerHours) < ZERO_POWER_HOURS:
                
                consecutive_hours = self.get_number_of_consecutive_zero_power_hours(hour)

                if consecutive_hours <= MAX_CONSECUTIVE_ZERO_POWER_HOURS:
                    add_to_zero_power_hours=True

            # Add to ZeroPowerHours always if price is above ultimate max price
            if hour["PriceWithTax"] > ULTIMATE_HIGHEST_PRICE:
                add_to_zero_power_hours = True
            
            # Keep heating on if price is below ultimate min price
            if hour["PriceWithTax"] < ULTIMATE_LOWEST_PRICE:
                continue

            if add_to_zero_power_hours:
                
                # Don't add more than SAFE_ZERO_POWER_HOURS
                if len(self.ZeroPowerHours) < SAFE_ZERO_POWER_HOURS:
                    self.ZeroPowerHours.append(hour)
                add_to_zero_power_hours = False

            elif len(self.HalfPowerHours) < HALF_POWER_HOURS:
                self.HalfPowerHours.append(hour)

    def set_heat(self):
        reset_heat = True

        for hour in self.HalfPowerHours:
            if hour["Hour"] == datetime.datetime.now().hour:
                # self.set_heat_50_percent()
                print(str(datetime.datetime.now()) + ": Half power")
                reset_heat = False
                break

        # Set heat on 100 % if we are on ZeroPowerHours

        for hour in self.ZeroPowerHours:
            if hour["Hour"] == datetime.datetime.now().hour:
                # self.set_heat_100_percent()
                print(str(datetime.datetime.now()) + ": Zero power")
                reset_heat = False
                break

        if reset_heat:
            # self.set_heat_on()
            print(str(datetime.datetime.now()) + ": Heat on")

def main():
        
        ht = HeatControl()
        # Keep the program running
        while True:
            try:
                schedule.run_pending()
                time.sleep(1)
            except:
                ht.set_heat_on()
                print("Unexpected error:", sys.exc_info()[0])

if __name__ == "__main__":
    main()
