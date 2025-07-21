import json
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import NoSuchElementException
import os
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

CONFIG_PATH = 'config.json'
COURSES_PATH = 'courses.txt'
LOGIN_URL = 'https://reg.exam.dtu.ac.in/student/login'

# Load credentials
def load_config():
    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)

def load_courses():
    courses = []
    with open(COURSES_PATH, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                code, slot = line.split(':')
                courses.append({'code': code.strip(), 'slot': slot.strip(), 'registered': False})
    return courses

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
    # Click the Course Registration button
    try:
        driver.find_element(By.LINK_TEXT, 'Course Registration 2025-26').click()
    except NoSuchElementException:
        # fallback: go directly
        driver.get(reg_url)
    time.sleep(2)

def hunt_courses(driver, courses):
    while not all(c['registered'] for c in courses):
        driver.refresh()
        time.sleep(1.2)  # Fast, but not too aggressive
        for course in courses:
            if course['registered']:
                continue
            try:
                # Find the row for the course code and slot
                xpath = f"//tr[td[contains(text(), '{course['code']}')] and td[contains(text(), '{course['slot']}')]]"
                row = driver.find_element(By.XPATH, xpath)
                # Check seat count (5th cell, index 4)
                cells = row.find_elements(By.TAG_NAME, "td")
                seat_count = int(cells[4].text.strip())
                if seat_count > 0:
                    form = row.find_element(By.TAG_NAME, "form")
                    driver.execute_script("arguments[0].submit();", form)
                    print(f"[SUCCESS] Registered for {course['code']} in slot {course['slot']}")
                    course['registered'] = True
                    time.sleep(0.2)
                else:
                    print(f"[INFO] No seats for {course['code']} in slot {course['slot']}")
            except NoSuchElementException:
                continue
    print("All specified courses registered!")

def main():
    config = load_config()
    courses = load_courses()
    # Setup Chrome driver
    chromedriver_path = './chromedriver'
    service = Service(chromedriver_path)
    options = webdriver.ChromeOptions()
    # options.add_argument('--headless')  # Visible mode
    driver = webdriver.Chrome(service=service, options=options)
    try:
        login(driver, config['username'], config['password'])
        go_to_registration(driver, config)
        hunt_courses(driver, courses)
    finally:
        print("Done. Leaving browser open for review.")
        # driver.quit()  # Uncomment to close browser automatically

if __name__ == '__main__':
    main() 