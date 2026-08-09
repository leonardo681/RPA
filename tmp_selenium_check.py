from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
import time

options = webdriver.ChromeOptions()
options.add_argument('--headless=new')
options.add_argument('--window-size=1920,1080')

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
try:
    driver.get('https://br.investing.com/currencies/usd-brl')
    time.sleep(5)
    print('title:', driver.title)
    for xpath in [
        '//*[@id="__next"]/div[2]/div[2]/div[2]/div[1]/div[1]/div[3]/div[1]/div[1]/div[1]',
        '//*[@id="__next"]/div[2]/div[2]/div[2]/div[1]/div[1]/div[3]/div[1]/div[1]/div[2]',
        '//*[@id="__next"]/div[2]/div[2]/div[2]/div[1]/div[1]/div[3]/div[3]/div[1]/div[2]',
    ]:
        try:
            el = driver.find_element(By.XPATH, xpath)
            print(xpath, '=>', el.text)
        except Exception as e:
            print(xpath, 'ERR', e)
finally:
    driver.quit()
