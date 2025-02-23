
import time
from datetime import datetime
import logging
import firebase_admin
from firebase_admin import credentials, firestore, messaging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from selenium.common.exceptions import (
    TimeoutException,
    WebDriverException,
    NoSuchElementException,
    StaleElementReferenceException,
)

logging.basicConfig(level=logging.INFO)
# Initalizing Firebase
cred = credentials.Certificate(r"A:\Python\Web Scraper Script\credentials\scraper-db59b-firebase-adminsdk-x4wc8-1a17eb7609.json")
firebase_admin.initialize_app(cred)
dataBase = firestore.client()

# SettingUp Chrome WebDriver with options for headless mode
chromedriver_path = r"A:\Python\Web Scraper Script\driver\chromedriver.exe"
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_argument("--disable-extensions")  # Optional: disables extensions

# Set the user agent to make it appear like a regular browser
chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

# SettingUp Chrome WebDriver for automation on chrome
service = Service(chromedriver_path)
driver = webdriver.Chrome(service=service, options=chrome_options)

website_Names = ['JB Hifi', 'Noon UAE','Amazon UAE','Amazon USA']
target_for_sites = [
    {
        'siteName': 'jb hi fi',
        'targetParentClass': 'PriceTag_actualWrapperDefault__1eb7mu9p',
        'targetElementClass': 'PriceTag_actual__1eb7mu9q'
    },
    {
        'siteName': 'Noon UAE',
        'targetElementClass': 'priceNow'
    },
    {
        'siteName': 'Amazon UAE',
        'targetParentClass': 'a-section',
        'targetElementClass': 'span.a-price.a-text-price.a-size-medium span[aria-hidden="true"]',
        'targetParentClass2': 'reinventPricePriceToPayMargin',
        'targetElementClass2': 'a-price-whole',
    },
    {
        'siteName': 'Amazon USA',
        'targetParentClass': 'reinventPricePriceToPayMargin',
        'targetElementClass': 'a-price-whole',
    },
]

