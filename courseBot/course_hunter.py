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
from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import StaleElementReferenceException

CONFIG_PATH = 'config.json'
COURSES_PATH = 'courses.txt'
LOGIN_URL = 'https://reg.exam.dtu.ac.in/student/login'

PRIORITY_PATH = 'course_priority.json'

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

def load_priorities():
    with open(PRIORITY_PATH, 'r') as f:
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
    # Click the Course Registration button
    try:
        driver.find_element(By.LINK_TEXT, 'Course Registration 2025-26').click()
    except NoSuchElementException:
        # fallback: go directly
        driver.get(reg_url)
    time.sleep(2)

def seat_available(driver, course):
    try:
        xpath = f"//tr[td[contains(text(), '{course['code']}')] and td[contains(text(), '{course['slot']}')]]"
        row = driver.find_element(By.XPATH, xpath)
        cells = row.find_elements(By.TAG_NAME, "td")
        seat_count = int(cells[4].text.strip())
        return seat_count > 0
    except NoSuchElementException:
        return False

def is_higher_priority(course, current_course, courses):
    # Lower index = higher priority
    course_priority = next((i for i, c in enumerate(courses) if c['code'] == course['code'] and c['slot'] == course['slot']), float('inf'))
    current_priority = next((i for i, c in enumerate(courses) if c['code'] == current_course['code'] and c['slot'] == current_course['slot']), float('inf'))
    return course_priority < current_priority

def close_overlays(driver):
    # Try to close any overlay/popups that might block clicks
    try:
        # Try common close buttons
        close_btns = driver.find_elements(By.XPATH, "//button[contains(text(), 'Close') or contains(text(), 'OK') or contains(text(), '×') or contains(@class, 'close')]")
        for btn in close_btns:
            if btn.is_displayed() and btn.is_enabled():
                btn.click()
                print("[DEBUG] Closed overlay/popup.")
                time.sleep(0.5)
    except Exception as e:
        print(f"[DEBUG] No overlay to close or error: {e}")

def print_page_messages(driver):
    # Print any visible alert, error, or success messages
    try:
        messages = driver.find_elements(By.XPATH, "//*[contains(@class, 'alert') or contains(@class, 'error') or contains(@class, 'success') or contains(@role, 'alert')]")
        for msg in messages:
            if msg.is_displayed():
                print(f"[PAGE MESSAGE] {msg.text.strip()}")
    except Exception:
        pass

def register_course(driver, course):
    try:
        xpath = f"//tr[td[contains(text(), '{course['code']}')] and td[contains(text(), '{course['slot']}')]]"
        row = driver.find_element(By.XPATH, xpath)
        # Try to find a button to click (not just form submit)
        for attempt in range(3):
            try:
                reg_button = row.find_element(By.XPATH, ".//button[contains(text(), 'Register') or contains(text(), 'Add') or contains(text(), 'Enroll') or contains(text(), 'Submit')]")
                driver.execute_script("arguments[0].scrollIntoView(true);", reg_button)
                WebDriverWait(driver, 10).until(EC.element_to_be_clickable(reg_button))
                close_overlays(driver)
                reg_button.click()
                print(f"[SUCCESS] Clicked register button for {course['code']} in slot {course['slot']}")
                break
            except (StaleElementReferenceException, Exception) as e:
                print(f"[WARN] Click intercepted or stale element, retrying... ({attempt+1}/3)")
                time.sleep(1)
                row = driver.find_element(By.XPATH, xpath)  # Re-find row and button
        else:
            # Fallback: try form submit
            try:
                form = row.find_element(By.TAG_NAME, "form")
                driver.execute_script("arguments[0].submit();", form)
                print(f"[SUCCESS] Submitted form for {course['code']} in slot {course['slot']}")
            except Exception as e:
                print(f"[ERROR] Could not register for {course['code']} in slot {course['slot']} (no button or form): {e}")
        print_page_messages(driver)
    except NoSuchElementException:
        print(f"[WARN] Could not register for {course['code']} in slot {course['slot']}")

def drop_course(driver, current_course):
    try:
        xpath = f"//tr[td[contains(text(), '{current_course['code']}')] and td[contains(text(), '{current_course['slot']}')]]"
        row = driver.find_element(By.XPATH, xpath)
        drop_btn = row.find_element(By.XPATH, ".//button[contains(text(), 'Drop') and not(@disabled)]")
        drop_form = drop_btn.find_element(By.XPATH, "ancestor::form")
        driver.execute_script("arguments[0].scrollIntoView(true);", drop_btn)
        print(f"[DEBUG] Submitting drop form for {current_course['code']} in slot {current_course['slot']}")
        driver.execute_script("arguments[0].submit();", drop_form)
        print_page_messages(driver)
    except NoSuchElementException:
        print(f"[WARN] Could not find drop button/form for {current_course['code']} in slot {current_course['slot']}")
    except Exception as e:
        print(f"[ERROR] Exception during drop for {current_course['code']} in slot {current_course['slot']}: {e}")

