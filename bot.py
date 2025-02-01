# Imports
import os
import time
import threading
import requests
import contextlib
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import google.generativeai as genai

# Constants
CONVERSATION_URL = 'https://www.messenger.com/t/1620008488123023'
CREDENTIALS_FILE = "credentials"
API_KEY = ""
HISTORY_FILE = "history.txt"
CHAT_SUPERVISION_TRIGGER_NAME = "big nigga"

# Utility Functions
def remove_non_ascii(text):
    """Removes non-ASCII characters from a string."""
    return ''.join(char for char in text if ord(char) < 128)

def clear_terminal():
    """Clears the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

def load_credentials(filename):
    """Loads credentials from a file."""
    data = {}
    with open(filename, 'r') as file:
        for line in file:
            key, value = line.strip().split('=')
            data[key] = value
            if key == "API_KEY":
                API_KEY = data[key]
    return data

# Selenium Interaction Functions
def accept_cookies(driver):
    """Accepts cookies on the website if prompted."""
    try:
        accept_button = WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.XPATH, "//button[@id='allow_button']"))
        )
        accept_button.click()
        print("Cookies accepted.")
    except Exception as e:
        print("Cookies acceptance button not found:", str(e))

def login(driver, credentials):
    """Logs into Facebook Messenger."""
    try:
        phone_textbox = driver.find_element(By.XPATH, "//input[@id='email']")  
        password_textbox = driver.find_element(By.XPATH, "//input[@id='pass']")
        
        phone_textbox.send_keys(credentials['phone_nr'])
        password_textbox.send_keys(credentials['password'])
        
        login_button = driver.find_element(By.XPATH, "//button[@id='loginbutton']")
        login_button.click()
        print("Logged in.")
        
        insert_pin(driver, credentials['pin'])
    except Exception as e:
        print("Couldn't login:", str(e))

def insert_pin(driver, pin):
    """Inserts the security pin if prompted."""
    try:
        time.sleep(10)
        pin_box = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//input[@id='mw-numeric-code-input-prevent-composer-focus-steal']"))
        )
        pin_box.send_keys(pin)
        print("Pin entered.")
    except Exception as e:
        print("Couldn't enter PIN:", str(e))

def send_message(driver, message):
    """Sends a message in the Messenger chat."""
    try:
        message_box = driver.find_element(By.XPATH, "//div[@aria-label='Mensagem']")
        message_box.send_keys(message)
        message_box.send_keys(Keys.RETURN)
    except Exception as e:
        print("Couldn't send message:", str(e))

def get_history(driver, nr_messages):
    """Fetches the last 'nr_messages' from chat history."""
    message_elements = driver.find_elements(By.XPATH, "//div[@data-pagelet='MWMessageRow']")
    #print(div.alt)
    #history = "\n".join(div.text.replace("Enter", "\n") for div in message_elements[-nr_messages:])

    history = ""
    for div in message_elements[-nr_messages:]:
        text = div.text.replace("Enter", "\n")
        #print(div)
        history += text + "\n"

    return remove_non_ascii(history)

# Generative Model Functions
def configure_genai(api_key):
    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-1.5-flash")

def send_gemini(model, message):
    """Sends a message to the Gemini model and returns the response."""
    response = model.generate_content(message)
    return remove_non_ascii(response.text)
    #return response.text

# Prompt and Response Functions
def build_prompt(history, nr_words, adjetivos, desired_response=""):
    """Builds a prompt based on history and given parameters."""
    insert_desired_string = f"a dizer {desired_response}" if desired_response else ""
    prompt = (
        f"Em aproximadamente {nr_words} palavras, escreve uma resposta sem aspas a esta mensagem "
        f"{insert_desired_string} como se fosses eu, mantendo o meu estilo de escrita informal. "
        f"Tenta que a tua resposta seja: {', '.join(adjetivos)}. As últimas mensagens do chat foram as seguintes:\n{history}"
    )
    return prompt

def create_context_appropriate_message(driver, model, desired_response=""):
    """Creates a context-appropriate message using chat history and model."""
    history = get_history(driver, 5)
    prompt = build_prompt(history, 20, ["medieval","sofisticada", "irônica", "insultuosa", "católica", "intelectual"], desired_response)
    
    while True:
        try:
            response = send_gemini(model, prompt)
            return response
        except Exception:
            print("Couldn't generate response. Retrying...")

# Chat Supervision Functions
def summarize_last_messages(driver, original_request, model):
    nr_messages = 20
    words = original_request.split()
    for i in range(len(words) - 1):
        if words[i] == "mensagens":
            nr_messages = int(words[i - 1])

    last_x_messages = get_history(driver, nr_messages)
    return send_gemini(model, "Faz um resumo do seguinte chat:\n\n" + last_x_messages)


def chat_closed(driver):
    last_message = ""
    while True:
        current_message = get_history(driver, 1)

        if(last_message != current_message):
            if("abre o chat" in current_message ):
                send_message(driver,"o chat ta aberto podem voltar a dizer merda")
                break
            else:
                send_message(driver, "CALEM A PUTA DA BOCA O CHAT ESTA FECHADO")
                last_message = current_message

        time.sleep(3)


def remove_trigger_name(message):
    return message.replace(CHAT_SUPERVISION_TRIGGER_NAME, '')


def supervise_chat(driver, model):
    with open(HISTORY_FILE, 'a') as file:
        last_message = ""
        while CHAT_SUPERVISION:
            current_message = get_history(driver, 1)
            if current_message != last_message:
                file.write(current_message)
                last_message = current_message
            
            if CHAT_SUPERVISION_TRIGGER_NAME in current_message:
                current_message = remove_trigger_name(current_message)
                response = ""
                print("BOT COMMAND: "+current_message)
                if "resume" in current_message:
                    response = summarize_last_messages(driver, current_message, model)
                if "fecha o chat" in current_message:
                    chat_closed(driver)
                else:
                    history = get_history(driver, 10)
                    prompt = f"{current_message}. Se necessario utiliza o contexto das seguintes mensagens: \n{history} "
                    response = send_gemini(model, prompt)

                if response != "":
                    send_message(driver, response)
            time.sleep(0.5)

def run_bot():
    clear_terminal()
    driver = webdriver.Chrome()
    driver.get(CONVERSATION_URL)
    
    genai_model = configure_genai(API_KEY)
    accept_cookies(driver)

    credentials = load_credentials(CREDENTIALS_FILE)
    login(driver, credentials)

    supervising_thread = threading.Thread(target=supervise_chat, args=(driver, genai_model))
    
    global CHAT_SUPERVISION
    CHAT_SUPERVISION = False
    
    
    while True:
        clear_terminal()
        print(f""" ---- OPTIONS ----
1 - Send message
2 - Send context-appropriate response
3 - Respond with context
4 - Toggle chat supervision ({'ON' if CHAT_SUPERVISION else 'OFF'})
E - Exit
""")
        user_input = input("Select option: ")
        
        if user_input == '1':
            input_message = input("Message: ")
            send_message(driver, input_message)
        elif user_input in {'2', '3'}:
            desired_response = input("Response to give: ") if user_input == '3' else ""
            response_message = create_context_appropriate_message(driver, genai_model, desired_response)
            send_message(driver, response_message)
        elif user_input == '4':
            CHAT_SUPERVISION = not CHAT_SUPERVISION
            if CHAT_SUPERVISION:
                supervising_thread.start()
            else:
                supervising_thread.join()
        elif user_input.lower() == 'e':
            break
        else:
            print("Invalid command")



# Main Program
def main():
    try:
        run_bot()
    except Exception as e:
        print(f"Exception occurred: {e}")
        time.sleep(5)
        main()

if __name__ == "__main__":   
    main()
    