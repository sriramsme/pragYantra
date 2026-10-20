import os
from dotenv import load_dotenv
load_dotenv()

from crew import PersonalAssistantCrew

def run():
    #user_query
    #user_message, recent_chats_summary
    #source_language, target_language, message

    inputs={#"user_query": "What a good day!",
            "user_message": "What a good day!",
            "recent_chats_summary": "We have been talking about the weather and how good the day is!",
            # "source_language": "en",
            # "target_language": "es",
            # "message": "What a good day!"
            }

    PersonalAssistantCrew().crew().kickoff(inputs=inputs)

if __name__ == "__main__":
    run()