def get_current_registrations(driver):
    """Scan the registration table and return a dict: slot -> course dict for currently registered courses."""
    registered = {}
    try:
        rows = driver.find_elements(By.XPATH, "//tr")
        for row in rows:
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) >= 2:
                code = cells[0].text.strip()
                slot = cells[1].text.strip()
                # Only consider rows that look like course registrations
                if code and slot:
                    registered[slot] = {'code': code, 'slot': slot}
    except Exception as e:
        print(f"[DEBUG] Error scanning registrations: {e}")
    return registered

def detect_current_courses(driver):
    courses = []
    try:
        tables = driver.find_elements(By.XPATH, "//table[contains(@class, 'table') and contains(@class, 'table-bordered')]")
        for table in tables:
            rows = table.find_elements(By.TAG_NAME, "tr")
            for row in rows:
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) >= 6:
                    course_code = cells[1].text.strip()
                    slot = cells[3].text.strip()
                    try:
                        drop_btn = cells[5].find_element(By.XPATH, ".//button[contains(text(), 'Drop') and not(@disabled)]")
                        if course_code and slot:
                            courses.append({"code": course_code, "slot": slot})
                    except Exception:
                        continue
    except Exception as e:
        print(f"[ERROR] Could not detect courses: {e}")
    return courses

def wait_for_table_or_message(driver, timeout=10):
    # Wait for either the table to update or a page message to appear
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: d.find_elements(By.XPATH, "//*[contains(@class, 'alert') or contains(@class, 'error') or contains(@class, 'success') or contains(@role, 'alert')]") or
                      d.find_elements(By.XPATH, "//table[contains(@class, 'table') and contains(@class, 'table-bordered')]")
        )
    except TimeoutException:
        pass
    # Return any visible messages
    messages = driver.find_elements(By.XPATH, "//*[contains(@class, 'alert') or contains(@class, 'error') or contains(@class, 'success') or contains(@role, 'alert')]")
    for msg in messages:
        if msg.is_displayed():
            return msg.text.strip()
    return None

def hunt_courses(driver, priorities):
    while True:
        driver.refresh()
        time.sleep(0.6)
        print("[DEBUG] Refreshed site.")
        current_courses = detect_current_courses(driver)
        current_by_slot = {c['slot']: c['code'] for c in current_courses}
        print("[DEBUG] Current registrations:", current_by_slot)
        for slot, priority_list in priorities.items():
            registered_code = current_by_slot.get(slot)
            if registered_code and registered_code in priority_list:
                registered_priority = priority_list.index(registered_code)
            else:
                registered_priority = None
            for i, course_code in enumerate(priority_list):
                if registered_priority is not None and i >= registered_priority:
                    break
                try:
                    xpath = f"//tr[td[contains(text(), '{course_code}')] and td[contains(text(), '{slot}')]]"
                    row = driver.find_element(By.XPATH, xpath)
                    cells = row.find_elements(By.TAG_NAME, "td")
                    seat_count = int(cells[4].text.strip())
                    if seat_count > 0:
                        print(f"[INFO] Seat available for {course_code} in slot {slot}.")
                        if registered_code:
                            print(f"[INFO] Dropping {registered_code} from slot {slot} to upgrade to {course_code}")
                            drop_course(driver, {"code": registered_code, "slot": slot})
                            print("[DEBUG] Drop complete. Breaking to refresh and re-detect.")
                            break  # After drop, refresh and re-detect everything
                        else:
                            print(f"[INFO] Registering for {course_code} in slot {slot}")
                            register_course(driver, {"code": course_code, "slot": slot})
                            print("[DEBUG] Registration attempt complete. Breaking to refresh and re-detect.")
                            break  # After register, refresh and re-detect everything
                except Exception as e:
                    print(f"[WARN] Could not check/register {course_code} in slot {slot}: {e}")
                time.sleep(0.6)
        print("[INFO] Done checking all priorities.")
        print("[INFO] Waiting 0.6 seconds before next check...")
        time.sleep(0.6)

def main():
    config = load_config()
    priorities = load_priorities()
    chromedriver_path = './chromedriver'
    service = Service(chromedriver_path)
    options = webdriver.ChromeOptions()
    driver = webdriver.Chrome(service=service, options=options)
    try:
        login(driver, config['username'], config['password'])
        go_to_registration(driver, config)
        print("[INFO] Starting continuous monitoring. Press Ctrl+C to stop.")
        hunt_courses(driver, priorities)
    finally:
        print("Done. Leaving browser open for review.")
        # driver.quit()  # Uncomment to close browser automatically

if __name__ == '__main__':
    main() 