# Function for writing details for timeout and noSuch element found error in a file
def log_error(site_name, url, exception):
    """
    Logs errors to a file with a timestamp and site details.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"{timestamp} - Site: {site_name} \n URL: {url} \n This Url may be expired or not available in your region \n Detailed Error: {exception}\n\n\n"
    print(log_message)  # Also print the error to the console for immediate debugging
    with open("logg.txt", "a") as log_file:
        log_file.write(log_message)

# Function to fetch all product and all URLs and return them in lists
def fetchProductInformation(site_name):
    try:
        product_reference = dataBase.collection(site_name)
        all_docs = product_reference.stream()
    except Exception as e:
        print(f"Connection Issue with Firestore, Failed to retrieve documents from collection '{site_name}'. Error: {e}")
        return [], []  

    product_names = []
    urls = []
    try:
        for doc in all_docs:
            try:
                product_id = doc.id
                product_information = doc.to_dict()
                product_name = product_information.get('Product Name')
                url = product_information.get('Url')

                if product_name and url is not None:
                    product_names.append(product_name)
                    urls.append(url)
                else:
                    print(f"Missing 'Product Name' or 'Url' in document {product_id}.")
            except KeyError as e:
                print(f"KeyError in document {doc.id}: {e}")
            except Exception as e:
                print(f"Unexpected error in processing document {doc.id}: {e}")
    except:
        print(f"Connection Issue with Firestore, problem in fetching documents for collection {site_name}")

    return product_names, urls

# Function to safely find an element
def safe_find_element(by, value):
    for _ in range(3):  # retry 3 times if failed
        try:
            element = driver.find_element(by, value)
            return element
        except Exception:
            time.sleep(3)  # wait before retrying
    raise Exception("Failed to find element after 3 retries")

# Function for fetching each product's price
def scrape_price(url, index,retries=3):
    attempt = 0
    while attempt < retries:
        try:
            driver.get(url)
            if website_Names[index] == 'Noon UAE':
                try:
                    WebDriverWait(driver, 60).until(
                        EC.presence_of_element_located((By.CLASS_NAME, target_for_sites[index]['targetElementClass']))
                    )
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(12)

                    # Use safe_find_element to ensure we handle any stale element exceptions
                    price_element = safe_find_element(By.CLASS_NAME, target_for_sites[index]['targetElementClass'])
                    if price_element:
                        price = price_element.text.split(' ')[1]
                        print(f'Got price on attempt {attempt + 1}')
                        return price
                except (TimeoutException, NoSuchElementException) as e:
                    log_error("Noon UAE", url, e)

            elif website_Names[index] == 'Amazon UAE':
                success = False  
                # Try the first approach for webpage format 1
                try:
                    WebDriverWait(driver, 60).until(
                        EC.presence_of_element_located((By.CLASS_NAME, target_for_sites[index]['targetParentClass']))
                    )
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(12)

                    price_element = safe_find_element(By.CSS_SELECTOR, target_for_sites[index]['targetElementClass'])
                    if price_element:
                        price = price_element.text
                        print(f"Got price on attempt {attempt + 1} using 1st approach")
                        success = True
                        return price
                    
                except (TimeoutException, NoSuchElementException) as e:
                    log_error("Harvey Norman", url, e)
                    logging.error(f"TimeOut or NoSuchElement exception occur in 1st approach attempt {attempt + 1} check logg.txt file for details")
                except Exception as e:
                    logging.error(f"First approach failed for URL {url}: {e}")

                # If the first approach fails, try the second one for webpage format 2
                if not success:
                    try:
                        time.sleep(6)
                        WebDriverWait(driver, 60).until(
                            EC.presence_of_element_located((By.CLASS_NAME, 'reinventPricePriceToPayMargin'))
                        )
                        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                        time.sleep(12)

                        # Use safe_find_element to ensure we handle any stale element exceptions
                        parent_element = safe_find_element(By.CLASS_NAME, 'reinventPricePriceToPayMargin')
                        price_element = parent_element.find_element(By.CLASS_NAME, 'a-price-whole')

                        if price_element and price_element.is_displayed():
                            print(f"Got price on attempt {attempt + 1} using 2nd approach")
                            return price
                    except (TimeoutException, NoSuchElementException) as e:
                        log_error("Amazon UAE", url, e)
                        logging.error(f"TimeOut or NoSuchElement exception occur in 2nd approach attempt {attempt + 1} check logg.txt file for details")
                    except Exception as e:
                        logging.error(f"Second also approach failed for URL {url}: {e}")

                logging.error(f"Failed to get price for URL {url} on Amazon UAE.")    
                return '0'
            # for general sites
            else:
                try:
                    WebDriverWait(driver, 60).until(
                        EC.presence_of_element_located((By.CLASS_NAME, target_for_sites[index]['targetParentClass']))
                    )
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(12)

                    parent_element = safe_find_element(By.CLASS_NAME, target_for_sites[index]['targetParentClass'])
                    price_element = parent_element.find_element(By.CLASS_NAME, target_for_sites[index]['targetElementClass'])
                    if price_element:
                        price = price_element.text
                        print(f'Got price in {attempt} attempt')
                        return price
                except (TimeoutException, NoSuchElementException) as e:
                    log_error("General", url, e)

        except WebDriverException as e:
            logging.error(f"WebDriverException for URL {url}: {e}")
        except Exception as e:
            logging.error(f"Unhandled exception for URL {url}: {e}")
        finally:
            attempt += 1
            print(f"Attempt {attempt} failed. Retrying in 5 seconds...")
            time.sleep(5)
    print(f"Failed to scrape price after {retries} attempts. ")
    logging.error(f"Failed to scrape price for URL {url} after {retries} attempts.")
    return '0'


    

# Main scraping loop for each website
for index, website_name in enumerate(website_Names):
    try:
        print(f"Scraping website: {website_name}")
        product_names, urls = fetchProductInformation(website_name)
        if not product_names or not urls:
            logging.warning(f"Skipping Because No products found for website: {website_name}")
            continue

        # List to store all scraped prices
        product_prices = []

        # Scraping prices for each product URL
        for url in urls:
            price = scrape_price(url, index)
            product_prices.append(price)

        for name, price in zip(product_names, product_prices):
            try:
                doc_ref = dataBase.collection(website_name).document(name)
                doc_ref.update({
                    'productPrice':price 
                })
                print(f'Data saved to Firestore successfully for {name}')
            except Exception as e:
                logging.error(f"Connection Error while saving data for product {name} on website {website_name}: {e}")
        print('------------------------------------------------------------')
    except Exception as e:
        logging.error(f"Error scraping data from website {website_name}: {e}")


driver.quit()

def delete_old_notification():
    try:
        # Reference to the 'Notifications' collection
        notification_collection_ref = dataBase.collection('Notifications')
        
        # Stream all documents in the collection
        notification_docs = notification_collection_ref.stream()

        for doc in notification_docs:
            try:
                # Attempt to delete each document
                doc.reference.delete()
                print(f"Deleted notification: {doc.id}")
            except Exception as e:
                print(f"Failed to delete notification {doc.id}: {e}")
        
        print("Old notifications deleted successfully.")
    
    except Exception as e:
        print(f"Error accessing or deleting from 'Notifications' collection: {e}")
    #--------------------------------------------------------------------------

delete_old_notification()

def notify_users(website_Name):
    try:
        products = dataBase.collection(website_Name).stream()

        # refrence for collection where notifications store
        notification_collection_ref = dataBase.collection('Notifications')

        for product in products:
            product_id = product.id
            product_data = product.to_dict()

            try:
                product_name_str = product_data.get('Product Name')
                current_price_str = product_data.get('productPrice')
                targeted_price_str = product_data.get('Targeted Price')
            except:
                print(f'problem in getting product data for product:{product_id}')

            if current_price_str is not None and targeted_price_str is not None and current_price_str != '0':
                # removing unwanted characters
                try:
                    current_price = float(current_price_str.replace('$', '').replace(',', '').replace('AED','').replace('€','').strip())
                    targeted_price = float(str(targeted_price_str).replace('$', '').replace(',', '').replace('AED','').replace('€','').strip())

                    print(f'Product: {product_name_str}')
                    print(f"Current price: {current_price}")
                    print(f"Targeted price: {targeted_price}")
                except:
                    print(f'problem in removing(unwanted characters) or parsing price and target price for product {product_id}')

                if current_price <= targeted_price:
                    try:

                        # add the product to notifications as collection
                        notification_collection_ref.document(product_name_str).set({
                            'name': product_name_str,
                            'siteName': website_Name,
                            'newPrice': current_price,
                            'target': targeted_price,

                        })
                        # getting Fcm tokens for all devices in our firestore
                        fcm_tokens = dataBase.collection('FCMTokens').stream()

                        for token_document in fcm_tokens:
                            token_doc_data = token_document.to_dict()
                            fcm_token =  token_doc_data.get('fcmToken')

                            # Now sending notification to this fcm token
                            if fcm_token:
                                # constructing message
                                message = messaging.Message(
                                    notification=messaging.Notification(
                                        title= f'Price Alert! {website_Name}',
                                        body=f'The price for {product_id} has dropped to {current_price}.',
                                        # image=notification_image_url,
                                        
                                    ),
                                    token=fcm_token,
                                    android=messaging.AndroidConfig(
                                        priority='high',
                                        # notification=messaging.AndroidNotification(
                                        #     icon='launcher_icon'  # Use the drawable resource name
                                        # )  # Ensure high-priority delivery
                                    ),
                                    apns=messaging.APNSConfig(
                                        payload=messaging.APNSPayload(
                                            aps=messaging.Aps(
                                                alert=messaging.ApsAlert(
                                                    title=f'Price Alert! {website_Name}',
                                                    body=f'The price for {product_id} has dropped to {current_price}.',
                                                ),
                                                sound="default",  # Adds notification sound for iOS
                                                content_available=True,  # Required for background notifications
                                            )
                                        )
                                    )
                                )
                                try:
                                    response = messaging.send(message)
                                    print(f'Successfully sent message: {response}')
                                    print('----------------------------------')

                                    time.sleep(4)  # Adjust as needed
                                except Exception as e:
                                    print(f'Failed to send message: {e}')
                    except Exception as e:
                        print(f"Error adding notification to Firestore for product {product_id}: {e}")

            else:
    
                print(f"Skipping product {product_id} due to missing price or targetedPrice.")
    except Exception as e:
        print(f"Error Processing Colleciom for sending notification {website_Name}")

# calling the function
for website in website_Names:
    try:
        notify_users(website)
    except Exception as e:
        print(f"Error in notify_users() for website {website}: {e}")  

