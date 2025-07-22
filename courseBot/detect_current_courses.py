import json
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException

CONFIG_PATH = 'config.json'
LOGIN_URL = 'https://reg.exam.dtu.ac.in/student/login'

# Load credentials
def load_config():
    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)

def login(driver, username, password):
    driver.get(LOGIN_URL)
    wait = WebDriverWait(driver, 15)
    roll_no_input = wait.until(EC.presence_of_element_located((By.NAME, 'roll_no')))
    roll_no_input.send_keys(username)
    driver.find_element(By.NAME, 'password').send_keys(password)
    driver.find_element(By.XPATH, "//button[@type='submit']").click()
    time.sleep(2)

def go_to_registration(driver, config):
    home_url = f'https://reg.exam.dtu.ac.in/student/home/{config["student_id"]}'
    reg_url = f'https://reg.exam.dtu.ac.in/student/courseRegistration/{config["student_id"]}'
    driver.get(home_url)
    time.sleep(1)
    try:
        driver.find_element(By.LINK_TEXT, 'Course Registration 2025-26').click()
    except NoSuchElementException:
        driver.get(reg_url)
    time.sleep(2)

def detect_current_courses(driver):
    print("Detecting currently registered courses...")
    courses = []
    try:
        # Find all elective/registered course tables
        tables = driver.find_elements(By.XPATH, "//table[contains(@class, 'table') and contains(@class, 'table-bordered')]")
        for table in tables:
            rows = table.find_elements(By.TAG_NAME, "tr")
            for row in rows:
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) >= 6:
                    course_code = cells[1].text.strip()
                    slot = cells[3].text.strip()
                    # Check if the Drop button is enabled (not disabled)
                    try:
                        drop_btn = cells[5].find_element(By.XPATH, ".//button[contains(text(), 'Drop') and not(@disabled)]")
                        if course_code and slot:
                            courses.append({"code": course_code, "slot": slot})
                    except Exception:
                        continue  # No enabled Drop button, not registered
    except Exception as e:
        print(f"[ERROR] Could not detect courses: {e}")
    return courses

def main():
    config = load_config()
    chromedriver_path = './chromedriver'
    service = Service(chromedriver_path)
    options = webdriver.ChromeOptions()
    driver = webdriver.Chrome(service=service, options=options)
    try:
        login(driver, config['username'], config['password'])
        go_to_registration(driver, config)
        current_courses = detect_current_courses(driver)
        print("\nCurrently registered courses:")
        for c in current_courses:
            print(f"Slot: {c['slot']} | Course: {c['code']}")
    finally:
        print("Done. Leaving browser open for review.")
        # driver.quit()  # Uncomment to close browser automatically

if __name__ == '__main__':
    main() 