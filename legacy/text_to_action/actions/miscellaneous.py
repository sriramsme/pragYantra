from text_to_action.entity_models import *
from typing import Union

def get_weather(location: GPE):
    """
    Get the weather, climate information.
    """
    print("Getting weather information for", location.name)

def get_news(category: Union[EVENT, NORP, GPE, PERSON, LOC, ORG, PRODUCT, LAW, FAC]):
    """
    Get the latest news.
    """
    print("Getting news for", category.name)

def get_time(location: GPE):
    """
    Get the time for a location.
    """
    print("Getting time for", location.name)

def get_context_from_memory(text: str):
    """
    Get the context from memory. Recall, retrieve the memory from past.
    """
    print("Getting context from memory for", text)

def play_music(text: str):
    """
    Play a song or playlist.
    """
    print("Playing music for", text)

def get_stock(org: ORG):
    """
    Get the stock information.
    """
    print("Getting stock information for", org.name)

def get_definition(text: str):
    """
    Get the definitions of a word.
    """
    print("Getting definitions for", text)

def translate_text(text: str, language: LANGUAGE):
    """
    Translate text to a given language.
    """
    print("Translating", text, "to", language.name)

def set_reminder(text: str, time: TIME):
    """
    Set a reminder for an event or task.
    """
    print("Setting reminder for", text, "at", time.time)

def book_flight(origin: GPE, destination: GPE, time: TIME):
    """
    Book a flight from origin to destination at a given time.
    """
    print("Booking flight from", origin, "to", destination, "at", time.time)

def send_message(text: str, recipient: Union[GPE, PERSON]):
    """
    Send a message to a contact.
    """
    print("Sending message to", recipient, "with text", text)

def get_recipe(dish: str):
    """
    Get the recipe for a dish.
    """
    print("Getting recipe for", dish)

