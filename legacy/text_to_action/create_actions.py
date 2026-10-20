from vector_utils.vector_emb import VectorStore, ModelSource
import time

def create_actions_context_store(functions_description, file_name):
    """
    Creates a context store (VectorStore) for the given functions_description and saves it to a file (.h5).
    """
    store = VectorStore()
    start_time = time.time()
    for i in functions_description:
        store.add_vector(text=i["prompt"],id_name=i["name"])
    print("Time taken to add vectors: ",time.time()-start_time)
    store.save(file_name)

if __name__ == "__main__":
    #sample
    functions_description = [    {
        "name": "add",
        "prompt": "20+50"
    },
    {
        "name": "subtract",
        "prompt": "What is 10 minus 4?"
    }]
    
    start_time = time.time()    
    create_actions_context_store(functions_description, "calculator.h5")
    print("Time taken to add vectors: ",time.time()-start_time)
    
