import json
import requests
import datetime
import schedule
import time

# import RPi.GPIO as GPIO

HALF_POWER_HOURS = 8
ZERO_POWER_HOURS = 4


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

    # Tää skip oli aika hieno
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
        # Print average price
        print("Average price: " + str(self.average_price))

        # Print price difference between highest and lowest
        print(
            "Price difference between highest and lowest: "
            + str(self.price_difference_between_highest_and_lowest)
        )

        # Print highest prices
        print("Highest prices:")
        for hour in self.highest_prices:
            print(str(hour["Hour"]) + " " + str(hour["PriceNoTax"]))

        # Print lowest prices
        print("Lowest prices:")
        for hour in self.lowest_prices:
            print(str(hour["Hour"]) + " " + str(hour["PriceNoTax"]))

        # Print hour prices
        print("Hour prices:")
        self.hour_prices.sort(key=lambda x: x["Rank"])
        for hour in self.hour_prices:
            print(str(hour["Hour"]) + " " + str(hour["PriceNoTax"]))

    def set_rasbperry_pi_gpio_pin(pin_number, state):
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

    def set_prices_for_today(self):
        hour_prices = HourPrices()
        self.hour_prices = hour_prices.hour_prices

        highest_prices = hour_prices.get_highest_prices(
            ZERO_POWER_HOURS + HALF_POWER_HOURS, 0
        )

        self.ZeroPowerHours = []
        self.HalfPowerHours = []

        highest_prices.sort(key=lambda x: x["Hour"])

        # Reorder zero power hours and half power hours so that there are no consecutive zero power hours
        for hour in highest_prices:


            if self.ZeroPowerHours: 
                print("debug")
                print(self.ZeroPowerHours[-1]["Hour"])
                print(hour["Hour"] - 1)


            if len(self.ZeroPowerHours) < ZERO_POWER_HOURS and (
                not self.ZeroPowerHours or self.ZeroPowerHours[-1]["Hour"] != hour["Hour"] - 1
            ):                       
                self.ZeroPowerHours.append(hour)
            else:
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


ht = HeatControl()
# Keep the program running
while True:
    schedule.run_pending()
    time.sleep(1)
