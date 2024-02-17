# Import necessary modules & packages:
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from snowflake.connector import connect
from snowflake.sqlalchemy import URL
from datetime import datetime
from snowflake.connector.pandas_tools import pd_writer
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType
import pandas as pd
import json
import time
import os

"""
# Read in Snowflake credentials - local testing:
with open("Credentials.json", "r") as f:
    config = json.load(f)
"""

# Set credential variables:
user = os.environ["USER"]
password = os.environ["PASSWORD"]
account = os.environ["ACCOUNT"]
warehouse = os.environ["WAREHOUSE"]
database = os.environ["DATABASE"]
schema = os.environ["SCHEMA"]
role = os.environ["ROLE"]

# Establish Snowflake connection:
conn = connect(
    user=user,
    password=password,
    account=account,
    warehouse=warehouse,
    database=database,
    schema=schema,
)

# Create SQLAlchemy engine:
engine = URL(
    user=user,
    password=password,
    account=account,
    warehouse=warehouse,
    database=database,
    schema=schema,
    role=role,
)

# Set driver location and provide website URL:
# service = Service(executable_path="/usr/local/bin/chromedriver")
driver_path = Service(ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install())
driver = webdriver.Chrome(service=driver_path)

driver.get("https://www.chrono24.co.uk/")
wait = WebDriverWait(driver, 10)

# Wait for cookie window popping up and click 'accept':
wait.until(
    EC.element_to_be_clickable(
        (
            By.XPATH,
            "//button[@class='btn btn-primary btn-full-width js-cookie-accept-all wt-consent-layer-accept-all m-b-2']",
        )
    )
).click()

# Wait for search box to be visible:
search_box = wait.until(
    EC.presence_of_element_located(
        (By.XPATH, "//input[@class='wt-search-input form-control ac_input']")
    )
)

# Pause 2 seconds before conducting search:
time.sleep(2)
search_text = search_box.send_keys("Rolex Paul Newman Dial" + Keys.RETURN)

# Create empty lists that later for loop will populate:
data = {"Title": [], "Price": [], "Image": [], "Link": []}

# Enter into outer try - checking for the 'next page' button being active:
try:

    has_next_page = True

    while has_next_page:

        try:
            # Lookout for the 'subscribe to our newsletter' popup and decline if this does appear:
            try:
                popup = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located(
                        (By.XPATH, "//div[@class='js-modal-content modal-content']")
                    )
                )
                print("Popup found")

                close_button = popup.find_element(
                    By.XPATH,
                    "//button[@class='btn btn-secondary flex-equal w-100-sm m-r-sm-5 js-close-modal']",
                )
                close_button.click()
            except:
                pass

            # Wait for the grid of watches to be found and then isolate the containers when done:
            watches = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located(
                    (
                        By.XPATH,
                        "//div[@class='js-article-item-list article-item-list article-list block']",
                    )
                )
            )
            # print("Watch list found!") - Testing element is found

            containers = watches.find_elements(
                By.XPATH,
                "//div[@class='article-item-container wt-search-result article-image-carousel']",
            )

            # print(containers[1].get_attribute("innerHTML")) - Checking list values are distinct

            # Pass through list of containers, finding the description and price of each - pass these into the empty lists above:
            for container in containers:
                desc = container.find_element(
                    By.XPATH, ".//div[@class='text-sm text-sm-md text-ellipsis m-b-2']"
                )
                price = container.find_element(By.XPATH, ".//div[@class='text-bold']")
                img = container.find_element(
                    By.XPATH,
                    ".//img",
                ).get_attribute("src")
                link = container.find_element(By.XPATH, ".//a").get_attribute("href")

                # print(desc.text + " - " + price.text) - Testing

                data["Title"].append(desc.text)
                data["Price"].append(price.text)
                data["Image"].append(img)
                data["Link"].append(link)

            # Pause 2 seconds before pressing the 'next page' button if present:
            next_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//a[@class='paging-next']"))
            )
            time.sleep(2)
            next_button.click()

        except:
            has_next_page = False

except:
    print("An error occured!")

finally:
    driver.quit()

# Create a dataframe from the two lists:
df = pd.DataFrame(data)
df["As of date"] = datetime.now()

print("Dataframe created...")
print(df)

"""
# Output a local copy of the dataframe - local testing:
df.to_csv(
    "G:\\My Drive\\My Documents\\Python\\Projects\\Chrono24 Webscraping\\Output.csv",
    encoding="utf-8",
    index=False,
)
"""

# Push the resulting data out to a Snowflake table, appending new data each day:
df.to_sql(
    "np_chronodata",
    engine,
    index=False,
    if_exists="append",
    method=pd_writer,
)

# Close the connection:
conn.close()

# Print a completion message:
print("Run completed successfully!")
