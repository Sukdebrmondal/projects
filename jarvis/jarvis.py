import pyttsx3
import speech_recognition as sr
import webbrowser
import datetime
import pyjokes
import os


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
        except  sr.UnknownValueError:
            # if you not say 
            print("Ami bujta pari ni ,na na tumi to kichu bolo ni")
            return "nothing"
        
# Text to Speech
def text_to_speech(x):
    engine = pyttsx3.init()   
    voices = engine.getProperty('voices')  
    engine.setProperty('voice',voices[1].id)    
    rate = engine.getProperty('rate')
    engine.setProperty('rate',120)
    # for speck
    engine.say(x)
    engine.runAndWait()

if __name__ == '__main__':

    if sptext().lower() == "hello jarvis":
        text_to_speech("Hello Sir how can i help now? ")
        while True:

            # store the data
            data1 = sptext().lower()
            if "your name" in data1:
                name = "my name is jarvis and also you made me"
                text_to_speech(name)

            elif "how are you" in data1:
                age = "i am fine and i hope ou are also fine"
                text_to_speech(age)

            elif "how r u" in data1:
                age = "i am fine and i hope ou are also fine"
                text_to_speech(age)

            elif "old are you" in data1:
                age = "i am one day old"
                text_to_speech(age)

            elif "time now" in data1:
                tie = datetime.datetime.now().strftime("%I%M%p")
                text_to_speech(tie)
            elif "open youtube" in data1:
                text_to_speech("opening youtube")
                webbrowser.open("https://www.youtube.com/")

            elif "open google" in data1:
                text_to_speech("opening Google")
                webbrowser.open("https://www.google.com/")

            elif "open brave browser" in data1:
                text_to_speech("open brave browser")
                webbrowser.open("https://www.google.com/")

            elif "open chat gpt" in data1:
                text_to_speech("opening chat gpt")
                webbrowser.open("https://chatgpt.com/")

            elif "joke" in data1:
                joke_1= pyjokes.get_joke(language = "en",category="all")
                print(joke_1)
                text_to_speech(joke_1)

            elif "play song" in data1:
                song = "music"
                list_song = os.listdir(song)
                print(list_song)
                os.startfile(os.path.join(song,list_song[1]))

            elif "shutdown" in data1:
                text_to_speech("Good Bye have a nice day")
                break

            elif "shut down" in data1:
                text_to_speech("Good Bye sir have a nice day")
                break
            
else:
    print("Thanks")