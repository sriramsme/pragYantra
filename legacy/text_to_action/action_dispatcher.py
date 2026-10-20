import importlib
from vector_utils.vector_emb import VectorStore, ModelSource
from text_to_action.entity_models import *
from utils import verbose_print
from text_to_action.extract_parameters import NERParameterExtractor,LLMParameterExtractor

class ActionDispatcher:
    """
    Function Calling mechanism.
    """
    def __init__(self,vector_store_path,actions_file_name,use_llm_extract_parameters=False,spacy_model_ner="en_core_web_trf"):
        """
        Parameters:
        vector_store_path : The path to the vector store. (Example: calculator.h5)
        actions_file_name : The name of the file containing the actions. (Example: calculator.py)
        use_llm_extract_parameters : Whether to use LLM to extract all parameters. (Default: False)
        spacy_model_ner : The name of the spaCy model to use for parameter extraction. (Default: en_core_web_trf)
        """
        self.task_handler_context_store = VectorStore(embedding_model="all-MiniLM-L6-v2",
                                                      model_source = ModelSource.SBERT)
        self.task_handler_context_store.load(vector_store_path)
        self.parameter_extractor = LLMParameterExtractor() if use_llm_extract_parameters else NERParameterExtractor(spacy_model_ner)

        self.actions_module = importlib.import_module(f"text_to_action.actions.{actions_file_name}")


    @staticmethod
    def execute_action(function_name: callable, extracted_parameters: Dict[str, Any]) -> Any:
        verbose_print("Executing action: {}".format(function_name.__name__))
        try:
            result = function_name(**extracted_parameters)
            return result
        except Exception as e:
            print(f"Error executing function: {e}")
            return None
        
    def dispatch(self, query_text,*args, **kwargs):
        """
        Dispatch the task to the appropriate functions.

        Args:
            text : The text input.

        Returns: results : The results of the function calls.
        """
        possible_actions = self.task_handler_context_store.query(query_text,k=5)

        self.parameter_extractor.clear()

        results = {}
        threshold = 0.45
        # threshold value for function selection
        if "threshold" in kwargs:
            threshold = kwargs["threshold"]     

        for action in possible_actions:
            if action[1] > threshold and action[0].id_name not in results:
                action_to_perform = getattr(self.actions_module, action[0].id_name)
                try:
                    extracted_params = self.parameter_extractor.extract_parameters(query_text, action_to_perform)
                except Exception as e:
                    print(f"Error extracting parameters for function {action_to_perform.__name__}: {e}")
                    continue
                results[action[0].id_name] = self.execute_action(action_to_perform, extracted_params)
                break

        return results
        

if __name__ == '__main__':
    from config import Config
    dispatcher = ActionDispatcher("calculator.h5","calculator",use_llm_extract_parameters=True)
    Config.set_verbose(True)
    while True:
        user_input = input("Enter your query: ")
        if user_input.lower() == 'quit':
            break
        results = dispatcher.dispatch(user_input)
        for result in results:
            print(result,":",results[result])
        print('\n')