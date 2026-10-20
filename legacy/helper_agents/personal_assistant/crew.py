from crewai import Agent, Task, Crew, Process
from crewai.project import CrewBase, agent, crew, task
from langchain_groq import ChatGroq

@CrewBase
class PersonalAssistantCrew():
    """Personal Assistant Crew"""
    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    def __init__(self)-> None:
        self.llm = ChatGroq(
            temperature=0,  
            model_name="llama3-8b-8192"
        )

    @agent
    def personal_assistant(self) -> Agent:
        return Agent(
            config=self.agents_config["personal_assistant"],
            llm=self.llm,
            max_iter=3
        )
    
    # @agent
    # def visual_aider(self) -> Agent:
    #     return Agent(
    #         config=self.agents_config["visual_aider"],
    #         llm=self.llm
    #     )
    
    # @agent
    # def auditory_aider(self) -> Agent:
    #     return Agent(
    #         config=self.agents_config["auditory_aider"],
    #         llm=self.llm
    #     )
    
    # @task
    # def answer_user_task(self) -> Task:
    #     return Task(
    #         config=self.tasks_config["answer_user_task"],
    #         agent=self.personal_assistant()
    #     )
    
    @task
    def converse_user_task(self) -> Task:
        return Task(
            config=self.tasks_config["converse_user_task"],
            agent=self.personal_assistant()
        )
    
    # @task
    # def ask_user_question_task(self) -> Task:
    #     return Task(
    #         config=self.tasks_config["ask_user_question_task"],
    #         agent=self.personal_assistant()
    #     )
    
    # @task
    # def translate_message_task(self) -> Task:
    #     return Task(
    #         config=self.tasks_config["translate_message_task"],
    #         agent=self.personal_assistant()
    #     )
    
    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.hierarchical,
            verbose=2,
            manager_llm=self.llm
        )