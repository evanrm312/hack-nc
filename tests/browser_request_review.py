"""Real Firefox regression against an explicitly isolated sandbox preview.

Run with Selenium and geckodriver installed outside application dependencies:
  python tests/browser_request_review.py http://127.0.0.1:5057 /path/to/geckodriver
Never run against a shared database. This creates one private QA request.
Gemini is mocked; request creation/retry authorization and persistence are real.
"""
import json
import sys
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import Select, WebDriverWait

base, driver_path = sys.argv[1:3]
if base != "http://127.0.0.1:5057":
    raise SystemExit("Use the isolated completion preview on 5057.")
options = webdriver.FirefoxOptions()
options.add_argument("-headless")
driver = webdriver.Firefox(service=Service(driver_path), options=options)
wait = WebDriverWait(driver, 12)
checks = []

def check(name, condition):
    checks.append({"name": name, "passed": bool(condition)})
    print(name, "PASS" if condition else "FAIL", flush=True)
    assert condition, name

def click(element):
    driver.execute_script('arguments[0].scrollIntoView({block:"center",behavior:"instant"})', element)
    element.click()

try:
    driver.get(base + "/sign-in")
    Select(driver.find_element(By.ID, "sandbox-email")).select_by_value("alice@unc.edu")
    click(driver.find_element(By.CSS_SELECTOR, "#sandbox-form button"))
    wait.until(lambda d: d.find_element(By.ID, "nav-sign-in").text == "Account")
    driver.get(base + "/")
    wait.until(lambda d: not d.find_element(By.ID, "request-submit").get_property("disabled"))
    driver.execute_script('''
      const original = api.post.bind(api);
      window.reviewCalls = [];
      window.reviewIds = [];
      api.post = async (path, body, options) => {
        if (path === '/api/requests/normalize') return { normalized: {
          source:'gemini', modes:['borrow'], category:'formalwear',
          needed_by:'2027-01-05T17:00:00Z',
          ambiguous_dates:[{field:'needed_by',text:'next Tuesday',proposed:'2027-01-05T17:00:00Z'}]
        }};
        if (path === '/api/requests') {
          window.reviewCalls.push(options.headers['Idempotency-Key']);
          const result = await original(path, body, options);
          window.reviewIds.push(result.request.id);
          sessionStorage.setItem('qa-review-keys', JSON.stringify(window.reviewCalls));
          if (window.reviewCalls.length === 1) throw new api.ApiError(503,{error:{code:'network_unavailable',message:'Simulated lost response'}});
          return result;
        }
        return original(path, body, options);
      };
    ''')
    text = driver.find_element(By.ID, "request-text")
    text.clear()
    text.send_keys("QA borrow a suit next Tuesday")
    click(driver.find_element(By.ID, "request-submit"))
    wait.until(lambda d: d.find_element(By.ID, "confirm").is_displayed())
    check("ambiguous date stops before request creation", driver.execute_script("return reviewCalls.length === 0"))
    click(driver.find_element(By.ID, "confirm-submit"))
    wait.until(lambda d: d.find_element(By.ID, "f-date-review").get_attribute("aria-invalid") == "true")
    check("explicit date review required", driver.execute_script("return reviewCalls.length === 0"))
    click(driver.find_element(By.ID, "f-date-review"))
    date = driver.find_element(By.ID, "f-needed-by")
    driver.execute_script('arguments[0].dispatchEvent(new Event("input",{bubbles:true}))', date)
    check("date edits invalidate acknowledgement", not driver.find_element(By.ID, "f-date-review").is_selected())
    click(driver.find_element(By.ID, "f-date-review"))
    click(driver.find_element(By.ID, "confirm-submit"))
    wait.until(lambda d: d.find_element(By.ID, "confirm-error").is_displayed())
    check("failed response preserves reviewed form", driver.find_element(By.ID, "f-date-review").is_selected() and driver.find_element(By.ID, "c-text").get_attribute("value") == "QA borrow a suit next Tuesday")
    ids, keys = driver.execute_script("return [reviewIds.slice(),reviewCalls.slice()]")
    click(driver.find_element(By.ID, "confirm-submit"))
    wait.until(lambda d: "/results/" in d.current_url)
    check("retry opens same persisted request", driver.current_url.endswith(ids[0]))
    retried_keys = driver.execute_script("return JSON.parse(sessionStorage.getItem('qa-review-keys'))")
    check("retry uses same creation key", len(retried_keys) == 2 and retried_keys[0] == retried_keys[1] == keys[0])
finally:
    driver.quit()
    print(json.dumps(checks, indent=2))
    print("SUMMARY", len(checks), sum(c["passed"] for c in checks), "passed")
