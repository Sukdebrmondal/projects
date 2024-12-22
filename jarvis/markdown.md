# Voice Assistance Project Documentation

## Overview
The Voice Assistance Project is a Python-based personal assistant program designed to perform various tasks such as responding to user queries, telling jokes, opening websites, and playing songs. The project uses speech recognition and text-to-speech technologies to enable hands-free interaction.

---

## Features
- Voice interaction to understand and execute user commands.
- Responds to queries about its name, age, and well-being.
- Provides the current time.
- Opens commonly used websites such as YouTube, Google, Brave Browser,    and ChatGPT.
- Tells jokes using the pyjokes library.
- Plays songs from a predefined directory.
- Gracefully shuts down upon user request.

---

## Requirements
To run the project, ensure you have the following Python modules installed:

```
comtypes==1.4.8
PyAudio==0.2.14
pyjokes==0.8.3
pypiwin32==223
pyttsx3==2.98
pywin32==308
SpeechRecognition==3.12.0
typing_extensions==4.12.2
```
---

## Code Walkthrough

### Importing Required Libraries
```python
import pyttsx3
import speech_recognition as sr
import webbrowser
import datetime
import pyjokes
import os
```
The required libraries provide text-to-speech (pyttsx3), speech recognition (speech_recognition), web browsing, date-time functionalities, jokes, and file system access.

---

### Speech-to-Text Function
```python
def sptext():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:  
        print("Listening......")
        recognizer.adjust_for_ambient_noise(source)
        audio = recognizer.listen(source)
        try:
            print("Recognizing....")
            data = recognizer.recognize_google(audio)
            print(data)
            return data
        except sr.UnknownValueError:
            print("Ami bujta pari ni ,na na tumi to kichu bolo ni")
            return "nothing"
```
- Listens for user input via microphone.
- Converts audio to text using Google's Speech Recognition API.
- Handles errors if speech is unrecognizable.

---

### Text-to-Speech Function
```python
def text_to_speech(x):
    engine = pyttsx3.init()
    voices = engine.getProperty('voices')
    engine.setProperty('voice', voices[1].id)
    rate = engine.getProperty('rate')
    engine.setProperty('rate', 120)
    engine.say(x)
    engine.runAndWait()
```
- Converts text to speech using the pyttsx3 library.
- Configures the voice and speech rate.

---

- Waits for the user to initiate the assistant by saying "Hello Jarvis".
- Continuously listens for commands and executes corresponding actions.
- Gracefully shuts down when the user says "shutdown".

---

## Key Commands
| Command             | Action                          |
|---------------------|---------------------------------|
| "your name"         | Replies with its name.          |
| "how are you"       | Responds about its well-being.  |
| "old are you"       | Tells its age.                  |
| "time now"          | Announces the current time.     |
| "open YouTube"      | Opens YouTube in the browser.   |
| "open Google"       | Opens Google in the browser.    |
| "open Brave Browser"| Opens Brave browser.            |
| "open Chat GPT"     | Opens ChatGPT.                  |
| "joke"              | Tells a joke.                   |
| "play song"         | Plays a song from a directory.  |
| "shutdown"          | Shuts down the assistant.       |

---

## Setup and Usage
1. Install the required Python modules:
   ```bash
   pip install -r requirements.txt
   ```
2. Create a directory named music and add some audio files for the "play song" feature.
3. Run the script:
   ``` bash
   python voice_assistance.py
   ```
4. Interact with the assistant using voice commands.

---

## Notes
- Ensure your microphone is functional.
- Background noise can affect speech recognition accuracy.
- The music directory should be in the same location as the script.
- Modify the script to add more functionalities as needed.

---

## Future Enhancements
- Add support for more commands.
- Integrate with APIs for advanced functionalities (e.g., weather updates, email handling).
- Improve error handling and robustness.
- Allow customization of the assistant's voice and responses.