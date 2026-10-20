from abc import ABC, abstractmethod
from typing import Dict, Any, List, Type
from utils import verbose_print
import inspect
from collections import Counter
from pydantic import BaseModel
from text_to_action.llm_utils import llm_extract_parameters, llm_map_pydantic_parameters,llm_extract_all_parameters
from text_to_action.entity_models import *

class ParameterExtractor(ABC):
    @abstractmethod
    def extract_parameters(self, query_text: str, function_name: callable) -> Dict[str, Any]:
        pass

    def clear(self):
        return

class NERParameterExtractor(ParameterExtractor):
    
    def __init__(self, spacy_model_ner: str):
        import spacy
        self.entity_recognizer = spacy.load(spacy_model_ner)
        self.entities = None

    def clear(self):
        self.entities = None
        return 
    
    def _ner(self, query_text: str) -> Dict[str, List[str]]:
        doc = self.entity_recognizer(query_text)
        self.entities = {}
        for ent in doc.ents:
            entity_type = str(ent.label_).upper()
            value = ent.text
            if entity_type in globals():
                class_obj = globals()[entity_type]
                if issubclass(class_obj, BaseModel):
                    fields = list(class_obj.model_fields.keys())
                    if len(fields) == 1:
                        instance = class_obj(**{fields[0]: value})
                    else:
                        instance = class_obj(value)
                    self.entities[entity_type] = [instance] if entity_type not in self.entities else self.entities[entity_type] + [instance]
    
    def extract_parameters(self, query_text: str, function_name: callable) -> Dict[str, Any]:
        """
        Return extracted args from the query text using NER (and LLM if any params are missing).
        """
        if self.entities is None:
            self._ner(query_text)
        
        return self._map_parameters(function_name, self.entities, query_text)

    def _map_parameters(self, function_name: callable, extracted_parameters, query_text: str) -> Dict[str, Any]:
        # Get the signature of the function
        sig = inspect.signature(function_name)
        
        # Prepare a dictionary to hold the parameter instances/values
        arguments = {}
        
       # Count the expected number of parameters for each type
        expected_param_counts = Counter(param.annotation for param in sig.parameters.values())

        # Check if we need to extract additional parameters
        for param_annotation, expected_count in expected_param_counts.items():
            param_type = param_annotation.__name__.upper()
            if param_type == "LIST":
                param_type =  param_annotation.__args__[0].__name__.upper()

            if param_type not in extracted_parameters:
                extracted_parameters[param_type] = []
            
            if len(extracted_parameters[param_type]) < expected_count and param_type != 'STR':
                # Use LLM to extract missing parameters
                verbose_print(f"Extracting parameters for {param_type} using llm: {extracted_parameters[param_type]}")
                extracted_parameters[param_type] = llm_extract_parameters(query_text, globals()[param_type])
        

        verbose_print(f"Extracted paramaeters: {extracted_parameters}")
        # Check if we can skip llm_map_pydantic_parameters
        need_llm_mapping = False
        for name, param in sig.parameters.items():
            if param.annotation is str:
                arguments[name] = query_text

            elif param.annotation.__name__ == 'List':
                param_type = param.annotation.__args__[0].__name__.upper()
                if param_type in extracted_parameters:
                    arguments[name] = extracted_parameters[param_type]
                else:
                    print(f"No matching entity found for {name}")
                    return None
                
            elif param.annotation.__name__.upper() in extracted_parameters:
                extracted_values = extracted_parameters[param.annotation.__name__.upper()]
                if len(extracted_values) == 1:
                    arguments[name] = extracted_values[0]
                else:
                    need_llm_mapping = True
                    break

            else:
                print(f"No matching entity found for {name}")
                return None

        if need_llm_mapping:
            # We need to use llm_map_pydantic_parameters
            verbose_print(f"Mapping parameters to correct kwarg using llm: {extracted_parameters}")
            param_descriptions = ", ".join([f"{name} ({param.annotation.__name__})" for name, param in sig.parameters.items()])
            mapped_params = llm_map_pydantic_parameters(query_text, function_name.__name__, param_descriptions, extracted_parameters)

            verbose_print(f"param  mapping: {mapped_params}")
            for name, param in sig.parameters.items():
                if name in mapped_params:
                    arguments[name] = mapped_params[name]
                elif param.annotation is str:
                    arguments[name] = query_text
                else:
                    print(f"No matching entity found for {name}")
                    return None

        return arguments
    
class LLMParameterExtractor(ParameterExtractor):
    def extract_parameters(self, query_text: str, function_name: callable) -> Dict[str, Any]:
        return llm_extract_all_parameters(function_name, query_text)
